"""Test ADNOCGAS May 14 flatten with detailed tracing."""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from strategies.v1_baseline.handler import create_v1_handler
from strategies.v1_baseline.strategy import V1BaselineStrategy
from orderbook import OrderBook
from config_loader import load_strategy_config

# Load config
config = load_strategy_config('configs/v1_baseline_config.json')

# Create handler
handler_fn = create_v1_handler(config)

# Read ADNOCGAS May 14 data
print("Loading ADNOCGAS May 14 data...")
df = pd.read_excel('data/raw/TickData.xlsx', sheet_name='ADNOCGAS UH Equity', header=None, skiprows=4)
df.columns = ['timestamp', 'type', 'price', 'volume']
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])
df['type'] = df['type'].astype(str).str.lower().str.strip()

# Filter to May 14 only, around EOD
may14 = df[df['timestamp'].dt.date == pd.Timestamp('2025-05-14').date()].copy()
eod_chunk = may14[may14['timestamp'].dt.time >= pd.Timestamp('14:54:00').time()].copy()

print(f"\nChunk has {len(eod_chunk)} rows")
print(f"First 5 rows at/after 14:55:00:")
eod_555 = eod_chunk[eod_chunk['timestamp'].dt.time >= pd.Timestamp('14:55:00').time()]
print(eod_555.head()[['timestamp', 'type', 'price', 'volume']])

# Prepare state and orderbook
security = 'ADNOCGAS UH Equity'
state = {}
orderbook = OrderBook()

# Process the chunk
print(f"\n{'='*80}")
print("Processing chunk...")
print(f"{'='*80}\n")

result_state = handler_fn(security, eod_chunk, orderbook, state)

# Check trades
trades = result_state.get('trades', [])
print(f"\nTotal trades: {len(trades)}")

# Find EOD flatten trade
eod_trades = [t for t in trades if t['timestamp'].date() == pd.Timestamp('2025-05-14').date() 
              and t['timestamp'].time() >= pd.Timestamp('14:55:00').time()]

if eod_trades:
    print(f"\nTrades at/after 14:55:00 on May 14:")
    for t in eod_trades[:5]:  # Show first 5
        print(f"  {t['timestamp']} | {t['side']:4s} | Price: {t['price']:.2f} | Qty: {t['quantity']:7.0f} | PnL: {t['pnl']:10.2f}")
else:
    print("\nNo trades found at/after 14:55:00")

# Check final position
final_pos = result_state.get('position', 0)
final_pnl = result_state.get('pnl', 0)
print(f"\nFinal position: {final_pos}")
print(f"Final PnL: {final_pnl:.2f}")
