"""
Manually regenerate comparison plots from comprehensive_results.csv
This will create NEW plot files with V2.1 data included
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime

print("="*60)
print("REGENERATING PLOTS WITH V2.1 DATA")
print("="*60)

# Load data
csv_path = Path('output/comprehensive_sweep/comprehensive_results.csv')
print(f"\nReading: {csv_path}")
df = pd.read_csv(csv_path)

# Check strategies
strategies = sorted(df['strategy'].unique())
print(f"\nStrategies found: {strategies}")
print(f"Total rows: {len(df)}")

# Show V2.1 data
v21 = df[df['strategy'] == 'v2_1']
print(f"\nV2.1 rows: {len(v21)}")
if len(v21) > 0:
    print("V2.1 data:")
    print(v21[['strategy', 'interval_sec', 'total_pnl', 'total_trades']])

print("\n" + "="*60)
print("GENERATING CUMULATIVE P&L PLOT")
print("="*60)

# Plot settings
colors = {
    'v1': 'steelblue',
    'v2': 'coral',
    'v2_1': 'mediumorchid',
    'v3': 'mediumseagreen'
}
markers = {
    'v1': 'o',
    'v2': 's',
    'v2_1': 'D',
    'v3': '^'
}

def format_name(s):
    return s.replace('_', '.').upper()

# Create cumulative P&L plot
fig, ax = plt.subplots(figsize=(14, 8))

for strategy in strategies:
    sdf = df[df['strategy'] == strategy].sort_values('interval_sec')
    label = format_name(strategy)
    color = colors.get(strategy, 'gray')
    marker = markers.get(strategy, 'o')
    
    ax.plot(sdf['interval_sec'], sdf['total_pnl'],
           marker=marker, color=color,
           linewidth=2, markersize=10,
           label=label)
    print(f"✓ Plotted {label}: {len(sdf)} data points")

ax.set_xlabel('Refill Interval (seconds)', fontweight='bold', fontsize=12)
ax.set_ylabel('Total P&L (AED)', fontweight='bold', fontsize=12)

# Title based on what strategies we have
if 'v2_1' in strategies and 'v2' in strategies:
    title = 'V2 vs V2.1: Cumulative P&L Comparison'
else:
    title = 'Cumulative P&L by Strategy and Interval'
    
ax.set_title(title, fontweight='bold', fontsize=14)
ax.legend(fontsize=11)
ax.grid(alpha=0.3)
ax.axhline(0, color='black', linestyle='--', linewidth=0.8)

plt.tight_layout()

# Save with timestamp
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_path = Path('output/comprehensive_sweep')
new_filename = output_path / f'cumulative_pnl_by_strategy_NEW_{timestamp}.png'
old_filename = output_path / 'cumulative_pnl_by_strategy.png'

# Save both
plt.savefig(new_filename, dpi=150, bbox_inches='tight')
plt.savefig(old_filename, dpi=150, bbox_inches='tight')
plt.close()

print(f"\n✓ Saved NEW plot: {new_filename.name}")
print(f"✓ Overwrote old plot: {old_filename.name}")

print("\n" + "="*60)
print("COMPLETE!")
print("="*60)
print(f"\nThe plots now include: {', '.join([format_name(s) for s in strategies])}")
print(f"\nLook for the file: {new_filename.name}")
print("This is a BRAND NEW file with V2.1 data!")
