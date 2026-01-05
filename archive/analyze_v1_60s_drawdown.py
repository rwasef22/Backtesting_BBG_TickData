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

# Calculate cumulative PNL
combined['realized_pnl'] = combined['realized_pnl'].round(0)
combined['cumulative_pnl'] = combined['realized_pnl'].cumsum()
combined['cumulative_drawdown'] = combined['cumulative_pnl'] - combined['cumulative_pnl'].cummax()

# Find the maximum drawdown point
max_dd_idx = combined['cumulative_drawdown'].idxmin()
max_dd_row = combined.loc[max_dd_idx]

print(f'Maximum Drawdown: {round(max_dd_row["cumulative_drawdown"])}')
print(f'Occurred at: {max_dd_row["timestamp"]}')
print(f'Security: {max_dd_row["security"]}')
print(f'Cumulative PNL at that point: {round(max_dd_row["cumulative_pnl"])}')
print(f'Peak PNL before drawdown: {round(combined.loc[:max_dd_idx, "cumulative_pnl"].max())}')
print(f'Trade index: {max_dd_idx} out of {len(combined)} total trades')
print()

# Show context around the drawdown
print('Trades around maximum drawdown:')
start_idx = max(0, max_dd_idx - 10)
end_idx = min(len(combined), max_dd_idx + 10)
cols_to_show = [c for c in ['timestamp', 'security', 'side', 'price', 'realized_pnl', 'cumulative_pnl', 'cumulative_drawdown'] if c in combined.columns]
print(combined.iloc[start_idx:end_idx+1][cols_to_show].to_string())

print("\n\nLet's look at daily PNL to identify the problematic period:")
combined['date'] = combined['timestamp'].dt.date
daily_pnl = combined.groupby('date')['realized_pnl'].sum().reset_index()
daily_pnl['cumulative_pnl'] = daily_pnl['realized_pnl'].cumsum()
daily_pnl['cumulative_dd'] = daily_pnl['cumulative_pnl'] - daily_pnl['cumulative_pnl'].cummax()

# Find worst days
worst_days = daily_pnl.nsmallest(10, 'realized_pnl')
print("\n10 Worst Trading Days:")
print(worst_days.to_string())

# Show period around max drawdown date
max_dd_date = max_dd_row['timestamp'].date()
print(f"\n\nDaily PNL around max drawdown date ({max_dd_date}):")
daily_pnl['realized_pnl'] = daily_pnl['realized_pnl'].round(0)
daily_pnl['cumulative_pnl'] = daily_pnl['cumulative_pnl'].round(0)
daily_pnl['cumulative_dd'] = daily_pnl['cumulative_dd'].round(0)
date_window = daily_pnl[
    (daily_pnl['date'] >= pd.Timestamp(max_dd_date) - pd.Timedelta(days=5)) & 
    (daily_pnl['date'] <= pd.Timestamp(max_dd_date) + pd.Timedelta(days=5))
]
print(date_window.to_string())
