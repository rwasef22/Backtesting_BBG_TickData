"""Full simulation of May 9th with complete handler logic"""
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

target_date = datetime(2025, 5, 9).date()

print(f"Full simulation of {target_date} with handler logic...")
print()

# Create handler
handler = create_mm_handler(config=config)

# Initialize state
state = {}
orderbook = OrderBook()

# Load Excel data for May 9th only
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

rows_data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            if timestamp.date() != target_date:
                continue
                
            event_type = str(row[1]).lower() if row[1] else None
            price = float(row[2]) if row[2] is not None else None
            volume = float(row[3]) if row[3] is not None else None
            
            rows_data.append({
                'timestamp': timestamp,
                'type': event_type,
                'price': price,
                'volume': volume
            })
        except:
            pass

print(f"Found {len(rows_data)} rows for {target_date}")

# Create DataFrame
df = pd.DataFrame(rows_data)

# Process with handler
state = handler('EMAAR', df, orderbook, state)

print(f"\nResults after processing {target_date}:")
print(f"  Rows processed: {state.get('rows', 0)}")
print(f"  Bids: {state.get('bid_count', 0)}")
print(f"  Asks: {state.get('ask_count', 0)}")
print(f"  Trades: {state.get('trade_count', 0)}")
print(f"  Strategy trades: {len(state.get('trades', []))}")
print(f"  Position: {state.get('position', 0)}")
print(f"  P&L: ${state.get('pnl', 0):.2f}")
print()

if state.get('trades'):
    print(f"First 5 strategy trades:")
    for i, trade in enumerate(state['trades'][:5], 1):
        side = trade.get('side', 'UNK')
        qty = trade.get('quantity', trade.get('qty', 0))
        price = trade.get('price', 0)
        print(f"  {i}. {side:4s} {qty:6.0f} @ ${price:7.3f}")
else:
    print("NO STRATEGY TRADES GENERATED")
