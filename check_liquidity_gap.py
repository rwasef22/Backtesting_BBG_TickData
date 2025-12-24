#!/usr/bin/env python
"""Check orderbook liquidity during gap period to see if min_local_currency threshold blocks quoting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

import pandas as pd
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from datetime import datetime, date, time, timedelta

gap_start = date(2025, 4, 23)  # Day after last trade in CSV
gap_end = date(2025, 6, 18)     # Day before trades resume

print(f"Checking liquidity during gap: {gap_start} to {gap_end}\n")

# Track refill windows (5 min intervals)
REFILL_INTERVAL = 300  # seconds
MIN_LOCAL_CURRENCY = 25000

orderbook = OrderBook()
last_check_time = None
checks_with_sufficient_liquidity = 0
checks_with_insufficient_liquidity = 0
sample_insufficient = []

def is_in_auction(ts):
    """Check if timestamp is in auction window."""
    t = ts.time()
    return (time(9, 30) <= t < time(10, 0)) or (time(14, 45) <= t <= time(15, 0))

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    chunk = preprocess_chunk_df(chunk)
    
    for row in chunk.itertuples(index=False):
        ts = pd.to_datetime(row.timestamp)
        ts_date = ts.date()
        
        # Only process gap period
        if not (gap_start <= ts_date <= gap_end):
            continue
        
        # Skip auctions
        if is_in_auction(ts):
            continue
        
        event_type = str(row.type).strip().lower() if pd.notna(row.type) else None
        price = row.price
        volume = row.volume
        
        # Update orderbook
        orderbook.apply_update({
            'timestamp': ts,
            'type': event_type,
            'price': price,
            'volume': volume
        })
        
        # Check liquidity every refill interval
        if last_check_time is None or (ts - last_check_time).total_seconds() >= REFILL_INTERVAL:
            last_check_time = ts
            
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            if best_bid and best_ask:
                bid_price, bid_qty = best_bid
                ask_price, ask_qty = best_ask
                
                bid_local = bid_price * bid_qty
                ask_local = ask_price * ask_qty
                
                bid_ok = bid_local >= MIN_LOCAL_CURRENCY
                ask_ok = ask_local >= MIN_LOCAL_CURRENCY
                
                if bid_ok and ask_ok:
                    checks_with_sufficient_liquidity += 1
                else:
                    checks_with_insufficient_liquidity += 1
                    if len(sample_insufficient) < 10:
                        sample_insufficient.append({
                            'timestamp': ts,
                            'bid_price': bid_price,
                            'bid_qty': bid_qty,
                            'bid_local': bid_local,
                            'ask_price': ask_price,
                            'ask_qty': ask_qty,
                            'ask_local': ask_local,
                            'bid_ok': bid_ok,
                            'ask_ok': ask_ok
                        })

print(f"Refill checks in gap period: {checks_with_sufficient_liquidity + checks_with_insufficient_liquidity:,}")
print(f"  Sufficient liquidity (both sides >= ${MIN_LOCAL_CURRENCY:,}): {checks_with_sufficient_liquidity:,}")
print(f"  Insufficient liquidity: {checks_with_insufficient_liquidity:,}")

if checks_with_insufficient_liquidity > 0:
    pct = 100 * checks_with_insufficient_liquidity / (checks_with_sufficient_liquidity + checks_with_insufficient_liquidity)
    print(f"\n⚠️  {pct:.1f}% of refill opportunities blocked by min_local_currency threshold")
    
    if sample_insufficient:
        print(f"\nSample insufficient liquidity cases:")
        for s in sample_insufficient[:5]:
            print(f"  {s['timestamp']}: bid ${s['bid_price']:.2f} x {s['bid_qty']:.0f} = ${s['bid_local']:,.0f} ({'OK' if s['bid_ok'] else 'BLOCKED'}), "
                  f"ask ${s['ask_price']:.2f} x {s['ask_qty']:.0f} = ${s['ask_local']:,.0f} ({'OK' if s['ask_ok'] else 'BLOCKED'})")
else:
    print(f"\n✓ All refill checks had sufficient liquidity—something else is blocking quotes.")

print("\nDone.")
