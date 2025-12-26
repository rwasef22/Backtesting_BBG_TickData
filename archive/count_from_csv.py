import pandas as pd

print("Reading ADNOCGAS trades timeseries...")
df = pd.read_csv('output/adnocgas_trades_timeseries.csv')

# Extract dates from timestamp
df['date'] = pd.to_datetime(df['timestamp']).dt.date

# Count unique trading days
unique_dates = df['date'].unique()
n_days = len(unique_dates)

print(f"\n{'='*60}")
print(f"ADNOCGAS Trading Days (from backtest output)")
print(f"{'='*60}")
print(f"Unique trading dates: {n_days}")
print(f"\nDate range:")
print(f"  First date: {min(unique_dates)}")
print(f"  Last date: {max(unique_dates)}")

print(f"\nAll {n_days} trading dates:")
for date in sorted(unique_dates):
    print(f"  {date}")
