"""Detailed event-by-event trace of strategy execution.

This script creates a comprehensive trace of strategy behavior showing:
- Order book state after each event
- Strategy quote decisions
- Trade fills and P&L updates
- Position tracking

Usage:
    python scripts/trace_strategy_detailed.py --security EMAAR --days 3 --strategy v2
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data_loader import stream_sheets, preprocess_chunk_df
from orderbook import OrderBook
from strategies.v2_price_follow_qty_cooldown.strategy import V2PriceFollowQtyCooldownStrategy
from config_loader import load_strategy_config


def trace_v2_strategy(security: str, max_days: int, output_file: str):
    """Run V2 strategy with detailed event tracing."""
    
    # Load configuration
    config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')
    
    # Initialize strategy
    strategy = V2PriceFollowQtyCooldownStrategy(config=config)
    strategy.initialize_security(security)
    
    # Initialize order book
    orderbook = OrderBook()
    
    # State tracking
    state = {
        'trades': [],
        'last_date': None,
        'closed_at_eod': False,
        'last_flatten_date': None,
        'pending_flatten': None,
        'days_seen': 0
    }
    
    # Trace log
    trace = []
    event_num = 0
    
    # Get config for logging
    cfg = strategy.get_config(security)
    
    print(f"Starting trace for {security}")
    print(f"Configuration: quote_size={cfg['quote_size_bid']}/{cfg['quote_size_ask']}, "
          f"refill_interval={cfg['refill_interval_sec']}s, "
          f"max_position={cfg['max_position']}")
    print(f"Tracing first {max_days} trading days...")
    print()
    
    # Stream data
    sheet_filter = [f'{security} UH Equity']
    file_path = 'data/raw/TickData.xlsx'
    
    for sheet_name, chunk in stream_sheets(file_path, header_row=3, chunk_size=100000, 
                                          sheet_names_filter=sheet_filter):
        
        df = preprocess_chunk_df(chunk)
        
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type
            price = row.price
            volume = row.volume
            
            event_num += 1
            current_date = timestamp.date()
            
            # Track new trading days
            if state.get('last_date') is not None and state['last_date'] != current_date:
                state['days_seen'] += 1
                # Stop after max_days
                if state['days_seen'] >= max_days:
                    break
                    
                # Clear orderbook on new day
                orderbook.bids.clear()
                orderbook.asks.clear()
                orderbook.last_trade = None
                
                trace.append({
                    'event_num': event_num,
                    'timestamp': timestamp,
                    'date': current_date,
                    'event_type': '*** NEW TRADING DAY ***',
                    'event_price': None,
                    'event_volume': None,
                    'ob_best_bid_price': None,
                    'ob_best_bid_qty': None,
                    'ob_best_ask_price': None,
                    'ob_best_ask_qty': None,
                    'in_opening_auction': False,
                    'in_silent_period': False,
                    'in_closing_auction': False,
                    'should_quote_bid': False,
                    'should_quote_ask': False,
                    'quote_bid_price': None,
                    'quote_bid_size': None,
                    'quote_ask_price': None,
                    'quote_ask_size': None,
                    'fill_side': None,
                    'fill_qty': None,
                    'fill_price': None,
                    'position': strategy.position[security],
                    'entry_price': strategy.entry_price[security],
                    'realized_pnl': strategy.pnl[security],
                    'notes': 'Order book cleared'
                })
                
            state['last_date'] = current_date
            
            # Reset daily flatten flag
            if state.get('last_flatten_date') is not None and state['last_flatten_date'] != current_date:
                state['closed_at_eod'] = False
                state['pending_flatten'] = None
            
            # Check time windows
            is_eod = strategy.is_eod_close_time(timestamp)
            is_opening = strategy.is_in_opening_auction(timestamp)
            is_silent = strategy.is_in_silent_period(timestamp)
            is_closing = strategy.is_in_closing_auction(timestamp)
            
            # Store pre-event state
            pre_position = strategy.position[security]
            pre_pnl = strategy.pnl[security]
            pre_entry = strategy.entry_price[security]
            
            # Handle EOD flatten
            notes = []
            if is_eod and not state['closed_at_eod']:
                if strategy.position[security] != 0:
                    if event_type == 'trade':
                        strategy.flatten_position(security, price, timestamp)
                        state['trades'] = strategy.trades[security]
                        state['closed_at_eod'] = True
                        state['last_flatten_date'] = current_date
                        notes.append('EOD flatten executed')
                    else:
                        state['pending_flatten'] = {
                            'position': strategy.position[security],
                            'timestamp': timestamp
                        }
                        state['closed_at_eod'] = True
                        state['last_flatten_date'] = current_date
                        notes.append('EOD flatten pending (waiting for trade)')
                else:
                    state['closed_at_eod'] = True
                    state['last_flatten_date'] = current_date
            
            # Execute pending flatten
            if state['pending_flatten'] is not None:
                if event_type == 'trade':
                    strategy.flatten_position(security, price, timestamp)
                    state['trades'] = strategy.trades[security]
                    state['pending_flatten'] = None
                    notes.append('Pending flatten executed')
                # Continue to skip further processing while waiting for trade
                trace.append({
                    'event_num': event_num,
                    'timestamp': timestamp,
                    'date': current_date,
                    'event_type': event_type.upper(),
                    'event_price': price,
                    'event_volume': volume,
                    'ob_best_bid_price': None,
                    'ob_best_bid_qty': None,
                    'ob_best_ask_price': None,
                    'ob_best_ask_qty': None,
                    'in_opening_auction': is_opening,
                    'in_silent_period': is_silent,
                    'in_closing_auction': is_closing,
                    'should_quote_bid': False,
                    'should_quote_ask': False,
                    'quote_bid_price': None,
                    'quote_bid_size': None,
                    'quote_ask_price': None,
                    'quote_ask_size': None,
                    'fill_side': None,
                    'fill_qty': None,
                    'fill_price': None,
                    'position': strategy.position[security],
                    'entry_price': strategy.entry_price[security],
                    'realized_pnl': strategy.pnl[security],
                    'notes': ' | '.join(notes) if notes else ''
                })
                continue
            
            # Skip silent period - must skip ALL processing
            if is_silent:
                notes.append('Silent period - skipped')
                trace.append({
                    'event_num': event_num,
                    'timestamp': timestamp,
                    'date': current_date,
                    'event_type': event_type.upper(),
                    'event_price': price,
                    'event_volume': volume,
                    'ob_best_bid_price': None,
                    'ob_best_bid_qty': None,
                    'ob_best_ask_price': None,
                    'ob_best_ask_qty': None,
                    'in_opening_auction': is_opening,
                    'in_silent_period': is_silent,
                    'in_closing_auction': is_closing,
                    'should_quote_bid': False,
                    'should_quote_ask': False,
                    'quote_bid_price': None,
                    'quote_bid_size': None,
                    'quote_ask_price': None,
                    'quote_ask_size': None,
                    'fill_side': None,
                    'fill_qty': None,
                    'fill_price': None,
                    'position': strategy.position[security],
                    'entry_price': strategy.entry_price[security],
                    'realized_pnl': strategy.pnl[security],
                    'notes': ' | '.join(notes) if notes else ''
                })
                continue
            
            # Skip closing auction - must skip ALL processing
            if is_closing:
                notes.append('Closing auction - skipped')
                trace.append({
                    'event_num': event_num,
                    'timestamp': timestamp,
                    'date': current_date,
                    'event_type': event_type.upper(),
                    'event_price': price,
                    'event_volume': volume,
                    'ob_best_bid_price': None,
                    'ob_best_bid_qty': None,
                    'ob_best_ask_price': None,
                    'ob_best_ask_qty': None,
                    'in_opening_auction': is_opening,
                    'in_silent_period': is_silent,
                    'in_closing_auction': is_closing,
                    'should_quote_bid': False,
                    'should_quote_ask': False,
                    'quote_bid_price': None,
                    'quote_bid_size': None,
                    'quote_ask_price': None,
                    'quote_ask_size': None,
                    'fill_side': None,
                    'fill_qty': None,
                    'fill_price': None,
                    'position': strategy.position[security],
                    'entry_price': strategy.entry_price[security],
                    'realized_pnl': strategy.pnl[security],
                    'notes': ' | '.join(notes) if notes else ''
                })
                continue
            
            # Apply update to orderbook
            orderbook.apply_update({
                'timestamp': timestamp,
                'type': event_type,
                'price': price,
                'volume': volume
            })
            
            # Get order book state
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # Check if should quote (only if not in restricted periods)
            should_quote_bid = False
            should_quote_ask = False
            quote_bid_price = None
            quote_bid_size = None
            quote_ask_price = None
            quote_ask_size = None
            
            if not (is_silent or is_closing or state.get('pending_flatten')):
                # Check refill conditions
                should_quote_bid = strategy.should_refill_side(security, timestamp, 'bid')
                should_quote_ask = strategy.should_refill_side(security, timestamp, 'ask')
                
                # Generate quotes - V2 generates on every update
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
                    
                    # Process BID
                    if best_bid is not None and quotes.get('bid_price'):
                        quote_bid_price = quotes['bid_price']
                        quote_bid_size = quotes['bid_size']
                        bid_ahead = orderbook.bids.get(quote_bid_price, 0) if quote_bid_price else 0
                        bid_local = (quote_bid_price * bid_ahead) if quote_bid_price else 0
                        bid_ok = bid_local >= threshold and quote_bid_size > 0
                        
                        if bid_ok:
                            current_bid_price = strategy.active_orders[security]['bid'].get('price')
                            price_changed = (current_bid_price is None or current_bid_price != quote_bid_price)
                            
                            if price_changed:
                                strategy.active_orders[security]['bid'] = {
                                    'price': quote_bid_price,
                                    'ahead_qty': int(bid_ahead),
                                    'our_remaining': int(quote_bid_size)
                                }
                            else:
                                strategy.active_orders[security]['bid']['our_remaining'] = int(quote_bid_size)
                            
                            strategy.quote_prices[security]['bid'] = quote_bid_price
                        else:
                            strategy.active_orders[security]['bid'] = {
                                'price': quote_bid_price,
                                'ahead_qty': int(bid_ahead),
                                'our_remaining': 0
                            }
                            strategy.quote_prices[security]['bid'] = None
                            quote_bid_size = None  # Mark as suppressed
                    
                    # Process ASK
                    if best_ask is not None and quotes.get('ask_price'):
                        quote_ask_price = quotes['ask_price']
                        quote_ask_size = quotes['ask_size']
                        ask_ahead = orderbook.asks.get(quote_ask_price, 0) if quote_ask_price else 0
                        ask_local = (quote_ask_price * ask_ahead) if quote_ask_price else 0
                        ask_ok = ask_local >= threshold and quote_ask_size > 0
                        
                        if ask_ok:
                            current_ask_price = strategy.active_orders[security]['ask'].get('price')
                            price_changed = (current_ask_price is None or current_ask_price != quote_ask_price)
                            
                            if price_changed:
                                strategy.active_orders[security]['ask'] = {
                                    'price': quote_ask_price,
                                    'ahead_qty': int(ask_ahead),
                                    'our_remaining': int(quote_ask_size)
                                }
                            else:
                                strategy.active_orders[security]['ask']['our_remaining'] = int(quote_ask_size)
                            
                            strategy.quote_prices[security]['ask'] = quote_ask_price
                        else:
                            strategy.active_orders[security]['ask'] = {
                                'price': quote_ask_price,
                                'ahead_qty': int(ask_ahead),
                                'our_remaining': 0
                            }
                            strategy.quote_prices[security]['ask'] = None
                            quote_ask_size = None  # Mark as suppressed
            
            # Process trade fills
            fill_info = None
            if event_type == 'trade':
                pre_trade_count = len(strategy.trades[security])
                strategy.process_trade(security, timestamp, price, volume, orderbook)
                post_trade_count = len(strategy.trades[security])
                
                # Check if we got filled
                if post_trade_count > pre_trade_count:
                    last_trade = strategy.trades[security][-1]
                    fill_info = {
                        'side': last_trade['side'],
                        'qty': last_trade['fill_qty'],
                        'price': last_trade['fill_price']
                    }
                    notes.append(f"FILL: {last_trade['side']} {last_trade['fill_qty']} @ {last_trade['fill_price']}")
            
            # Detect position/PnL changes
            if strategy.position[security] != pre_position:
                notes.append(f"Position: {pre_position} → {strategy.position[security]}")
            if strategy.pnl[security] != pre_pnl:
                pnl_change = strategy.pnl[security] - pre_pnl
                notes.append(f"PnL change: {pnl_change:+.2f}")
            
            # Log this event
            trace.append({
                'event_num': event_num,
                'timestamp': timestamp,
                'date': current_date,
                'event_type': event_type.upper(),
                'event_price': price,
                'event_volume': volume,
                'ob_best_bid_price': best_bid[0] if best_bid else None,
                'ob_best_bid_qty': best_bid[1] if best_bid else None,
                'ob_best_ask_price': best_ask[0] if best_ask else None,
                'ob_best_ask_qty': best_ask[1] if best_ask else None,
                'in_opening_auction': is_opening,
                'in_silent_period': is_silent,
                'in_closing_auction': is_closing,
                'should_quote_bid': should_quote_bid,
                'should_quote_ask': should_quote_ask,
                'quote_bid_price': quote_bid_price,
                'quote_bid_size': quote_bid_size,
                'quote_ask_price': quote_ask_price,
                'quote_ask_size': quote_ask_size,
                'fill_side': fill_info['side'] if fill_info else None,
                'fill_qty': fill_info['qty'] if fill_info else None,
                'fill_price': fill_info['price'] if fill_info else None,
                'position': strategy.position[security],
                'entry_price': strategy.entry_price[security],
                'realized_pnl': strategy.pnl[security],
                'notes': ' | '.join(notes) if notes else ''
            })
        
        # Break outer loop if we've seen enough days
        if state['days_seen'] >= max_days:
            break
    
    # Convert to DataFrame and save
    df_trace = pd.DataFrame(trace)
    
    # Save to CSV
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_trace.to_csv(output_path, index=False)
    
    print(f"\nTrace complete!")
    print(f"Events traced: {len(df_trace)}")
    print(f"Trading days: {state['days_seen']}")
    print(f"Total trades: {len(strategy.trades[security])}")
    print(f"Final position: {strategy.position[security]}")
    print(f"Final P&L: {strategy.pnl[security]:.2f} AED")
    print(f"\nTrace saved to: {output_path}")
    
    # Print summary statistics
    fills = df_trace[df_trace['fill_side'].notna()]
    if len(fills) > 0:
        print(f"\nFills Summary:")
        print(f"  Total fills: {len(fills)}")
        print(f"  Buy fills: {len(fills[fills['fill_side'] == 'buy'])}")
        print(f"  Sell fills: {len(fills[fills['fill_side'] == 'sell'])}")
        print(f"  Avg fill size: {fills['fill_qty'].mean():.0f}")
        print(f"  Avg fill price: {fills['fill_price'].mean():.3f}")
    
    quotes = df_trace[(df_trace['quote_bid_price'].notna()) | (df_trace['quote_ask_price'].notna())]
    if len(quotes) > 0:
        print(f"\nQuoting Summary:")
        print(f"  Total quote events: {len(quotes)}")
        print(f"  Bid quotes: {quotes['quote_bid_price'].notna().sum()}")
        print(f"  Ask quotes: {quotes['quote_ask_price'].notna().sum()}")
    
    return df_trace


def main():
    parser = argparse.ArgumentParser(description='Detailed strategy trace')
    parser.add_argument('--security', type=str, default='EMAAR', help='Security to trace')
    parser.add_argument('--days', type=int, default=3, help='Number of trading days to trace')
    parser.add_argument('--output', type=str, default=None, help='Output file path')
    
    args = parser.parse_args()
    
    if args.output is None:
        args.output = f'output/trace/{args.security.lower()}_v2_30s_{args.days}days_trace.csv'
    
    trace_v2_strategy(args.security, args.days, args.output)


if __name__ == '__main__':
    main()
