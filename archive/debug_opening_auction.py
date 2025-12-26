#!/usr/bin/env python
"""
Quick debug script to check if opening auction events are being processed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
import json

# Load config
with open('configs/mm_config.json') as f:
    config = json.load(f)

# Create a debug wrapper handler
original_handler = create_mm_handler(config=config)

def debug_handler(security, df, orderbook, state):
    # Count opening auction events
    if 'opening_auction_events' not in state:
        state['opening_auction_events'] = 0
        state['post_auction_events'] = 0
        state['dates_seen'] = set()
    
    for _, row in df.iterrows():
        ts = row['timestamp']
        date_str = str(ts.date()) if hasattr(ts, 'date') else str(ts)[:10]
        state['dates_seen'].add(date_str)
        
        # Check if in opening auction (9:30-10:00)
        try:
            t = ts.time() if hasattr(ts, 'time') else ts
            from datetime import time
            if time(9, 30) <= t < time(10, 0):
                state['opening_auction_events'] += 1
            elif time(10, 0) <= t < time(10, 5):
                state['post_auction_events'] += 1
        except:
            pass
    
    # Call original handler
    state = original_handler(security, df, orderbook, state)
    return state

# Run backtest
backtest = MarketMakingBacktest()
print("Running debug backtest...")
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=debug_handler,
    only_trades=False,
)

print("\nDebug Results:")
for sec, data in results.items():
    print(f"\n{sec}:")
    print(f"  Opening auction events processed: {data.get('opening_auction_events', 0)}")
    print(f"  Post-auction (10:00-10:05) events: {data.get('post_auction_events', 0)}")
    print(f"  Total trades executed: {len(data.get('trades', []))}")
    print(f"  Final position: {data.get('position', 0)}")
    
    # Check if 2025-05-09 was seen
    dates = sorted(list(data.get('dates_seen', set())))
    print(f"  First date: {dates[0] if dates else 'None'}")
    print(f"  Last date: {dates[-1] if dates else 'None'}")
    if '2025-05-09' in dates:
        print(f"  ✓ 2025-05-09 WAS processed")
    else:
        print(f"  ✗ 2025-05-09 NOT found in processed dates")
