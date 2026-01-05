"""
Handler for v2_1_stop_loss strategy.

BASED ON v2_price_follow_qty_cooldown handler.
Key v2.1-specific additions:
1. Monitors unrealized P&L on every orderbook update
2. Triggers stop-loss when loss exceeds threshold
3. Executes liquidation at opposite price (long->bid, short->ask)
4. Supports partial execution when liquidity insufficient
"""

from datetime import time
from .strategy import V21StopLossStrategy


def create_v2_1_stop_loss_handler(config: dict = None):
    """Factory function to create v2.1 handler.
    
    Args:
        config: dict mapping security -> parameters (includes stop_loss_threshold_pct)
    
    Returns:
        handler function for use with backtest.run_streaming()
    """
    strategy = V21StopLossStrategy(config=config)
    
    def v2_1_handler(security, df, orderbook, state):
        """Market-making handler for v2.1 strategy with stop-loss.
        
        Args:
            security: security name (e.g., 'EMAAR')
            df: DataFrame chunk with [timestamp, type, price, volume]
            orderbook: OrderBook instance
            state: dict of accumulated stats
        
        Returns:
            updated state dict
        """
        # Initialize strategy state for this security
        strategy.initialize_security(security)
        
        # Initialize state dict if first time
        if 'rows' not in state:
            state['rows'] = 0
            state['bid_count'] = 0
            state['ask_count'] = 0
            state['trade_count'] = 0
            state['trades'] = []
            state['position'] = 0
            state['pnl'] = 0.0
            state['last_price'] = None
            state['closed_at_eod'] = False
            state['last_flatten_date'] = None
            state['market_dates'] = set()
            state['strategy_dates'] = set()
            state['last_date'] = None
            state['pending_flatten'] = None
            state['stop_loss_triggered_count'] = 0  # V2.1: Track stop-loss triggers
        
        # Process each row
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type
            price = row.price
            volume = row.volume

            # Reset daily flatten flag if date changes
            current_date = timestamp.date()
            
            # Clear orderbook if new trading day
            if state.get('last_date') is not None and state['last_date'] != current_date:
                orderbook.bids.clear()
                orderbook.asks.clear()
                orderbook.last_trade = None
            state['last_date'] = current_date
            
            # Track market trade dates
            if event_type == 'trade':
                state['market_dates'].add(current_date)
            
            if state.get('last_flatten_date') is not None and state['last_flatten_date'] != current_date:
                state['closed_at_eod'] = False
                state['pending_flatten'] = None

            # 1) EOD flatten at/after 14:55
            if strategy.is_eod_close_time(timestamp) and not state['closed_at_eod']:
                if strategy.position[security] != 0:
                    if event_type == 'trade':
                        strategy.flatten_position(security, price, timestamp)
                        state['trades'] = strategy.trades[security]
                        state['closed_at_eod'] = True
                        state['last_flatten_date'] = current_date
                        continue
                    else:
                        state['pending_flatten'] = {
                            'position': strategy.position[security],
                            'entry_price': strategy.entry_price[security],
                            'timestamp': timestamp
                        }
                        state['closed_at_eod'] = True
                        state['last_flatten_date'] = current_date
                        continue
                else:
                    state['closed_at_eod'] = True
                    state['last_flatten_date'] = current_date
            
            # 2) Execute pending flatten when we see a trade
            if state['pending_flatten'] is not None:
                if event_type == 'trade':
                    strategy.flatten_position(security, price, timestamp)
                    state['trades'] = strategy.trades[security]
                    state['pending_flatten'] = None
                continue

            # 3) STRICT TRADING WINDOW: Only trade between 10:00 and 14:45
            # Skip everything before 10:00 (opening auction, pre-market)
            t = timestamp.time()
            if t < time(10, 0, 0):
                continue
            
            # Skip everything at/after 14:45 (closing auction, after market)
            if t >= time(14, 45, 0):
                continue

            # Apply update to orderbook
            orderbook.apply_update({
                'timestamp': timestamp,
                'type': event_type,
                'price': price,
                'volume': volume
            })
            
            # Update counts
            state['rows'] += 1
            if event_type == 'bid':
                state['bid_count'] += 1
            elif event_type == 'ask':
                state['ask_count'] += 1
            elif event_type == 'trade':
                state['trade_count'] += 1
            
            # Track last price
            if event_type == 'trade':
                state['last_price'] = price
            
            # ==== V2.1 STOP LOSS LOGIC ====
            
            # Get best bid/ask for stop-loss monitoring
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # A) Check if we need to trigger stop-loss
            # Use mid price for unrealized P&L calculation
            if best_bid is not None and best_ask is not None and strategy.position[security] != 0:
                mid_price = (best_bid[0] + best_ask[0]) / 2.0
                
                if strategy.should_trigger_stop_loss(security, mid_price):
                    strategy.trigger_stop_loss(security, timestamp)
                    state['stop_loss_triggered_count'] += 1
            
            # B) Execute pending stop-loss liquidation (if any)
            if strategy.stop_loss_pending[security] is not None:
                bid_price = best_bid[0] if best_bid else None
                ask_price = best_ask[0] if best_ask else None
                bid_depth = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                ask_depth = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                
                fully_liquidated = strategy.execute_stop_loss_liquidation(
                    security, bid_price, ask_price, bid_depth, ask_depth, timestamp
                )
                
                if fully_liquidated:
                    state['trades'] = strategy.trades[security]
                    # Continue to normal quote generation below
                else:
                    # Partial fill or no liquidity yet - skip normal quoting this update
                    continue
            
            # ==== V2 TRADING LOGIC (same as V2) ====
            
            # Generate quotes on EVERY update (V2 behavior)
            quotes = strategy.generate_quotes(security, best_bid, best_ask, timestamp)
            if quotes:
                # Ensure containers exist
                strategy.active_orders.setdefault(security, {
                    'bid': {'price': None, 'ahead_qty': 0, 'our_remaining': 0},
                    'ask': {'price': None, 'ahead_qty': 0, 'our_remaining': 0}
                })
                strategy.quote_prices.setdefault(security, {'bid': None, 'ask': None})

                cfg = strategy.get_config(security)
                threshold = cfg.get('min_local_currency_before_quote', 25000)

                # --- BID side ---
                if best_bid is not None:
                    bid_price = quotes['bid_price']
                    bid_size = quotes['bid_size']
                    bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                    bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                    bid_ok = bid_local >= threshold and bid_size > 0

                    if bid_ok:
                        current_bid_price = strategy.active_orders[security]['bid'].get('price')
                        price_changed = (current_bid_price is None or current_bid_price != bid_price)
                        
                        if price_changed:
                            strategy.active_orders[security]['bid'] = {
                                'price': bid_price,
                                'ahead_qty': int(bid_ahead),
                                'our_remaining': int(bid_size)
                            }
                        else:
                            strategy.active_orders[security]['bid']['our_remaining'] = int(bid_size)
                        
                        strategy.quote_prices[security]['bid'] = bid_price
                    else:
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': int(bid_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['bid'] = None

                # --- ASK side ---
                if best_ask is not None:
                    ask_price = quotes['ask_price']
                    ask_size = quotes['ask_size']
                    ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                    ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                    ask_ok = ask_local >= threshold and ask_size > 0

                    if ask_ok:
                        current_ask_price = strategy.active_orders[security]['ask'].get('price')
                        price_changed = (current_ask_price is None or current_ask_price != ask_price)
                        
                        if price_changed:
                            strategy.active_orders[security]['ask'] = {
                                'price': ask_price,
                                'ahead_qty': int(ask_ahead),
                                'our_remaining': int(ask_size)
                            }
                        else:
                            strategy.active_orders[security]['ask']['our_remaining'] = int(ask_size)
                        
                        strategy.quote_prices[security]['ask'] = ask_price
                    else:
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': int(ask_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['ask'] = None
            
            # Process market trades (already in valid trading window 10:00-14:45)
            if event_type == 'trade':
                strategy.process_trade(security, timestamp, price, volume, orderbook=orderbook)
        
        # Update state with final position/P&L
        state['position'] = strategy.position[security]
        state['pnl'] = strategy.get_total_pnl(security, state.get('last_price'))
        state['trades'] = strategy.trades[security]
        
        # Track strategy trading dates
        for trade in strategy.trades[security]:
            trade_date = trade['timestamp'].date() if hasattr(trade['timestamp'], 'date') else trade['timestamp']
            state['strategy_dates'].add(trade_date)
        
        return state
    
    return v2_1_handler
