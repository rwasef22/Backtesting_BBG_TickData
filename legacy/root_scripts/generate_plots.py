"""
Generate comparison tables and plots from completed comprehensive sweep results
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def format_strategy_name(strategy: str) -> str:
    """Format strategy name for display (e.g., 'v2_1' -> 'V2.1')"""
    return strategy.replace('_', '.').upper()

# Load existing results
output_dir = Path("output/comprehensive_sweep")
metrics_df = pd.read_csv(output_dir / "comprehensive_results.csv")

print("=== Loaded Comprehensive Results ===")
print(f"Strategies: {sorted(metrics_df['strategy'].unique())}")
print(f"Intervals: {sorted(metrics_df['interval_sec'].unique())}")
print()

# Create comparison table
available_strategies = sorted(metrics_df['strategy'].unique())

if len(available_strategies) >= 2:
    intervals = sorted(metrics_df['interval_sec'].unique())
    comparison_data = {'Interval (sec)': intervals}
    
    for strategy in available_strategies:
        strat_df = metrics_df[metrics_df['strategy'] == strategy].sort_values('interval_sec')
        
        # Create a complete series aligned with all intervals
        pnl_series = pd.Series(index=intervals, dtype=float)
        trades_series = pd.Series(index=intervals, dtype=int)
        sharpe_series = pd.Series(index=intervals, dtype=float)
        dd_series = pd.Series(index=intervals, dtype=float)
        win_series = pd.Series(index=intervals, dtype=float)
        
        # Fill in available data
        for _, row in strat_df.iterrows():
            interval = row['interval_sec']
            pnl_series[interval] = row['total_pnl']
            trades_series[interval] = row['total_trades']
            sharpe_series[interval] = row['sharpe_ratio']
            dd_series[interval] = row['max_drawdown_pct']
            win_series[interval] = row['win_rate']
        
        comparison_data[f'{format_strategy_name(strategy)} P&L'] = pnl_series.values
        comparison_data[f'{format_strategy_name(strategy)} Trades'] = trades_series.values
        comparison_data[f'{format_strategy_name(strategy)} Sharpe'] = sharpe_series.values
        comparison_data[f'{format_strategy_name(strategy)} Max DD%'] = dd_series.values
        comparison_data[f'{format_strategy_name(strategy)} Win%'] = win_series.values
    
    comparison = pd.DataFrame(comparison_data)
    
    print("=== Strategy Comparison ===")
    print(comparison.to_string(index=False))
    print()
    
    comparison.to_csv(output_dir / "comparison_table.csv", index=False)
    print(f"✓ Saved comparison_table.csv")
    print()

# Generate plots
print("Generating plots...")

strategies = sorted(metrics_df['strategy'].unique())
strategy_colors = {
    'v1': 'steelblue',
    'v2': 'coral',
    'v2_1': 'mediumorchid',
    'v3': 'mediumseagreen'
}
strategy_markers = {
    'v1': 'o',
    'v2': 's',
    'v2_1': 'D',
    'v3': '^'
}

# Cumulative P&L by strategy
fig, ax = plt.subplots(figsize=(14, 8))

for strategy in strategies:
    strat_df = metrics_df[metrics_df['strategy'] == strategy].sort_values('interval_sec')
    ax.plot(strat_df['interval_sec'], strat_df['total_pnl'], 
           marker=strategy_markers.get(strategy, 'o'),
           color=strategy_colors.get(strategy, 'gray'),
           linewidth=2, markersize=10,
           label=format_strategy_name(strategy))

ax.set_xlabel('Refill Interval (seconds)', fontweight='bold', fontsize=12)
ax.set_ylabel('Total P&L (AED)', fontweight='bold', fontsize=12)
ax.set_title('Cumulative P&L by Strategy and Interval', fontweight='bold', fontsize=14)
ax.legend(fontsize=11)
ax.grid(alpha=0.3)
ax.axhline(0, color='black', linestyle='--', linewidth=0.8)

plt.tight_layout()
plt.savefig(output_dir / 'cumulative_pnl_by_strategy.png', dpi=150, bbox_inches='tight')
plt.close()

print(f"✓ Saved cumulative_pnl_by_strategy.png")

# Comprehensive comparison plot (4x3 grid)
fig = plt.figure(figsize=(20, 16))
gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)

strategy_data = {s: metrics_df[metrics_df['strategy'] == s].sort_values('interval_sec') 
                 for s in strategies}

intervals = sorted(metrics_df['interval_sec'].unique())
x = np.arange(len(intervals))
width = 0.8 / len(strategies)

# 1. Total P&L
ax1 = fig.add_subplot(gs[0, 0])
for i, strategy in enumerate(strategies):
    offset = width * (i - (len(strategies) - 1) / 2)
    ax1.bar(x + offset, strategy_data[strategy]['total_pnl'], width, 
           label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
ax1.set_xlabel('Interval (sec)', fontweight='bold')
ax1.set_ylabel('P&L (AED)', fontweight='bold')
ax1.set_title('Total P&L', fontweight='bold', fontsize=12)
ax1.set_xticks(x)
ax1.set_xticklabels(intervals)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)
ax1.axhline(0, color='black', linestyle='--', linewidth=0.5)

# 2. Total Trades
ax2 = fig.add_subplot(gs[0, 1])
for i, strategy in enumerate(strategies):
    offset = width * (i - (len(strategies) - 1) / 2)
    ax2.bar(x + offset, strategy_data[strategy]['total_trades'], width, 
           label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
ax2.set_xlabel('Interval (sec)', fontweight='bold')
ax2.set_ylabel('Number of Trades', fontweight='bold')
ax2.set_title('Total Trades', fontweight='bold', fontsize=12)
ax2.set_xticks(x)
ax2.set_xticklabels(intervals)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

# 3. Sharpe Ratio
ax3 = fig.add_subplot(gs[0, 2])
for strategy in strategies:
    ax3.plot(strategy_data[strategy]['interval_sec'], strategy_data[strategy]['sharpe_ratio'],
            marker=strategy_markers[strategy], color=strategy_colors[strategy], linewidth=2, markersize=10,
            label=format_strategy_name(strategy))
ax3.set_xlabel('Interval (sec)', fontweight='bold')
ax3.set_ylabel('Sharpe Ratio', fontweight='bold')
ax3.set_title('Sharpe Ratio', fontweight='bold', fontsize=12)
ax3.legend()
ax3.grid(alpha=0.3)

# 4. Max Drawdown %
ax4 = fig.add_subplot(gs[1, 0])
for i, strategy in enumerate(strategies):
    offset = width * (i - (len(strategies) - 1) / 2)
    ax4.bar(x + offset, strategy_data[strategy]['max_drawdown_pct'], width, 
           label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
ax4.set_xlabel('Interval (sec)', fontweight='bold')
ax4.set_ylabel('Max Drawdown (%)', fontweight='bold')
ax4.set_title('Maximum Drawdown %', fontweight='bold', fontsize=12)
ax4.set_xticks(x)
ax4.set_xticklabels(intervals)
ax4.legend()
ax4.grid(axis='y', alpha=0.3)
ax4.axhline(0, color='black', linestyle='--', linewidth=0.5)

# 5. Win Rate
ax5 = fig.add_subplot(gs[1, 1])
for strategy in strategies:
    ax5.plot(strategy_data[strategy]['interval_sec'], strategy_data[strategy]['win_rate'],
            marker=strategy_markers[strategy], color=strategy_colors[strategy], linewidth=2, markersize=10,
            label=format_strategy_name(strategy))
ax5.set_xlabel('Interval (sec)', fontweight='bold')
ax5.set_ylabel('Win Rate (%)', fontweight='bold')
ax5.set_title('Win Rate', fontweight='bold', fontsize=12)
ax5.legend()
ax5.grid(alpha=0.3)

# 6. Profit Factor
ax6 = fig.add_subplot(gs[1, 2])
for strategy in strategies:
    ax6.plot(strategy_data[strategy]['interval_sec'], strategy_data[strategy]['profit_factor'],
            marker=strategy_markers[strategy], color=strategy_colors[strategy], linewidth=2, markersize=10,
            label=format_strategy_name(strategy))
ax6.set_xlabel('Interval (sec)', fontweight='bold')
ax6.set_ylabel('Profit Factor', fontweight='bold')
ax6.set_title('Profit Factor', fontweight='bold', fontsize=12)
ax6.legend()
ax6.grid(alpha=0.3)
ax6.axhline(1.0, color='black', linestyle='--', linewidth=0.5)

# 7. Avg P&L per Trade
ax7 = fig.add_subplot(gs[2, 0])
for i, strategy in enumerate(strategies):
    offset = width * (i - (len(strategies) - 1) / 2)
    ax7.bar(x + offset, strategy_data[strategy]['avg_pnl_per_trade'], width, 
           label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
ax7.set_xlabel('Interval (sec)', fontweight='bold')
ax7.set_ylabel('Avg P&L per Trade (AED)', fontweight='bold')
ax7.set_title('Average P&L per Trade', fontweight='bold', fontsize=12)
ax7.set_xticks(x)
ax7.set_xticklabels(intervals)
ax7.legend()
ax7.grid(axis='y', alpha=0.3)
ax7.axhline(0, color='black', linestyle='--', linewidth=0.5)

# 8. Calmar Ratio
ax8 = fig.add_subplot(gs[2, 1])
for strategy in strategies:
    ax8.plot(strategy_data[strategy]['interval_sec'], strategy_data[strategy]['calmar_ratio'],
            marker=strategy_markers[strategy], color=strategy_colors[strategy], linewidth=2, markersize=10,
            label=format_strategy_name(strategy))
ax8.set_xlabel('Interval (sec)', fontweight='bold')
ax8.set_ylabel('Calmar Ratio', fontweight='bold')
ax8.set_title('Calmar Ratio', fontweight='bold', fontsize=12)
ax8.legend()
ax8.grid(alpha=0.3)

# 9. Trades per Day
ax9 = fig.add_subplot(gs[2, 2])
for strategy in strategies:
    ax9.plot(strategy_data[strategy]['interval_sec'], strategy_data[strategy]['trades_per_day'],
            marker=strategy_markers[strategy], color=strategy_colors[strategy], linewidth=2, markersize=10,
            label=format_strategy_name(strategy))
ax9.set_xlabel('Interval (sec)', fontweight='bold')
ax9.set_ylabel('Trades per Day', fontweight='bold')
ax9.set_title('Trading Frequency', fontweight='bold', fontsize=12)
ax9.legend()
ax9.grid(alpha=0.3)

# 10. P&L vs Sharpe scatter
ax10 = fig.add_subplot(gs[3, 0])
for strategy in strategies:
    ax10.scatter(strategy_data[strategy]['sharpe_ratio'], strategy_data[strategy]['total_pnl'],
                s=200, marker=strategy_markers[strategy], color=strategy_colors[strategy], 
                alpha=0.7, edgecolors='black', linewidths=2, label=format_strategy_name(strategy))
ax10.set_xlabel('Sharpe Ratio', fontweight='bold')
ax10.set_ylabel('Total P&L (AED)', fontweight='bold')
ax10.set_title('P&L vs Risk-Adjusted Returns', fontweight='bold', fontsize=12)
ax10.legend()
ax10.grid(alpha=0.3)

# 11. Max DD vs P&L scatter
ax11 = fig.add_subplot(gs[3, 1])
for strategy in strategies:
    ax11.scatter(strategy_data[strategy]['max_drawdown_pct'], strategy_data[strategy]['total_pnl'],
                s=200, marker=strategy_markers[strategy], color=strategy_colors[strategy],
                alpha=0.7, edgecolors='black', linewidths=2, label=format_strategy_name(strategy))
ax11.set_xlabel('Max Drawdown (%)', fontweight='bold')
ax11.set_ylabel('Total P&L (AED)', fontweight='bold')
ax11.set_title('P&L vs Maximum Drawdown', fontweight='bold', fontsize=12)
ax11.legend()
ax11.grid(alpha=0.3)

# 12. Win Rate vs Profit Factor scatter
ax12 = fig.add_subplot(gs[3, 2])
for strategy in strategies:
    ax12.scatter(strategy_data[strategy]['win_rate'], strategy_data[strategy]['profit_factor'],
                s=200, marker=strategy_markers[strategy], color=strategy_colors[strategy],
                alpha=0.7, edgecolors='black', linewidths=2, label=format_strategy_name(strategy))
ax12.set_xlabel('Win Rate (%)', fontweight='bold')
ax12.set_ylabel('Profit Factor', fontweight='bold')
ax12.set_title('Win Rate vs Profit Factor', fontweight='bold', fontsize=12)
ax12.legend()
ax12.grid(alpha=0.3)
ax12.axhline(1.0, color='black', linestyle='--', linewidth=0.5)

fig.suptitle(f"Comprehensive Strategy Comparison: {', '.join([format_strategy_name(s) for s in strategies])}", 
             fontsize=16, fontweight='bold', y=0.995)

plt.savefig(output_dir / 'comprehensive_comparison.png', dpi=150, bbox_inches='tight')
plt.close()

print(f"✓ Saved comprehensive_comparison.png")
print()
print("=== All plots and tables generated successfully ===")
