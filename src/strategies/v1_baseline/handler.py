"""Handler for V1 Baseline Strategy.

This handler bridges the V1 baseline strategy with the backtest framework.
It processes streaming data chunks and coordinates between the orderbook,
strategy logic, and state tracking.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from strategies.v1_baseline.strategy import V1BaselineStrategy


def create_v1_handler(config: dict = None):
    """Factory function to create V1 baseline handler.
    
    Args:
        config: Per-security configuration dictionary like:
            {
                'ADCB': {
                    'quote_size': 50000,
                    'refill_interval_sec': 180,
                    'max_position': 130000,
                    'max_notional': 1500000,
                    'min_local_currency_before_quote': 13000
                },
                ...
            }
    
    Returns:
        Handler function for use with backtest.run_streaming(handler=...)
    """
    strategy = V1BaselineStrategy(config=config)
    
    def v1_handler(security, df, orderbook, state):
        """Process data chunk for V1 baseline strategy.
        
        Args:
            security: Security name (e.g., 'ADCB')
            df: DataFrame chunk with [timestamp, type, price, volume]
            orderbook: OrderBook instance
            state: State dictionary
        
        Returns:
            Updated state dictionary
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
        
        # Process each row
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type
            price = row.price
            volume = row.volume

            # Reset daily flatten flag if date changes
            current_date = timestamp.date()
            
            # Clear orderbook on new trading day
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

            # 1) EOD flatten at/after 14:55
            if strategy.is_eod_close_time(timestamp) and not state['closed_at_eod']:
                if strategy.position[security] != 0:
                    close_price = price if price is not None else state.get('last_price', price)
                    strategy.flatten_position(security, close_price, timestamp)
                state['closed_at_eod'] = True
                state['last_flatten_date'] = current_date
                state['trades'] = strategy.trades[security]
                continue

            # 2) Handle opening auction
            is_opening_auction = strategy.is_in_opening_auction(timestamp)
            
            # 3) Skip silent period (10:00-10:05)
            if strategy.is_in_silent_period(timestamp):
                continue
            
            # 4) Skip closing auction (14:45-15:00)
            if strategy.is_in_closing_auction(timestamp):
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
            
            # ==== TRADING LOGIC ====
            
            # Get best bid/ask
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # Check per-side refill and place quotes independently
            quotes = strategy.generate_quotes(security, best_bid, best_ask)
            if quotes:
                # Ensure containers exist
                strategy.active_orders.setdefault(security, {
                    'bid': {'price': None, 'ahead_qty': 0, 'our_remaining': 0},
                    'ask': {'price': None, 'ahead_qty': 0, 'our_remaining': 0}
                })
                strategy.quote_prices.setdefault(security, {'bid': None, 'ask': None})

                cfg = strategy.get_config(security)
                threshold = cfg.get('min_local_currency_before_quote', 25000)

                # --- BID side (independent check) ---
                if best_bid is not None and strategy.should_refill_side(security, timestamp, 'bid'):
                    bid_price = quotes['bid_price']
                    bid_size = quotes['bid_size']
                    bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                    bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                    bid_ok = bid_local >= threshold and bid_size > 0

                    if bid_ok:
                        # Place bid and set timer
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': int(bid_ahead),
                            'our_remaining': int(bid_size)
                        }
                        strategy.quote_prices[security]['bid'] = bid_price
                        strategy.set_refill_time(security, 'bid', timestamp)
                    else:
                        # Suppress bid
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': int(bid_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['bid'] = None

                # --- ASK side (independent check) ---
                if best_ask is not None and strategy.should_refill_side(security, timestamp, 'ask'):
                    ask_price = quotes['ask_price']
                    ask_size = quotes['ask_size']
                    ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                    ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                    ask_ok = ask_local >= threshold and ask_size > 0

                    if ask_ok:
                        # Place ask and set timer
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': int(ask_ahead),
                            'our_remaining': int(ask_size)
                        }
                        strategy.quote_prices[security]['ask'] = ask_price
                        strategy.set_refill_time(security, 'ask', timestamp)
                    else:
                        # Suppress ask
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': int(ask_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['ask'] = None
            
            # Check for fills (skip during opening auction)
            if event_type == 'trade' and not is_opening_auction:
                strategy.process_trade(security, timestamp, price, volume, orderbook=orderbook)
        
        # Update final state
        state['position'] = strategy.position[security]
        state['pnl'] = strategy.pnl[security]
        state['trades'] = strategy.trades[security]
        
        # Track strategy trading dates
        for trade in strategy.trades[security]:
            trade_date = trade['timestamp'].date() if hasattr(trade['timestamp'], 'date') else trade['timestamp']
            state['strategy_dates'].add(trade_date)
        
        return state
    
    return v1_handler
