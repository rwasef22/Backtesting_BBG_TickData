"""Verify mm_handler.py uses correct trade prices for EOD flatten."""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from mm_handler import create_mm_handler
from orderbook import OrderBook
from config_loader import load_strategy_config

# Load config
config = load_strategy_config('configs/v1_baseline_config.json')

# Create handler
handler_fn = create_mm_handler(config)

# Read ADNOCGAS May 14 data
print("Loading ADNOCGAS data...")
df = pd.read_excel('data/raw/TickData.xlsx', sheet_name='ADNOCGAS UH Equity', header=None, skiprows=4)
df.columns = ['timestamp', 'type', 'price', 'volume']
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])
df['type'] = df['type'].astype(str).str.lower().str.strip()

# Filter to May 14 only
may14 = df[df['timestamp'].dt.date == pd.Timestamp('2025-05-14').date()].copy()

print(f"Total rows for May 14: {len(may14)}")

# Process in chunks
security = 'ADNOCGAS UH Equity'
state = {}
orderbook = OrderBook()

chunk_size = 50000
for i in range(0, len(may14), chunk_size):
    chunk = may14.iloc[i:i+chunk_size]
    state = handler_fn(security, chunk, orderbook, state)

# Check trades around 14:55:00
trades = state.get('trades', [])
print(f"\nTotal trades: {len(trades)}")

# Find EOD flatten trade on May 14
may14_trades = [t for t in trades if t['timestamp'].date() == pd.Timestamp('2025-05-14').date()]
eod_trades = [t for t in may14_trades if t['timestamp'].time() >= pd.Timestamp('14:55:00').time()]

if eod_trades:
    print(f"\nTrades at/after 14:55:00 on May 14:")
    for t in eod_trades[:5]:
        print(f"  {t['timestamp']} | {t['side']:4s} | Price: {t['fill_price']:.2f} | Qty: {t['fill_qty']:7.0f} | PnL: {t['pnl']:10.2f}")
    
    # Check the flatten trade (should be the last one that closes position)
    last_trade = may14_trades[-1]
    print(f"\nLast May 14 trade (EOD flatten):")
    print(f"  {last_trade['timestamp']} | {last_trade['side']:4s} | Price: {last_trade['fill_price']:.2f} | Qty: {last_trade['fill_qty']:7.0f} | PnL: {last_trade['pnl']:10.2f}")
    
    if abs(last_trade['fill_price'] - 3.26) < 0.01:
        print("\n✓ SUCCESS: EOD flatten used correct trade price 3.26")
    elif abs(last_trade['fill_price'] - 3.76) < 0.01:
        print("\n✗ FAILURE: EOD flatten still using wrong bid price 3.76")
    else:
        print(f"\n? UNEXPECTED: EOD flatten price is {last_trade['fill_price']:.2f}")
else:
    print("\nNo trades found at/after 14:55:00")

# Check final position
final_pos = state.get('position', 0)
print(f"\nFinal May 14 position: {final_pos}")
print(f"Final May 14 PnL: {state.get('pnl', 0):.2f}")
