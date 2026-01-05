import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

print("Starting plot generation...")
print(f"Timestamp: {datetime.now()}")

# Load data
df = pd.read_csv('output/comprehensive_sweep/comprehensive_results.csv')
print(f"\nStrategies in CSV: {sorted(df['strategy'].unique())}")
print(f"Total rows: {len(df)}")

strategies = sorted(df['strategy'].unique())

# Simple cumulative P&L plot
fig, ax = plt.subplots(figsize=(14, 8))

colors = {'v1': 'steelblue', 'v2': 'coral', 'v2_1': 'mediumorchid', 'v3': 'mediumseagreen'}
markers = {'v1': 'o', 'v2': 's', 'v2_1': 'D', 'v3': '^'}

for strategy in strategies:
    sdf = df[df['strategy'] == strategy].sort_values('interval_sec')
    label = strategy.replace('_', '.').upper()
    ax.plot(sdf['interval_sec'], sdf['total_pnl'],
           marker=markers.get(strategy, 'o'),
           color=colors.get(strategy, 'gray'),
           linewidth=2, markersize=10,
           label=label)
    print(f"Plotted {label}: {len(sdf)} points")

ax.set_xlabel('Refill Interval (seconds)', fontweight='bold', fontsize=12)
ax.set_ylabel('Total P&L (AED)', fontweight='bold', fontsize=12)
ax.set_title('V2 vs V2.1: Cumulative P&L by Interval', fontweight='bold', fontsize=14)
ax.legend(fontsize=11)
ax.grid(alpha=0.3)
ax.axhline(0, color='black', linestyle='--', linewidth=0.8)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'output/comprehensive_sweep/cumulative_pnl_LATEST_{timestamp}.png'
plt.tight_layout()
plt.savefig(filename, dpi=150, bbox_inches='tight')
plt.close()

print(f"\n✓ Saved {filename}")
print("\nDONE! Check the file with _LATEST_ in the name for the updated plot.")
