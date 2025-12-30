"""Market-making handler function for use with MarketMakingBacktest."""
from src.market_making_strategy import MarketMakingStrategy


def create_mm_handler(config: dict = None):
    """Factory function to create a market-making handler.
    
    config: dict like {
        'ADCB': {'quote_size': 50000, 'refill_interval_sec': 60, 'max_position': 2000000},
        'ADIB': {...},
        ...
    }
    
    Returns: handler function for use with backtest.run_streaming(handler=...)
    """
    strategy = MarketMakingStrategy(config=config)
    
    def mm_handler(security, df, orderbook, state):
        """Market-making handler for streaming backtest.
        
        Args:
            security: security name (e.g., 'ADCB')
            df: DataFrame chunk with [timestamp, type, price, volume]
            orderbook: OrderBook instance (current bid/ask state)
            state: dict of accumulated stats
        
        Returns: updated state dict
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
            state['market_dates'] = set()  # Days with market trades
            state['strategy_dates'] = set()  # Days we executed trades
            state['last_date'] = None  # Track last processed date for orderbook reset
            state['pending_flatten'] = None  # Track pending EOD position to flatten
        
        # Process each row in the chunk using itertuples for better performance
        # `preprocess_chunk_df` ensures columns are ['timestamp','type','price','volume']
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type  # already normalized to lowercase in preprocessing
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
                state['pending_flatten'] = None  # Clear pending flatten on new day

            # 1) EOD flatten at/after 14:55 - use trade price if available
            if strategy.is_eod_close_time(timestamp) and not state['closed_at_eod']:
                if strategy.position[security] != 0:
                    # If current event is a trade, use it immediately
                    if event_type == 'trade':
                        strategy.flatten_position(security, price, timestamp)
                        state['trades'] = strategy.trades[security]
                        state['closed_at_eod'] = True
                        state['last_flatten_date'] = current_date
                        continue
                    else:
                        # Not a trade, mark as pending flatten and wait
                        state['pending_flatten'] = {
                            'position': strategy.position[security],
                            'entry_price': strategy.entry_price[security],
                            'timestamp': timestamp
                        }
                        state['closed_at_eod'] = True
                        state['last_flatten_date'] = current_date
                        continue  # Skip this row, wait for trade
                else:
                    # No position to flatten
                    state['closed_at_eod'] = True
                    state['last_flatten_date'] = current_date
            
            # 2) Execute pending flatten when we see a trade
            if state.get('pending_flatten') is not None:
                if event_type == 'trade':
                    strategy.flatten_position(security, price, timestamp)
                    state['trades'] = strategy.trades[security]
                    state['pending_flatten'] = None
                continue  # Skip all events until we find the trade

            # 2) Handle opening auction: allow book updates and quoting, but skip trade processing
            is_opening_auction = strategy.is_in_opening_auction(timestamp)
            
            # 3) Skip silent period (10:00-10:05)
            if strategy.is_in_silent_period(timestamp):
                continue
            
            # 4) Skip closing auction (14:45-15:00) except the flatten handled above
            if strategy.is_in_closing_auction(timestamp):
                continue

            # Apply update to orderbook (only outside auction windows)
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
            
            # 5. Get best bid/ask from orderbook
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # 6. Check per-side refill and place quotes independently
            quotes = strategy.generate_quotes(security, best_bid, best_ask)
            if quotes:
                # Ensure containers exist
                strategy.active_orders.setdefault(security, {'bid': {'price': None, 'ahead_qty': 0, 'our_remaining': 0},
                                                           'ask': {'price': None, 'ahead_qty': 0, 'our_remaining': 0}})
                strategy.quote_prices.setdefault(security, {'bid': None, 'ask': None})

                cfg = strategy.get_config(security)
                threshold = cfg.get('min_local_currency_before_quote', 25000)

                # --- BID side ---
                if best_bid is not None and strategy.should_refill_side(security, timestamp, 'bid'):
                    bid_price = quotes['bid_price']
                    bid_size = quotes['bid_size']
                    bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                    bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                    bid_ok = bid_local >= threshold and bid_size > 0

                    if bid_ok:
                        # Quote passes liquidity check - place it and set refill time
                        # This makes the quote "stick" for the refill interval
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': int(bid_ahead),
                            'our_remaining': int(bid_size)
                        }
                        strategy.quote_prices[security]['bid'] = bid_price
                        strategy.set_refill_time(security, 'bid', timestamp)
                    else:
                        # Suppress bid quote - insufficient liquidity
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': int(bid_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['bid'] = None

                # --- ASK side ---
                if best_ask is not None and strategy.should_refill_side(security, timestamp, 'ask'):
                    ask_price = quotes['ask_price']
                    ask_size = quotes['ask_size']
                    ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                    ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                    ask_ok = ask_local >= threshold and ask_size > 0

                    if ask_ok:
                        # Quote passes liquidity check - place it and set refill time
                        # This makes the quote "stick" for the refill interval
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': int(ask_ahead),
                            'our_remaining': int(ask_size)
                        }
                        strategy.quote_prices[security]['ask'] = ask_price
                        strategy.set_refill_time(security, 'ask', timestamp)
                    else:
                        # Suppress ask quote - insufficient liquidity
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': int(ask_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['ask'] = None
            
            # 6. Check if market trades hit our quotes (but skip during opening auction)
            if event_type == 'trade' and not is_opening_auction:
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
    
    return mm_handler
