"""
Focused diagnostic trace for 2025-05-09.

Captures:
  - First few best bid/ask updates
  - Our quoted prices/sizes per side
  - First 20 trades and whether they should hit our quotes
  - Position/P&L snapshots after each trade
"""
import sys
import os
from datetime import datetime, time
import pandas as pd

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_loader import stream_sheets
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
import json


def main():
    # Load config
    with open('configs/mm_config.json', 'r') as f:
        config = json.load(f)
    
    # Data file path
    data_file = 'data/raw/TickData.xlsx'
    security = 'EMAAR'
    target_date = '2025-05-09'
    
    print(f"\n{'='*80}")
    print(f"DIAGNOSTIC TRACE FOR {security} ON {target_date}")
    print(f"{'='*80}\n")
    
    # Initialize strategy and orderbook
    strategy = MarketMakingStrategy(config=config)
    strategy.initialize_security(security)
    orderbook = OrderBook()
    
    bid_updates_logged = 0
    ask_updates_logged = 0
    trades_logged = 0
    max_bid_updates = 3
    max_ask_updates = 3
    max_trades = 20
    
    trace_events = []
    
    # Stream the data
    for sheet_name, chunk_df in stream_sheets(data_file, header_row=3, chunk_size=10000):
        # Copy to avoid SettingWithCopyWarning
        chunk_df = chunk_df.copy()
        
        # Normalize type column to lowercase
        if 'Type' in chunk_df.columns:
            chunk_df['Type'] = chunk_df['Type'].astype(str).str.lower()
        
        # Rename columns to match expected format
        col_map = {
            'Dates': 'timestamp',
            'Type': 'type',
            'Price': 'price',
            'Size': 'volume'
        }
        chunk_df = chunk_df.rename(columns=col_map)
        
        # Parse timestamp
        chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'], errors='coerce')
        
        # Filter to target date
        chunk_df = chunk_df[chunk_df['timestamp'].dt.date == pd.to_datetime(target_date).date()]
        
        if chunk_df.empty:
            continue
        
        print(f"Processing {len(chunk_df)} rows for {target_date}")
        
        # Process each row
        for row in chunk_df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = row.type
            price = row.price
            volume = row.volume
            
            if pd.isna(timestamp) or pd.isna(price):
                continue
            
            # Skip opening auction (9:30-10:00)
            if strategy.is_in_opening_auction(timestamp):
                continue
            
            # Skip closing auction (14:45-15:00)
            if strategy.is_in_closing_auction(timestamp):
                continue
            
            # Update orderbook
            try:
                orderbook.apply_update({
                    'timestamp': timestamp,
                    'type': event_type,
                    'price': float(price),
                    'volume': float(volume)
                })
            except Exception as e:
                continue
            
            # Log bid updates
            if event_type == 'bid' and bid_updates_logged < max_bid_updates:
                best_bid = orderbook.get_best_bid()
                print(f"[BID UPDATE] {timestamp} | Price: {price}, Volume: {volume}")
                print(f"  -> Best bid now: {best_bid}")
                bid_updates_logged += 1
                trace_events.append(('bid_update', timestamp, price, volume, best_bid))
            
            # Log ask updates
            elif event_type == 'ask' and ask_updates_logged < max_ask_updates:
                best_ask = orderbook.get_best_ask()
                print(f"[ASK UPDATE] {timestamp} | Price: {price}, Volume: {volume}")
                print(f"  -> Best ask now: {best_ask}")
                ask_updates_logged += 1
                trace_events.append(('ask_update', timestamp, price, volume, best_ask))
            
            # Process refill and quotes
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # Generate quotes if we have a market
            quotes = strategy.generate_quotes(security, best_bid, best_ask)
            if quotes and event_type in ['bid', 'ask']:
                cfg = strategy.get_config(security)
                threshold = cfg.get('min_local_currency_before_quote', 25000)
                should_refill_bid = strategy.should_refill_side(security, timestamp, 'bid')
                should_refill_ask = strategy.should_refill_side(security, timestamp, 'ask')
                
                # Check refill for bid
                if best_bid is not None and should_refill_bid:
                    bid_price = quotes['bid_price']
                    bid_size = quotes['bid_size']
                    if bid_price is not None:
                        bid_ahead = orderbook.bids.get(bid_price, 0)
                        bid_local = bid_price * bid_ahead
                        bid_ok = bid_local >= threshold and bid_size > 0
                        
                        if bid_ok:
                            strategy.active_orders.setdefault(security, {'bid': {}, 'ask': {}})
                            strategy.active_orders[security]['bid'] = {
                                'price': bid_price,
                                'ahead_qty': int(bid_ahead),
                                'our_remaining': int(bid_size)
                            }
                            strategy.quote_prices[security]['bid'] = bid_price
                            strategy.set_refill_time(security, 'bid', timestamp)
                
                # Check refill for ask
                if best_ask is not None and should_refill_ask:
                    ask_price = quotes['ask_price']
                    ask_size = quotes['ask_size']
                    if ask_price is not None:
                        ask_ahead = orderbook.asks.get(ask_price, 0)
                        ask_local = ask_price * ask_ahead
                        ask_ok = ask_local >= threshold and ask_size > 0
                        
                        if ask_ok:
                            strategy.active_orders.setdefault(security, {'bid': {}, 'ask': {}})
                            strategy.active_orders[security]['ask'] = {
                                'price': ask_price,
                                'ahead_qty': int(ask_ahead),
                                'our_remaining': int(ask_size)
                            }
                            strategy.quote_prices[security]['ask'] = ask_price
                            strategy.set_refill_time(security, 'ask', timestamp)
            
            # Process trades
            if event_type == 'trade' and trades_logged < max_trades:
                bid_price = strategy.quote_prices[security].get('bid')
                ask_price = strategy.quote_prices[security].get('ask')
                
                # Determine if trade should hit our quotes
                bid_hit = bid_price is not None and float(price) <= float(bid_price)
                ask_hit = ask_price is not None and float(price) >= float(ask_price)
                
                # Show diagnostic info
                should_refill_bid = strategy.should_refill_side(security, timestamp, 'bid')
                should_refill_ask = strategy.should_refill_side(security, timestamp, 'ask')
                last_refill_bid = strategy.last_refill_time[security].get('bid')
                last_refill_ask = strategy.last_refill_time[security].get('ask')
                cfg = strategy.get_config(security)
                threshold = cfg.get('min_local_currency_before_quote', 25000)
                
                print(f"\n[TRADE {trades_logged+1}] {timestamp} | Price: {price}, Volume: {volume}")
                print(f"  Our quotes: Bid={bid_price} Ask={ask_price}")
                print(f"  Trade hits BID? {bid_hit} | Trade hits ASK? {ask_hit}")
                print(f"  Refill status: Bid_should_refill={should_refill_bid}, Ask_should_refill={should_refill_ask}")
                print(f"  Last refills: Bid={last_refill_bid}, Ask={last_refill_ask}")
                print(f"  Min local currency threshold: {threshold}")
                
                # Record before processing
                pos_before = strategy.position[security]
                pnl_before = strategy.get_total_pnl(security, float(price) if pd.notna(price) else None)
                
                # Process trade
                strategy.process_trade(security, timestamp, float(price), float(volume), orderbook=orderbook)
                
                # Record after processing
                pos_after = strategy.position[security]
                pnl_after = strategy.get_total_pnl(security, float(price) if pd.notna(price) else None)
                
                print(f"  Position: {pos_before} -> {pos_after} (delta: {pos_after - pos_before})")
                print(f"  P&L: {pnl_before:.2f} -> {pnl_after:.2f} (delta: {pnl_after - pnl_before:.2f})")
                
                trades_logged += 1
                trace_events.append(('trade', timestamp, price, volume, bid_hit, ask_hit, pos_after, pnl_after))
        
        # If we've logged enough, break
        if trades_logged >= max_trades:
            break
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Bid updates logged: {bid_updates_logged}")
    print(f"Ask updates logged: {ask_updates_logged}")
    print(f"Trades logged: {trades_logged}")
    print(f"Final position: {strategy.position[security]}")
    print(f"Final P&L: {strategy.get_total_pnl(security, None):.2f}")
    print(f"Total fills recorded: {len(strategy.trades[security])}")
    
    if strategy.trades[security]:
        print(f"\nFills recorded:")
        for i, trade in enumerate(strategy.trades[security][:10]):
            print(f"  {i+1}. {trade}")


if __name__ == '__main__':
    main()
