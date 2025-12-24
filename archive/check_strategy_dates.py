"""Check which dates the strategy actually traded on"""
import pandas as pd
from datetime import datetime

# Read the CSV output
df = pd.read_csv('output/emaar_trades_timeseries.csv')

# Parse timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['date'] = df['timestamp'].dt.date

# Get unique trading dates
strategy_dates = sorted(df['date'].unique())

print(f"Strategy traded on {len(strategy_dates)} unique dates:")
print("\nFirst 10 dates:")
for date in strategy_dates[:10]:
    print(f"  {date}")
    
print("\nLast 10 dates:")
for date in strategy_dates[-10:]:
    print(f"  {date}")

# Count trades per date
trades_per_date = df.groupby('date').size()
print(f"\nTrades per date statistics:")
print(f"  Mean: {trades_per_date.mean():.1f}")
print(f"  Min: {trades_per_date.min()}")
print(f"  Max: {trades_per_date.max()}")
print(f"\nDates with most trades:")
print(trades_per_date.nlargest(5))
