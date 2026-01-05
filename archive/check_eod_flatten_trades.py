"""Check for trades at/after 14:55 (EOD flatten period) in V2 backtest."""
import pandas as pd
from pathlib import Path
from datetime import time

# Load all V2 trade files
output_dir = Path('output')
trade_files = list(output_dir.glob('*_trades_timeseries.csv'))

print(f"Checking {len(trade_files)} securities for EOD flatten trades (14:55+)...\n")
print("=" * 100)

total_eod_trades = 0

for trade_file in sorted(trade_files):
    security = trade_file.stem.replace('_trades_timeseries', '').upper()
    
    df = pd.read_csv(trade_file)
    if df.empty:
        continue
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['time'] = df['timestamp'].dt.time
    df['date'] = df['timestamp'].dt.date
    
    # Get trades at/after 14:55
    eod_flatten_time = time(14, 55, 0)
    eod_trades = df[df['time'] >= eod_flatten_time].copy()
    
    if len(eod_trades) > 0:
        total_eod_trades += len(eod_trades)
        
        print(f"\n{security}: {len(eod_trades)} trades at/after 14:55")
        print("-" * 100)
        
        # Group by date
        for date, group in eod_trades.groupby('date'):
            print(f"\n  {date}: {len(group)} trades")
            print(f"    Position before EOD: ?  →  After EOD: {group['position'].iloc[-1]}")
            print(f"    Trades:")
            for idx, row in group.iterrows():
                print(f"      {row['timestamp'].strftime('%H:%M:%S')} - {row['side']:4s} {int(row['fill_qty']):6d} @ {row['fill_price']:.3f} → pos={int(row['position']):7d}")

print("\n" + "=" * 100)
print(f"\nSUMMARY:")
print(f"  Total EOD trades (14:55+): {total_eod_trades}")

if total_eod_trades == 0:
    print("\n  ⚠️  NO EOD FLATTEN TRADES FOUND")
    print("  This means positions are NOT being flattened at end of day!")
else:
    print(f"\n  ✓ EOD flatten trades executing across securities")
