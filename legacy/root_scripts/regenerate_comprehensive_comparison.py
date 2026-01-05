"""
Regenerate comprehensive comparison plot with V2.1 data
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime

print("="*60)
print("REGENERATING COMPREHENSIVE COMPARISON PLOT")
print("="*60)

# Load data
df = pd.read_csv('output/comprehensive_sweep/comprehensive_results.csv')
strategies = sorted(df['strategy'].unique())
print(f"\nStrategies: {strategies}")
print(f"V2.1 rows: {len(df[df['strategy']=='v2_1'])}")

# Colors and markers
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

def format_name(s):
    return s.replace('_', '.').upper()

# Create figure
fig = plt.figure(figsize=(20, 16))
gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)

strategy_data = {s: df[df['strategy'] == s].sort_values('interval_sec') for s in strategies}
intervals = sorted(df['interval_sec'].unique())
x_positions = {interval: i for i, interval in enumerate(intervals)}
x = np.arange(len(intervals))
width = 0.8 / len(strategies)

print(f"\nGenerating {len(strategies)} strategy comparison...")

# 1. Total P&L
ax1 = fig.add_subplot(gs[0, 0])
for i, strategy in enumerate(strategies):
    data = strategy_data[strategy]
    offset = width * (i - (len(strategies) - 1) / 2)
    x_vals = [x_positions[interval] + offset for interval in data['interval_sec']]
    ax1.bar(x_vals, data['total_pnl'], width,
           label=format_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
    data = strategy_data[strategy]
    offset = width * (i - (len(strategies) - 1) / 2)
    x_vals = [x_positions[interval] + offset for interval in data['interval_sec']]
    ax2.bar(x_vals, data['total_trades'], width,
           label=format_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
            label=format_name(strategy))
ax3.set_xlabel('Interval (sec)', fontweight='bold')
ax3.set_ylabel('Sharpe Ratio', fontweight='bold')
ax3.set_title('Sharpe Ratio', fontweight='bold', fontsize=12)
ax3.legend()
ax3.grid(alpha=0.3)

# 4. Max Drawdown %
ax4 = fig.add_subplot(gs[1, 0])
for i, strategy in enumerate(strategies):
    data = strategy_data[strategy]
    offset = width * (i - (len(strategies) - 1) / 2)
    x_vals = [x_positions[interval] + offset for interval in data['interval_sec']]
    ax4.bar(x_vals, data['max_drawdown_pct'], width,
           label=format_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
            label=format_name(strategy))
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
            label=format_name(strategy))
ax6.set_xlabel('Interval (sec)', fontweight='bold')
ax6.set_ylabel('Profit Factor', fontweight='bold')
ax6.set_title('Profit Factor', fontweight='bold', fontsize=12)
ax6.legend()
ax6.grid(alpha=0.3)
ax6.axhline(1.0, color='black', linestyle='--', linewidth=0.5)

# 7. Avg P&L per Trade
ax7 = fig.add_subplot(gs[2, 0])
for i, strategy in enumerate(strategies):
    data = strategy_data[strategy]
    offset = width * (i - (len(strategies) - 1) / 2)
    x_vals = [x_positions[interval] + offset for interval in data['interval_sec']]
    ax7.bar(x_vals, data['avg_pnl_per_trade'], width,
           label=format_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
            label=format_name(strategy))
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
            label=format_name(strategy))
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
                alpha=0.7, edgecolors='black', linewidths=2, label=format_name(strategy))
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
                alpha=0.7, edgecolors='black', linewidths=2, label=format_name(strategy))
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
                alpha=0.7, edgecolors='black', linewidths=2, label=format_name(strategy))
ax12.set_xlabel('Win Rate (%)', fontweight='bold')
ax12.set_ylabel('Profit Factor', fontweight='bold')
ax12.set_title('Win Rate vs Profit Factor', fontweight='bold', fontsize=12)
ax12.legend()
ax12.grid(alpha=0.3)
ax12.axhline(1.0, color='black', linestyle='--', linewidth=0.5)

# Title
fig.suptitle(f"Comprehensive Strategy Comparison: {', '.join([format_name(s) for s in strategies])}", 
             fontsize=16, fontweight='bold', y=0.995)

# Save
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_path = Path('output/comprehensive_sweep')
new_filename = output_path / f'comprehensive_comparison_NEW_{timestamp}.png'
old_filename = output_path / 'comprehensive_comparison.png'

plt.savefig(new_filename, dpi=150, bbox_inches='tight')
plt.savefig(old_filename, dpi=150, bbox_inches='tight')
plt.close()

print(f"\n✓ Saved NEW plot: {new_filename.name}")
print(f"✓ Overwrote old plot: {old_filename.name}")
print("\n" + "="*60)
print("COMPLETE!")
print("="*60)
print(f"\nThe plot now includes: {', '.join([format_name(s) for s in strategies])}")
print(f"\nLook for: {new_filename.name}")
