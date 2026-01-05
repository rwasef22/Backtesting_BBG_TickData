"""Check that V2 backtest has no fills outside allowed trading windows."""
import pandas as pd
from pathlib import Path
from datetime import time

# Load all V2 trade files
output_dir = Path('output')
trade_files = list(output_dir.glob('*_trades_timeseries.csv'))

print(f"Checking {len(trade_files)} securities for invalid fill times...\n")
print("=" * 80)

issues_found = False

for trade_file in sorted(trade_files):
    security = trade_file.stem.replace('_trades_timeseries', '').upper()
    
    df = pd.read_csv(trade_file)
    if df.empty:
        continue
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['time'] = df['timestamp'].dt.time
    df['date'] = df['timestamp'].dt.date
    
    # Define time windows
    opening_start = time(9, 30, 0)
    trading_start = time(10, 5, 0)  # After silent period
    closing_start = time(14, 45, 0)
    eod_flatten_time = time(14, 55, 0)
    
    # Check for fills before 10:05 (should be none - opening auction and silent period)
    before_trading = df[df['time'] < trading_start]
    
    # Check for fills between 14:45 and 14:55 (closing auction - should be none)
    closing_auction = df[(df['time'] >= closing_start) & (df['time'] < eod_flatten_time)]
    
    # Check for fills at/after 14:55 but not on position flattening
    # EOD flatten should close position to 0
    eod_fills = df[df['time'] >= eod_flatten_time].copy()
    
    # Group by date to check if EOD fills close to 0
    if len(eod_fills) > 0:
        for date, group in eod_fills.groupby('date'):
            last_pos = group['position'].iloc[-1]
            if last_pos != 0:
                print(f"⚠️  {security} - {date}: EOD position not flat: {last_pos}")
                issues_found = True
    
    if len(before_trading) > 0:
        print(f"❌ {security}: {len(before_trading)} fills BEFORE 10:05")
        print(f"   Times: {before_trading['time'].unique()}")
        print(f"   Sample:\n{before_trading[['timestamp', 'side', 'fill_qty', 'position']].head()}\n")
        issues_found = True
    
    if len(closing_auction) > 0:
        print(f"❌ {security}: {len(closing_auction)} fills during CLOSING AUCTION (14:45-14:55)")
        print(f"   Times: {closing_auction['time'].unique()}")
        print(f"   Sample:\n{closing_auction[['timestamp', 'side', 'fill_qty', 'position']].head()}\n")
        issues_found = True

print("=" * 80)

if not issues_found:
    print("✅ ALL CHECKS PASSED!")
    print("\nNo fills found:")
    print("  • Before 10:05 (opening auction + silent period)")
    print("  • During 14:45-14:55 (closing auction)")
    print("  • EOD positions all flat (0)")
else:
    print("❌ ISSUES FOUND - See details above")
