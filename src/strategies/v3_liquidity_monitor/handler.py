"""
Handler for v3_liquidity_monitor strategy.

Extends V2 handler with continuous orderbook depth monitoring.
Key addition: Checks liquidity at quoted prices on EVERY orderbook update.
"""

from datetime import time
from .strategy import V3LiquidityMonitorStrategy


def create_v3_liquidity_monitor_handler(config: dict = None):
    """Factory function to create v3 handler.
    
    Args:
        config: dict mapping security -> parameters
    
    Returns:
        handler function for use with backtest.run_streaming()
    """
    strategy = V3LiquidityMonitorStrategy(config=config)
    
    def v3_handler(security, df, orderbook, state):
        """Market-making handler for v3 strategy.
        
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
            
            # 2) Execute pending flatten
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
            
            # ==== V3 TRADING LOGIC ====
            
            # Get best bid/ask
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # Generate quotes (same as V2)
            quotes = strategy.generate_quotes(security, best_bid, best_ask, timestamp)
            if quotes:
                # Ensure containers exist
                strategy.active_orders.setdefault(security, {
                    'bid': {'price': None, 'ahead_qty': 0, 'our_remaining': 0},
                    'ask': {'price': None, 'ahead_qty': 0, 'our_remaining': 0}
                })
                strategy.quote_prices.setdefault(security, {'bid': None, 'ask': None})

                # --- BID side ---
                if best_bid is not None:
                    bid_price = quotes['bid_price']
                    bid_size = quotes['bid_size']
                    
                    # V3 KEY ADDITION: Check liquidity continuously
                    bid_liquidity_ok = strategy.should_activate_quote(
                        security, 'bid', bid_price, orderbook, timestamp
                    )
                    
                    if bid_liquidity_ok and bid_size > 0:
                        # Check if price changed
                        current_bid_price = strategy.active_orders[security]['bid'].get('price')
                        price_changed = (current_bid_price is None or current_bid_price != bid_price)
                        
                        if price_changed:
                            # Reset queue position at new price
                            bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                            strategy.active_orders[security]['bid'] = {
                                'price': bid_price,
                                'ahead_qty': int(bid_ahead),
                                'our_remaining': int(bid_size)
                            }
                        else:
                            # Price same, just update remaining quantity
                            strategy.active_orders[security]['bid']['our_remaining'] = int(bid_size)
                            # Update ahead_qty based on current orderbook
                            bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                            strategy.active_orders[security]['bid']['ahead_qty'] = int(bid_ahead)
                        
                        strategy.quote_prices[security]['bid'] = bid_price
                        strategy.quotes_active[security]['bid'] = True
                    else:
                        # V3: Withdraw bid quote due to insufficient liquidity or size
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': 0,
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['bid'] = None
                        strategy.quotes_active[security]['bid'] = False

                # --- ASK side ---
                if best_ask is not None:
                    ask_price = quotes['ask_price']
                    ask_size = quotes['ask_size']
                    
                    # V3 KEY ADDITION: Check liquidity continuously
                    ask_liquidity_ok = strategy.should_activate_quote(
                        security, 'ask', ask_price, orderbook, timestamp
                    )
                    
                    if ask_liquidity_ok and ask_size > 0:
                        # Check if price changed
                        current_ask_price = strategy.active_orders[security]['ask'].get('price')
                        price_changed = (current_ask_price is None or current_ask_price != ask_price)
                        
                        if price_changed:
                            # Reset queue position at new price
                            ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                            strategy.active_orders[security]['ask'] = {
                                'price': ask_price,
                                'ahead_qty': int(ask_ahead),
                                'our_remaining': int(ask_size)
                            }
                        else:
                            # Price same, just update remaining quantity
                            strategy.active_orders[security]['ask']['our_remaining'] = int(ask_size)
                            # Update ahead_qty based on current orderbook
                            ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                            strategy.active_orders[security]['ask']['ahead_qty'] = int(ask_ahead)
                        
                        strategy.quote_prices[security]['ask'] = ask_price
                        strategy.quotes_active[security]['ask'] = True
                    else:
                        # V3: Withdraw ask quote due to insufficient liquidity or size
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': 0,
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['ask'] = None
                        strategy.quotes_active[security]['ask'] = False
            
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
    
    return v3_handler
