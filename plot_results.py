#!/usr/bin/env python3
"""
Generate plots from existing backtest CSV results
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_security_results(csv_file, output_dir='plots'):
    """Generate inventory and P&L plots for a single security"""
    # Extract security name from filename
    security = csv_file.stem.replace('_trades_timeseries', '').upper()
    
    # Read CSV
    df = pd.read_csv(csv_file)
    if len(df) == 0:
        print(f"No trades for {security}, skipping plot")
        return
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Plot 1: Inventory over time
    ax1.plot(df['timestamp'], df['position'], linewidth=0.8, color='blue')
    ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.5, alpha=0.5)
    ax1.set_title(f'{security} - Inventory Over Time', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Position (shares)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # Plot 2: Cumulative P&L over time
    ax2.plot(df['timestamp'], df['pnl'], linewidth=0.8, color='green' if df['pnl'].iloc[-1] >= 0 else 'red')
    ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5, alpha=0.5)
    ax2.set_title(f'{security} - Cumulative P&L Over Time', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('P&L (AED)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)
    
    # Add summary stats
    total_trades = len(df)
    final_pnl = df['pnl'].iloc[-1]
    final_position = df['position'].iloc[-1]
    max_position = df['position'].abs().max()
    
    stats_text = f'Trades: {total_trades:,} | Final P&L: {final_pnl:,.2f} AED | Max Pos: {max_position:,}'
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    
    # Save plot
    os.makedirs(output_dir, exist_ok=True)
    output_file = Path(output_dir) / f'{security.lower()}_plot.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✓ Generated plot for {security}: {output_file}")
    print(f"  {total_trades:,} trades | Final P&L: {final_pnl:,.2f} AED")

def main():
    output_dir = Path('output')
    plots_dir = Path('plots')
    
    # Find all CSV files
    csv_files = list(output_dir.glob('*_trades_timeseries.csv'))
    
    if not csv_files:
        print("No CSV files found in output directory")
        return
    
    print(f"\n{'='*70}")
    print(f"GENERATING PLOTS FROM CSV FILES")
    print(f"{'='*70}\n")
    
    for csv_file in sorted(csv_files):
        try:
            plot_security_results(csv_file, plots_dir)
        except Exception as e:
            security = csv_file.stem.replace('_trades_timeseries', '').upper()
            print(f"✗ Error plotting {security}: {e}")
    
    print(f"\n{'='*70}")
    print(f"Plots saved to: {plots_dir.absolute()}")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
