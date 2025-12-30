"""Compare V1 and V2 parameter sweep results.

This script loads the results from both v1 and v2 parameter sweeps,
creates comparison tables and plots showing:
- Trade count vs interval
- P&L vs interval
- Avg P&L per trade vs interval
- Direct comparison table
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np


def load_sweep_results(sweep_dir: Path, strategy_name: str) -> pd.DataFrame:
    """Load parameter sweep comparison results."""
    if strategy_name == 'v1':
        csv_path = sweep_dir / 'interval_comparison.csv'
    else:
        csv_path = sweep_dir / 'v2_interval_comparison.csv'
    
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find {csv_path}")
    
    df = pd.read_csv(csv_path)
    df['strategy'] = strategy_name
    return df


def create_comparison_table(v1_df: pd.DataFrame, v2_df: pd.DataFrame) -> pd.DataFrame:
    """Create side-by-side comparison table."""
    
    comparison = pd.DataFrame({
        'Interval (sec)': v1_df['refill_interval_sec'],
        'Interval (min)': v1_df['refill_interval_min'],
        
        # V1 metrics
        'V1 Trades': v1_df['total_trades'].astype(int),
        'V1 P&L (AED)': v1_df['total_pnl'].round(2),
        'V1 Avg P&L/Trade': v1_df['avg_pnl_per_trade'].round(2),
        
        # V2 metrics
        'V2 Trades': v2_df['total_trades'].astype(int),
        'V2 P&L (AED)': v2_df['total_pnl'].round(2),
        'V2 Avg P&L/Trade': v2_df['avg_pnl_per_trade'].round(2),
        
        # Differences
        'Trade Diff': (v2_df['total_trades'] - v1_df['total_trades']).astype(int),
        'P&L Diff (AED)': (v2_df['total_pnl'] - v1_df['total_pnl']).round(2),
        'Avg P&L Diff': (v2_df['avg_pnl_per_trade'] - v1_df['avg_pnl_per_trade']).round(2),
    })
    
    return comparison


def plot_comparison(v1_df: pd.DataFrame, v2_df: pd.DataFrame, output_path: Path):
    """Create comprehensive comparison plots."""
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('V1 Baseline vs V2 Price Follow: Parameter Sweep Comparison', 
                 fontsize=16, fontweight='bold')
    
    intervals = v1_df['refill_interval_sec']
    
    # Plot 1: Total Trades
    ax1 = axes[0, 0]
    width = 0.35
    x = np.arange(len(intervals))
    ax1.bar(x - width/2, v1_df['total_trades'], width, label='V1 Baseline', 
            color='steelblue', alpha=0.8, edgecolor='black')
    ax1.bar(x + width/2, v2_df['total_trades'], width, label='V2 Price Follow', 
            color='coral', alpha=0.8, edgecolor='black')
    ax1.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax1.set_ylabel('Total Trades', fontweight='bold')
    ax1.set_title('Total Trades vs Interval', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(intervals.astype(int))
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Plot 2: Total P&L
    ax2 = axes[0, 1]
    v1_colors = ['green' if x > 0 else 'red' for x in v1_df['total_pnl']]
    v2_colors = ['green' if x > 0 else 'red' for x in v2_df['total_pnl']]
    ax2.bar(x - width/2, v1_df['total_pnl'], width, label='V1 Baseline', 
            color=v1_colors, alpha=0.8, edgecolor='black')
    ax2.bar(x + width/2, v2_df['total_pnl'], width, label='V2 Price Follow', 
            color=v2_colors, alpha=0.8, edgecolor='black')
    ax2.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax2.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax2.set_title('Total P&L vs Interval', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(intervals.astype(int))
    ax2.legend()
    ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax2.grid(axis='y', alpha=0.3)
    
    # Plot 3: Average P&L per Trade
    ax3 = axes[0, 2]
    ax3.bar(x - width/2, v1_df['avg_pnl_per_trade'], width, label='V1 Baseline', 
            color='steelblue', alpha=0.8, edgecolor='black')
    ax3.bar(x + width/2, v2_df['avg_pnl_per_trade'], width, label='V2 Price Follow', 
            color='coral', alpha=0.8, edgecolor='black')
    ax3.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax3.set_ylabel('Avg P&L per Trade (AED)', fontweight='bold')
    ax3.set_title('Average P&L per Trade vs Interval', fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(intervals.astype(int))
    ax3.legend()
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax3.grid(axis='y', alpha=0.3)
    
    # Plot 4: Trade Count Difference (V2 - V1)
    ax4 = axes[1, 0]
    trade_diff = v2_df['total_trades'].values - v1_df['total_trades'].values
    colors = ['green' if x > 0 else 'red' for x in trade_diff]
    ax4.bar(intervals, trade_diff, color=colors, alpha=0.7, edgecolor='black')
    ax4.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax4.set_ylabel('Trade Difference (V2 - V1)', fontweight='bold')
    ax4.set_title('Trade Count Advantage', fontweight='bold')
    ax4.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax4.grid(axis='y', alpha=0.3)
    
    # Plot 5: P&L Difference (V2 - V1)
    ax5 = axes[1, 1]
    pnl_diff = v2_df['total_pnl'].values - v1_df['total_pnl'].values
    colors = ['green' if x > 0 else 'red' for x in pnl_diff]
    ax5.bar(intervals, pnl_diff, color=colors, alpha=0.7, edgecolor='black')
    ax5.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax5.set_ylabel('P&L Difference (V2 - V1, AED)', fontweight='bold')
    ax5.set_title('P&L Advantage', fontweight='bold')
    ax5.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax5.grid(axis='y', alpha=0.3)
    
    # Plot 6: Line plots showing trends
    ax6 = axes[1, 2]
    ax6_twin = ax6.twinx()
    
    # P&L on left axis
    line1 = ax6.plot(intervals, v1_df['total_pnl'], 'o-', label='V1 P&L', 
                     color='steelblue', linewidth=2, markersize=8)
    line2 = ax6.plot(intervals, v2_df['total_pnl'], 's-', label='V2 P&L', 
                     color='coral', linewidth=2, markersize=8)
    ax6.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax6.set_ylabel('Total P&L (AED)', fontweight='bold', color='black')
    ax6.tick_params(axis='y', labelcolor='black')
    ax6.grid(alpha=0.3)
    
    # Trades on right axis
    line3 = ax6_twin.plot(intervals, v1_df['total_trades'], '^--', label='V1 Trades', 
                          color='steelblue', linewidth=1.5, markersize=6, alpha=0.5)
    line4 = ax6_twin.plot(intervals, v2_df['total_trades'], 'v--', label='V2 Trades', 
                          color='coral', linewidth=1.5, markersize=6, alpha=0.5)
    ax6_twin.set_ylabel('Total Trades', fontweight='bold', color='gray')
    ax6_twin.tick_params(axis='y', labelcolor='gray')
    
    # Combined legend
    lines = line1 + line2 + line3 + line4
    labels = [l.get_label() for l in lines]
    ax6.legend(lines, labels, loc='best')
    ax6.set_title('Performance Trends', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved comparison plot to: {output_path}")
    plt.close()


def main():
    print("="*80)
    print("V1 vs V2 PARAMETER SWEEP COMPARISON")
    print("="*80)
    
    # Load results
    print("\nLoading sweep results...")
    v1_df = load_sweep_results(Path('output/parameter_sweep'), 'v1')
    v2_df = load_sweep_results(Path('output/v2_parameter_sweep'), 'v2')
    print(f"  V1: {len(v1_df)} intervals")
    print(f"  V2: {len(v2_df)} intervals")
    
    # Create comparison table
    print("\nCreating comparison table...")
    comparison = create_comparison_table(v1_df, v2_df)
    
    # Save comparison table
    output_dir = Path('output/strategy_comparison')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    comparison_path = output_dir / 'v1_vs_v2_sweep_comparison.csv'
    comparison.to_csv(comparison_path, index=False)
    print(f"Saved comparison table to: {comparison_path}")
    
    # Display comparison table
    print("\n" + "="*80)
    print("COMPARISON TABLE: V1 Baseline vs V2 Price Follow")
    print("="*80)
    print(comparison.to_string(index=False))
    print("="*80)
    
    # Find best configurations
    print("\nBEST CONFIGURATIONS:")
    print("-"*80)
    
    # Best for V1
    v1_best_idx = v1_df['total_pnl'].idxmax()
    v1_best = v1_df.iloc[v1_best_idx]
    print(f"\nV1 Best Interval: {v1_best['refill_interval_sec']:.0f}s")
    print(f"  Trades: {v1_best['total_trades']:,.0f}")
    print(f"  P&L: {v1_best['total_pnl']:,.2f} AED")
    print(f"  Avg P&L/Trade: {v1_best['avg_pnl_per_trade']:.2f} AED")
    
    # Best for V2
    v2_best_idx = v2_df['total_pnl'].idxmax()
    v2_best = v2_df.iloc[v2_best_idx]
    print(f"\nV2 Best Interval: {v2_best['refill_interval_sec']:.0f}s")
    print(f"  Trades: {v2_best['total_trades']:,.0f}")
    print(f"  P&L: {v2_best['total_pnl']:,.2f} AED")
    print(f"  Avg P&L/Trade: {v2_best['avg_pnl_per_trade']:.2f} AED")
    
    # Overall winner
    print("\n" + "="*80)
    print("OVERALL WINNER:")
    print("="*80)
    if v2_best['total_pnl'] > v1_best['total_pnl']:
        advantage = v2_best['total_pnl'] - v1_best['total_pnl']
        pct = (advantage / abs(v1_best['total_pnl'])) * 100
        print(f"V2 PRICE FOLLOW wins with {v2_best['refill_interval_sec']:.0f}s interval")
        print(f"  Advantage: +{advantage:,.2f} AED ({pct:+.1f}%)")
    else:
        advantage = v1_best['total_pnl'] - v2_best['total_pnl']
        pct = (advantage / abs(v2_best['total_pnl'])) * 100
        print(f"V1 BASELINE wins with {v1_best['refill_interval_sec']:.0f}s interval")
        print(f"  Advantage: +{advantage:,.2f} AED ({pct:+.1f}%)")
    
    # Create comparison plot
    print("\n" + "="*80)
    print("Creating comparison plots...")
    plot_path = output_dir / 'v1_vs_v2_sweep_comparison.png'
    plot_comparison(v1_df, v2_df, plot_path)
    
    print("\n" + "="*80)
    print("COMPARISON COMPLETE!")
    print(f"All outputs saved to: {output_dir}")
    print("="*80)


if __name__ == '__main__':
    main()
