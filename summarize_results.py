"""
Summarize backtest performance statistics from all CSV files.
"""
import pandas as pd
import os
from glob import glob

# Find all trade timeseries CSVs
csv_files = glob('output/*_trades_timeseries.csv')

results = []

for csv_file in sorted(csv_files):
    security = os.path.basename(csv_file).replace('_trades_timeseries.csv', '').upper()
    
    try:
        df = pd.read_csv(csv_file)
        
        if df.empty:
            continue
        
        # Calculate statistics
        num_trades = len(df)
        final_pnl = df['pnl'].iloc[-1] if 'pnl' in df.columns else 0
        final_position = df['position'].iloc[-1] if 'position' in df.columns else 0
        
        # Trading days
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        trading_days = df['date'].nunique()
        
        # Buy/Sell split
        buys = len(df[df['side'] == 'buy'])
        sells = len(df[df['side'] == 'sell'])
        
        # Average trade size
        avg_qty = df['fill_qty'].mean()
        
        # Trade value
        total_value = (df['fill_qty'] * df['fill_price']).sum()
        
        results.append({
            'Security': security,
            'Trades': num_trades,
            'Trading Days': trading_days,
            'Buys': buys,
            'Sells': sells,
            'Avg Qty': int(avg_qty),
            'Total Value ($)': int(total_value),
            'Final P&L ($)': round(final_pnl, 2),
            'Final Position': int(final_position)
        })
        
    except Exception as e:
        print(f"Error processing {security}: {e}")
        continue

# Create DataFrame and display
summary_df = pd.DataFrame(results)

# Sort by P&L descending
summary_df = summary_df.sort_values('Final P&L ($)', ascending=False)

# Add totals row
totals = {
    'Security': 'TOTAL',
    'Trades': summary_df['Trades'].sum(),
    'Trading Days': '-',
    'Buys': summary_df['Buys'].sum(),
    'Sells': summary_df['Sells'].sum(),
    'Avg Qty': '-',
    'Total Value ($)': summary_df['Total Value ($)'].sum(),
    'Final P&L ($)': summary_df['Final P&L ($)'].sum(),
    'Final Position': summary_df['Final Position'].sum()
}

summary_df = pd.concat([summary_df, pd.DataFrame([totals])], ignore_index=True)

print("\n" + "="*120)
print("BACKTEST PERFORMANCE SUMMARY")
print("="*120)
print(summary_df.to_string(index=False))
print("="*120)

# Save to file
summary_df.to_csv('output/performance_summary.csv', index=False)
print("\nSummary saved to output/performance_summary.csv")
