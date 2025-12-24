"""Check what state exists at the start of May 9th in full backtest vs isolation"""
import openpyxl
from datetime import datetime
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
from src.mm_handler import create_mm_handler
import json
import pandas as pd

# Load config
with open('configs/mm_config.json') as f:
    config = json.load(f)

print("=" * 70)
print("SIMULATING CHUNK 1 UP TO MAY 9TH")
print("=" * 70)

# Create handler (same strategy object persists across dates)
handler = create_mm_handler(config=config)

# Get the strategy object to inspect state
import types
strategy = None
if isinstance(handler, types.FunctionType):
    # Extract strategy from closure
    strategy = handler.__closure__[0].cell_contents

state = {}
orderbook = OrderBook()

# Load Excel data for Chunk 1 up to and including May 9th
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

# Process dates up to May 8th first
may8_data = []
may9_data = []
earlier_data = []

for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            date_only = timestamp.date()
            target_may8 = datetime(2025, 5, 8).date()
            target_may9 = datetime(2025, 5, 9).date()
            
            if date_only < target_may8:
                earlier_data.append({
                    'timestamp': timestamp,
                    'type': str(row[1]).lower() if row[1] else None,
                    'price': float(row[2]) if row[2] is not None else None,
                    'volume': float(row[3]) if row[3] is not None else None
                })
            elif date_only == target_may8:
                may8_data.append({
                    'timestamp': timestamp,
                    'type': str(row[1]).lower() if row[1] else None,
                    'price': float(row[2]) if row[2] is not None else None,
                    'volume': float(row[3]) if row[3] is not None else None
                })
            elif date_only == target_may9:
                may9_data.append({
                    'timestamp': timestamp,
                    'type': str(row[1]).lower() if row[1] else None,
                    'price': float(row[2]) if row[2] is not None else None,
                    'volume': float(row[3]) if row[3] is not None else None
                })
            elif date_only > target_may9:
                break
        except:
            pass

print(f"\nProcessing dates before May 8th: {len(earlier_data)} rows")
if earlier_data:
    df_earlier = pd.DataFrame(earlier_data)
    state = handler('EMAAR', df_earlier, orderbook, state)
    print(f"  Trades after earlier dates: {len(state.get('trades', []))}")

print(f"\nProcessing May 8th: {len(may8_data)} rows")
if may8_data:
    df_may8 = pd.DataFrame(may8_data)
    trades_before_may8 = len(state.get('trades', []))
    state = handler('EMAAR', df_may8, orderbook, state)
    trades_after_may8 = len(state.get('trades', []))
    print(f"  Trades before May 8th: {trades_before_may8}")
    print(f"  Trades after May 8th: {trades_after_may8}")
    print(f"  New trades on May 8th: {trades_after_may8 - trades_before_may8}")

# Check strategy state after May 8th
if strategy:
    print(f"\nStrategy state after May 8th:")
    print(f"  Position: {strategy.position.get('EMAAR', 0)}")
    print(f"  Last refill bid: {strategy.last_refill_time.get('EMAAR', {}).get('bid')}")
    print(f"  Last refill ask: {strategy.last_refill_time.get('EMAAR', {}).get('ask')}")
    print(f"  Active orders: {strategy.active_orders.get('EMAAR', {})}")

print(f"\nNow processing May 9th: {len(may9_data)} rows")
if may9_data:
    df_may9 = pd.DataFrame(may9_data)
    trades_before_may9 = len(state.get('trades', []))
    state = handler('EMAAR', df_may9, orderbook, state)
    trades_after_may9 = len(state.get('trades', []))
    print(f"  Trades before May 9th: {trades_before_may9}")
    print(f"  Trades after May 9th: {trades_after_may9}")
    print(f"  New trades on May 9th: {trades_after_may9 - trades_before_may9}")

if strategy:
    print(f"\nStrategy state after May 9th:")
    print(f"  Position: {strategy.position.get('EMAAR', 0)}")
    print(f"  Last refill bid: {strategy.last_refill_time.get('EMAAR', {}).get('bid')}")
    print(f"  Last refill ask: {strategy.last_refill_time.get('EMAAR', {}).get('ask')}")

print()
print("=" * 70)
print(f"CONCLUSION: May 9th generated {trades_after_may9 - trades_before_may9} trades in full context")
print("=" * 70)
