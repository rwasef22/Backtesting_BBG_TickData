"""
Handler for v2_price_follow_qty_cooldown strategy.

BASED ON v1_baseline handler structure (which works correctly).
Key v2-specific differences:
1. Quotes on EVERY BID/ASK event (not just after refill timer)
2. Uses last_fill_time for cooldown (not last_refill_time)
3. Resets queue position when price changes
"""

from .strategy import V2PriceFollowQtyCooldownStrategy


def create_v2_price_follow_qty_cooldown_handler(config: dict = None):
    """Factory function to create v2 handler.
    
    Args:
        config: dict mapping security -> parameters
    
    Returns:
        handler function for use with backtest.run_streaming()
    """
    strategy = V2PriceFollowQtyCooldownStrategy(config=config)
    
    def v2_handler(security, df, orderbook, state):
        """Market-making handler for v2 strategy.
        
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
            state['pending_flatten'] = None  # Track pending EOD position to flatten
        
        # Process each row (columns: timestamp, type, price, volume)
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type  # already lowercase from preprocessing
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
            if state['pending_flatten'] is not None:
                if event_type == 'trade':
                    strategy.flatten_position(security, price, timestamp)
                    state['trades'] = strategy.trades[security]
                    state['pending_flatten'] = None
                continue  # Skip all events until we find the trade

            # 3) Handle opening auction
            is_opening_auction = strategy.is_in_opening_auction(timestamp)
            
            # 4) Skip silent period (10:00-10:05)
            if strategy.is_in_silent_period(timestamp):
                continue
            
            # 5) Skip closing auction (14:45-15:00)
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
            
            # ==== V2 TRADING LOGIC ====
            
            # 5. Get best bid/ask from orderbook
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # 6. V2 KEY DIFFERENCE: Generate quotes on EVERY update (no timer check)
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
                # V2: Always update (no should_refill_side check)
                if best_bid is not None:
                    bid_price = quotes['bid_price']
                    bid_size = quotes['bid_size']
                    bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                    bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                    bid_ok = bid_local >= threshold and bid_size > 0

                    if bid_ok:
                        # Check if price changed
                        current_bid_price = strategy.active_orders[security]['bid'].get('price')
                        price_changed = (current_bid_price is None or current_bid_price != bid_price)
                        
                        if price_changed:
                            # Reset queue position at new price
                            strategy.active_orders[security]['bid'] = {
                                'price': bid_price,
                                'ahead_qty': int(bid_ahead),
                                'our_remaining': int(bid_size)
                            }
                        else:
                            # Price same, update remaining (cooldown may have changed)
                            strategy.active_orders[security]['bid']['our_remaining'] = int(bid_size)
                        
                        strategy.quote_prices[security]['bid'] = bid_price
                    else:
                        # Suppress bid quote - insufficient liquidity
                        strategy.active_orders[security]['bid'] = {
                            'price': bid_price,
                            'ahead_qty': int(bid_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['bid'] = None

                # --- ASK side ---
                # V2: Always update (no should_refill_side check)
                if best_ask is not None:
                    ask_price = quotes['ask_price']
                    ask_size = quotes['ask_size']
                    ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                    ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                    ask_ok = ask_local >= threshold and ask_size > 0

                    if ask_ok:
                        # Check if price changed
                        current_ask_price = strategy.active_orders[security]['ask'].get('price')
                        price_changed = (current_ask_price is None or current_ask_price != ask_price)
                        
                        if price_changed:
                            # Reset queue position at new price
                            strategy.active_orders[security]['ask'] = {
                                'price': ask_price,
                                'ahead_qty': int(ask_ahead),
                                'our_remaining': int(ask_size)
                            }
                        else:
                            # Price same, update remaining (cooldown may have changed)
                            strategy.active_orders[security]['ask']['our_remaining'] = int(ask_size)
                        
                        strategy.quote_prices[security]['ask'] = ask_price
                    else:
                        # Suppress ask quote - insufficient liquidity
                        strategy.active_orders[security]['ask'] = {
                            'price': ask_price,
                            'ahead_qty': int(ask_ahead),
                            'our_remaining': 0
                        }
                        strategy.quote_prices[security]['ask'] = None
            
            # 7. Process market trades (skip during opening auction)
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
    
    return v2_handler
