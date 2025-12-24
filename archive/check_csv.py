import pandas as pd

csv = pd.read_csv('output/emaar_trades_timeseries.csv')
print(f"Total trades: {len(csv)}")
print(f"First trade: {csv['timestamp'].iloc[0]}")
print(f"Last trade: {csv['timestamp'].iloc[-1]}")

dates = pd.to_datetime(csv['timestamp']).dt.date.unique()
print(f"Unique trading dates: {len(dates)}")
print(f"Date range: {dates.min()} to {dates.max()}")
