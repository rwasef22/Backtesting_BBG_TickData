"""
Generate inventory and P&L plots for all securities from CSV files.
"""
import pandas as pd
import matplotlib.pyplot as plt
from glob import glob
import os

# Find all trade timeseries CSVs
csv_files = glob('output/*_trades_timeseries.csv')

for csv_file in sorted(csv_files):
    security = os.path.basename(csv_file).replace('_trades_timeseries.csv', '')
    
    print(f"Generating plot for {security.upper()}...")
    
    try:
        df = pd.read_csv(csv_file)
        
        if df.empty:
            print(f"  Skipping {security} - no data")
            continue
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
        
        # Plot 1: Position over time
        ax1.plot(df['timestamp'], df['position'], linewidth=0.8, color='blue')
        ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        ax1.set_ylabel('Position (shares)', fontsize=11)
        ax1.set_title(f'{security.upper()} - Inventory Position', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Cumulative P&L over time
        ax2.plot(df['timestamp'], df['pnl'], linewidth=0.8, color='green')
        ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        ax2.set_xlabel('Date', fontsize=11)
        ax2.set_ylabel('Cumulative P&L ($)', fontsize=11)
        ax2.set_title(f'{security.upper()} - Cumulative P&L', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Format final P&L
        final_pnl = df['pnl'].iloc[-1]
        color = 'green' if final_pnl >= 0 else 'red'
        ax2.text(0.02, 0.98, f'Final P&L: ${final_pnl:,.2f}', 
                transform=ax2.transAxes, fontsize=11, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor=color, alpha=0.2))
        
        plt.tight_layout()
        
        # Save plot
        output_path = f'output/{security}_inventory_pnl.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  Saved: {output_path}")
        
    except Exception as e:
        print(f"  Error processing {security}: {e}")
        continue

print("\nAll plots generated successfully!")
