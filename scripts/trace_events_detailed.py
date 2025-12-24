"""
Detailed event-by-event trace for 2025-05-09 showing exact order of bid/ask/trade events
and when quotes are placed.
"""
import sys
import os
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_loader import stream_sheets
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
import json


def main():
    with open('configs/mm_config.json', 'r') as f:
        config = json.load(f)
    
    data_file = 'data/raw/TickData.xlsx'
    security = 'EMAAR'
    target_date = '2025-05-09'
    
    print(f"\n{'='*100}")
    print(f"DETAILED EVENT TRACE FOR {security} ON {target_date}")
    print(f"{'='*100}\n")
    
    strategy = MarketMakingStrategy(config=config)
    strategy.initialize_security(security)
    orderbook = OrderBook()
    
    event_count = 0
    trade_count = 0
    max_events = 100  # Show first 100 events
    
    for sheet_name, chunk_df in stream_sheets(data_file, header_row=3, chunk_size=10000):
        chunk_df = chunk_df.copy()
        
        if 'Type' in chunk_df.columns:
            chunk_df['Type'] = chunk_df['Type'].astype(str).str.lower()
        
        col_map = {
            'Dates': 'timestamp',
            'Type': 'type',
            'Price': 'price',
            'Size': 'volume'
        }
        chunk_df = chunk_df.rename(columns=col_map)
        chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'], errors='coerce')
        
        # Filter to target date
        chunk_df = chunk_df[chunk_df['timestamp'].dt.date == pd.to_datetime(target_date).date()]
        
        if chunk_df.empty:
            continue
        
        print(f"Processing {len(chunk_df)} rows\n")
        
        for row in chunk_df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type
            price = row.price
            volume = row.volume
            
            if pd.isna(timestamp) or pd.isna(price):
                continue
            
            # Show all events in opening window (8:00 to 10:05)
            ts_hour = timestamp.hour
            ts_min = timestamp.minute
            in_open_window = (ts_hour == 8) or (ts_hour == 9) or (ts_hour == 10 and ts_min <= 5)
            
            if not in_open_window:
                continue
            
            # Check if it's opening auction time
            is_opening = strategy.is_in_opening_auction(timestamp)
            is_closing = strategy.is_in_closing_auction(timestamp)
            
            # Update orderbook before auction checks
            try:
                orderbook.apply_update({
                    'timestamp': timestamp,
                    'type': event_type,
                    'price': float(price),
                    'volume': float(volume)
                })
            except:
                pass
            
            # Get current best bid/ask
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # Generate quotes
            quotes = strategy.generate_quotes(security, best_bid, best_ask)
            
            # Check refill eligibility
            should_refill_bid = strategy.should_refill_side(security, timestamp, 'bid')
            should_refill_ask = strategy.should_refill_side(security, timestamp, 'ask')
            
            # Show event
            print(f"[{event_count+1:3d}] {timestamp.strftime('%H:%M:%S.%f')[:-3]} | {event_type.upper():6s} | Price: {price:7.2f}, Vol: {volume:8.0f}")
            print(f"       -> OpenAuction={is_opening}, ClosingAuction={is_closing}")
            print(f"       -> OrderBook: Bid={best_bid}, Ask={best_ask}")
            print(f"       -> Quotes generated: {quotes}")
            print(f"       -> Should refill BID={should_refill_bid}, ASK={should_refill_ask}")
            
            # Check if we can refill
            if quotes and best_bid is not None and should_refill_bid:
                bid_price = quotes['bid_price']
                bid_size = quotes['bid_size']
                if bid_price is not None:
                    bid_ahead = orderbook.bids.get(bid_price, 0)
                    bid_local = bid_price * bid_ahead
                    threshold = strategy.get_config(security)['min_local_currency_before_quote']
                    bid_ok = bid_local >= threshold and bid_size > 0
                    print(f"           BID: price={bid_price}, ahead={bid_ahead}, local={bid_local:.0f}, threshold={threshold}, OK={bid_ok}")
                    
                    if bid_ok:
                        strategy.active_orders.setdefault(security, {'bid': {}, 'ask': {}})
                        strategy.active_orders[security]['bid'] = {'price': bid_price, 'ahead_qty': int(bid_ahead), 'our_remaining': int(bid_size)}
                        strategy.quote_prices[security]['bid'] = bid_price
                        strategy.set_refill_time(security, 'bid', timestamp)
                        print(f"           -> BID QUOTE PLACED at {bid_price}")
            
            if quotes and best_ask is not None and should_refill_ask:
                ask_price = quotes['ask_price']
                ask_size = quotes['ask_size']
                if ask_price is not None:
                    ask_ahead = orderbook.asks.get(ask_price, 0)
                    ask_local = ask_price * ask_ahead
                    threshold = strategy.get_config(security)['min_local_currency_before_quote']
                    ask_ok = ask_local >= threshold and ask_size > 0
                    print(f"           ASK: price={ask_price}, ahead={ask_ahead}, local={ask_local:.0f}, threshold={threshold}, OK={ask_ok}")
                    
                    if ask_ok:
                        strategy.active_orders.setdefault(security, {'bid': {}, 'ask': {}})
                        strategy.active_orders[security]['ask'] = {'price': ask_price, 'ahead_qty': int(ask_ahead), 'our_remaining': int(ask_size)}
                        strategy.quote_prices[security]['ask'] = ask_price
                        strategy.set_refill_time(security, 'ask', timestamp)
                        print(f"           -> ASK QUOTE PLACED at {ask_price}")
            
            # Process trades
            if event_type == 'trade':
                bid_price = strategy.quote_prices[security].get('bid')
                ask_price = strategy.quote_prices[security].get('ask')
                bid_hit = bid_price is not None and float(price) <= float(bid_price)
                ask_hit = ask_price is not None and float(price) >= float(ask_price)
                
                pos_before = strategy.position[security]
                strategy.process_trade(security, timestamp, float(price), float(volume), orderbook=orderbook)
                pos_after = strategy.position[security]
                
                print(f"           TRADE: OurBid={bid_price}, OurAsk={ask_price}, BidHit={bid_hit}, AskHit={ask_hit}")
                print(f"           TRADE: Position {pos_before} -> {pos_after}")
                trade_count += 1
            
            print()
            event_count += 1
            if event_count >= max_events:
                break
        
        if event_count >= max_events:
            break
    
    print(f"\n{'='*100}")
    print(f"Events shown: {event_count}, Trades processed: {trade_count}")
    print(f"Final position: {strategy.position[security]}")
    print(f"Total fills recorded: {len(strategy.trades[security])}")


if __name__ == '__main__':
    main()
