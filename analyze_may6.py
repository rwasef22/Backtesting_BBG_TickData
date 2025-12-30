import pandas as pd
import glob
import os

# Load all V1 60s trade files
trade_files = glob.glob('output/comprehensive_sweep/v1_60s/*_trades.csv')

all_trades = []
for f in trade_files:
    security = os.path.basename(f).replace('_trades.csv', '')
    df = pd.read_csv(f)
    df['security'] = security
    all_trades.append(df)

# Combine and sort by timestamp
combined = pd.concat(all_trades, ignore_index=True)
combined['timestamp'] = pd.to_datetime(combined['timestamp'])
combined = combined.sort_values('timestamp')
combined['date'] = combined['timestamp'].dt.date

# Round PNL values
combined['realized_pnl'] = combined['realized_pnl'].round(0)

print("=" * 80)
print("ANALYZING MAY 6, 2025 - THE WORST TRADING DAY")
print("=" * 80)

# Filter for May 6, 2025
may6_trades = combined[combined['date'] == pd.to_datetime('2025-05-06').date()]

print(f"\nTotal trades on May 6: {len(may6_trades)}")
print(f"Total PNL on May 6: {round(may6_trades['realized_pnl'].sum())}")

# Group by security
security_pnl = may6_trades.groupby('security')['realized_pnl'].agg(['sum', 'count']).sort_values('sum')
print("\nPNL by Security on May 6, 2025:")
print(security_pnl.to_string())

# Find the worst trades on that day
worst_trades = may6_trades.nsmallest(20, 'realized_pnl')
print("\n20 Worst Individual Trades on May 6:")
cols_to_show = ['timestamp', 'security', 'side', 'realized_pnl', 'position']
if 'price' in worst_trades.columns:
    cols_to_show.insert(3, 'price')
print(worst_trades[cols_to_show].to_string())

# Check if there's a specific time period that was bad
print("\n\nHourly breakdown on May 6:")
may6_trades['hour'] = may6_trades['timestamp'].dt.hour
hourly_pnl = may6_trades.groupby('hour')['realized_pnl'].agg(['sum', 'count'])
print(hourly_pnl.to_string())

# Look at a few days before and after
print("\n\nDaily PNL from May 1-10:")
early_may = combined[(combined['date'] >= pd.to_datetime('2025-05-01').date()) & 
                      (combined['date'] <= pd.to_datetime('2025-05-10').date())]
daily_summary = early_may.groupby('date')['realized_pnl'].agg(['sum', 'count'])
daily_summary.columns = ['PNL', 'Trades']
daily_summary['Cumulative_PNL'] = daily_summary['PNL'].cumsum()
print(daily_summary.to_string())

# Check what was happening with specific securities
print("\n\nDetailed look at worst performing security on May 6:")
worst_security = security_pnl.index[0]
print(f"\nSecurity: {worst_security}")
worst_sec_trades = may6_trades[may6_trades['security'] == worst_security].sort_values('timestamp')
print(f"Number of trades: {len(worst_sec_trades)}")
print(f"Total PNL: {round(worst_sec_trades['realized_pnl'].sum())}")

# Show sample of trades
print("\nFirst 10 trades:")
print(worst_sec_trades.head(10)[cols_to_show].to_string())
print("\nLast 10 trades:")
print(worst_sec_trades.tail(10)[cols_to_show].to_string())
