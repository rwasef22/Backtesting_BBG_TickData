"""
Detailed per-security comparison between v1_baseline and v2_price_follow_qty_cooldown.

This script generates comprehensive analysis including:
- Per-security trade counts, P&L, and metrics
- Aggregate performance comparison
- Winner analysis
- Detailed visualizations
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_strategy_summary(strategy_name: str, base_dir: Path = Path('output')):
    """Load backtest summary for a strategy."""
    summary_file = base_dir / strategy_name / 'backtest_summary.csv'
    
    if not summary_file.exists():
        print(f"ERROR: Could not find {summary_file}")
        return None
    
    df = pd.read_csv(summary_file)
    
    # Normalize column names to match v2 format
    if 'Security' in df.columns:
        # V1 format - rename to match v2
        column_map = {
            'Security': 'security',
            'Trades': 'total_trades',
            'Final P&L (AED)': 'total_pnl',
            'Final Position': 'final_position'
        }
        df = df.rename(columns=column_map)
        
        # Calculate avg_pnl_per_trade if not present
        if 'avg_pnl_per_trade' not in df.columns:
            df['avg_pnl_per_trade'] = df['total_pnl'] / df['total_trades']
    
    print(f"Loaded {strategy_name}: {len(df)} securities")
    return df


def create_detailed_comparison(v1_df, v2_df, output_dir: Path):
    """Generate detailed comparison analysis."""
    
    # Merge on security name
    comparison = pd.merge(
        v1_df,
        v2_df,
        on='security',
        suffixes=('_v1', '_v2'),
        how='outer'
    )
    
    # Calculate differences and percentage changes
    comparison['trade_diff'] = comparison['total_trades_v2'] - comparison['total_trades_v1']
    comparison['trade_pct'] = (comparison['trade_diff'] / comparison['total_trades_v1']) * 100
    
    comparison['pnl_diff'] = comparison['total_pnl_v2'] - comparison['total_pnl_v1']
    comparison['pnl_pct'] = (comparison['pnl_diff'] / comparison['total_pnl_v1'].abs()) * 100
    
    comparison['avg_pnl_diff'] = comparison['avg_pnl_per_trade_v2'] - comparison['avg_pnl_per_trade_v1']
    comparison['avg_pnl_pct'] = (comparison['avg_pnl_diff'] / comparison['avg_pnl_per_trade_v1'].abs()) * 100
    
    # Save detailed comparison
    output_file = output_dir / 'detailed_comparison.csv'
    comparison.to_csv(output_file, index=False)
    print(f"\nSaved detailed comparison to: {output_file}")
    
    return comparison


def print_comparison_report(comparison: pd.DataFrame):
    """Print comprehensive comparison report."""
    
    print("\n" + "="*100)
    print("DETAILED PER-SECURITY COMPARISON: v1_baseline vs v2_price_follow_qty_cooldown")
    print("="*100)
    
    # Set pandas display options
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.float_format', '{:.2f}'.format)
    
    # Display key columns
    display_cols = [
        'security',
        'total_trades_v1', 'total_trades_v2', 'trade_diff', 'trade_pct',
        'total_pnl_v1', 'total_pnl_v2', 'pnl_diff', 'pnl_pct'
    ]
    
    print("\n" + "-"*100)
    print("TRADE COUNTS AND P&L:")
    print("-"*100)
    print(comparison[display_cols].to_string(index=False))
    
    # Avg P&L per trade
    avg_cols = [
        'security',
        'avg_pnl_per_trade_v1', 'avg_pnl_per_trade_v2', 'avg_pnl_diff', 'avg_pnl_pct'
    ]
    print("\n" + "-"*100)
    print("AVERAGE P&L PER TRADE:")
    print("-"*100)
    print(comparison[avg_cols].to_string(index=False))
    
    # Aggregate statistics
    print("\n" + "="*100)
    print("AGGREGATE STATISTICS:")
    print("="*100)
    
    total_trades_v1 = comparison['total_trades_v1'].sum()
    total_trades_v2 = comparison['total_trades_v2'].sum()
    total_pnl_v1 = comparison['total_pnl_v1'].sum()
    total_pnl_v2 = comparison['total_pnl_v2'].sum()
    
    print(f"\n{'Metric':<40} {'v1_baseline':>20} {'v2_price_follow':>20} {'Difference':>20}")
    print("-"*100)
    print(f"{'Total Trades':<40} {total_trades_v1:>20,.0f} {total_trades_v2:>20,.0f} {total_trades_v2-total_trades_v1:>20,.0f}")
    print(f"{'Total P&L (AED)':<40} {total_pnl_v1:>20,.2f} {total_pnl_v2:>20,.2f} {total_pnl_v2-total_pnl_v1:>20,.2f}")
    print(f"{'Avg P&L per Trade':<40} {total_pnl_v1/total_trades_v1:>20,.4f} {total_pnl_v2/total_trades_v2:>20,.4f} {(total_pnl_v2/total_trades_v2)-(total_pnl_v1/total_trades_v1):>20,.4f}")
    
    # Percentage changes
    trade_pct_change = ((total_trades_v2 - total_trades_v1) / total_trades_v1) * 100
    pnl_pct_change = ((total_pnl_v2 - total_pnl_v1) / abs(total_pnl_v1)) * 100
    
    print(f"\n{'Percentage Change':<40} {' ':>20} {' ':>20} {'% Change':>20}")
    print("-"*100)
    print(f"{'Trade Count Change':<40} {' ':>20} {' ':>20} {trade_pct_change:>19,.2f}%")
    print(f"{'P&L Change':<40} {' ':>20} {' ':>20} {pnl_pct_change:>19,.2f}%")
    
    # Winner analysis
    print("\n" + "="*100)
    print("WINNER ANALYSIS:")
    print("="*100)
    
    total_securities = len(comparison)
    
    # Count wins per metric
    v2_wins_trades = (comparison['total_trades_v2'] > comparison['total_trades_v1']).sum()
    v2_wins_pnl = (comparison['total_pnl_v2'] > comparison['total_pnl_v1']).sum()
    v2_wins_avg = (comparison['avg_pnl_per_trade_v2'] > comparison['avg_pnl_per_trade_v1']).sum()
    
    print(f"\n{'Metric':<40} {'v2 Wins':>15} {'v1 Wins':>15} {'v2 Win %':>15}")
    print("-"*100)
    print(f"{'Trade Count':<40} {v2_wins_trades:>15} {total_securities-v2_wins_trades:>15} {v2_wins_trades/total_securities*100:>14,.1f}%")
    print(f"{'Total P&L':<40} {v2_wins_pnl:>15} {total_securities-v2_wins_pnl:>15} {v2_wins_pnl/total_securities*100:>14,.1f}%")
    print(f"{'Avg P&L per Trade':<40} {v2_wins_avg:>15} {total_securities-v2_wins_avg:>15} {v2_wins_avg/total_securities*100:>14,.1f}%")
    
    # Overall winner
    print("\n" + "="*100)
    print("OVERALL WINNER:")
    print("="*100)
    
    if total_pnl_v2 > total_pnl_v1:
        winner = "v2_price_follow_qty_cooldown"
        improvement = ((total_pnl_v2 - total_pnl_v1) / abs(total_pnl_v1)) * 100
        abs_gain = total_pnl_v2 - total_pnl_v1
    else:
        winner = "v1_baseline"
        improvement = ((total_pnl_v1 - total_pnl_v2) / abs(total_pnl_v2)) * 100
        abs_gain = total_pnl_v1 - total_pnl_v2
    
    print(f"\nWINNER: {winner}")
    print(f"P&L Improvement: {improvement:+.2f}%")
    print(f"Absolute Gain: {abs_gain:+,.2f} AED")
    
    # Best/worst performers for v2
    print("\n" + "="*100)
    print("TOP 5 GAINERS (v2 vs v1):")
    print("="*100)
    top_gainers = comparison.nlargest(5, 'pnl_diff')[['security', 'pnl_diff', 'pnl_pct']]
    print(top_gainers.to_string(index=False))
    
    print("\n" + "="*100)
    print("TOP 5 LOSERS (v2 vs v1):")
    print("="*100)
    top_losers = comparison.nsmallest(5, 'pnl_diff')[['security', 'pnl_diff', 'pnl_pct']]
    print(top_losers.to_string(index=False))
    
    print("\n" + "="*100)


def generate_visualizations(comparison: pd.DataFrame, output_dir: Path):
    """Generate comprehensive comparison visualizations."""
    
    print("\nGenerating visualizations...")
    
    # Sort by security for consistent ordering
    comparison = comparison.sort_values('security').reset_index(drop=True)
    
    # Create figure with multiple subplots
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    securities = comparison['security'].tolist()
    x = np.arange(len(securities))
    width = 0.35
    
    # 1. Trade Counts
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.bar(x - width/2, comparison['total_trades_v1'], width, label='v1', alpha=0.8, color='steelblue')
    ax1.bar(x + width/2, comparison['total_trades_v2'], width, label='v2', alpha=0.8, color='coral')
    ax1.set_xlabel('Security', fontsize=10)
    ax1.set_ylabel('Total Trades', fontsize=10)
    ax1.set_title('Trade Count Comparison', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Total P&L
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.bar(x - width/2, comparison['total_pnl_v1'], width, label='v1', alpha=0.8, color='steelblue')
    ax2.bar(x + width/2, comparison['total_pnl_v2'], width, label='v2', alpha=0.8, color='coral')
    ax2.set_xlabel('Security', fontsize=10)
    ax2.set_ylabel('Total P&L (AED)', fontsize=10)
    ax2.set_title('Total P&L Comparison', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    
    # 3. Avg P&L per Trade
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.bar(x - width/2, comparison['avg_pnl_per_trade_v1'], width, label='v1', alpha=0.8, color='steelblue')
    ax3.bar(x + width/2, comparison['avg_pnl_per_trade_v2'], width, label='v2', alpha=0.8, color='coral')
    ax3.set_xlabel('Security', fontsize=10)
    ax3.set_ylabel('Avg P&L per Trade', fontsize=10)
    ax3.set_title('Avg P&L per Trade Comparison', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    
    # 4. Trade Count Difference
    ax4 = fig.add_subplot(gs[1, 0])
    colors = ['green' if val > 0 else 'red' for val in comparison['trade_diff']]
    ax4.bar(x, comparison['trade_diff'], color=colors, alpha=0.7)
    ax4.set_xlabel('Security', fontsize=10)
    ax4.set_ylabel('Trade Difference (v2 - v1)', fontsize=10)
    ax4.set_title('Trade Count Change', fontsize=12, fontweight='bold')
    ax4.set_xticks(x)
    ax4.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax4.grid(True, alpha=0.3)
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # 5. P&L Difference
    ax5 = fig.add_subplot(gs[1, 1])
    colors = ['green' if val > 0 else 'red' for val in comparison['pnl_diff']]
    ax5.bar(x, comparison['pnl_diff'], color=colors, alpha=0.7)
    ax5.set_xlabel('Security', fontsize=10)
    ax5.set_ylabel('P&L Difference (v2 - v1)', fontsize=10)
    ax5.set_title('P&L Change', fontsize=12, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax5.grid(True, alpha=0.3)
    ax5.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # 6. Avg P&L Difference
    ax6 = fig.add_subplot(gs[1, 2])
    colors = ['green' if val > 0 else 'red' for val in comparison['avg_pnl_diff']]
    ax6.bar(x, comparison['avg_pnl_diff'], color=colors, alpha=0.7)
    ax6.set_xlabel('Security', fontsize=10)
    ax6.set_ylabel('Avg P&L Diff (v2 - v1)', fontsize=10)
    ax6.set_title('Avg P&L per Trade Change', fontsize=12, fontweight='bold')
    ax6.set_xticks(x)
    ax6.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax6.grid(True, alpha=0.3)
    ax6.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # 7. Trade Count % Change
    ax7 = fig.add_subplot(gs[2, 0])
    colors = ['green' if val > 0 else 'red' for val in comparison['trade_pct']]
    ax7.bar(x, comparison['trade_pct'], color=colors, alpha=0.7)
    ax7.set_xlabel('Security', fontsize=10)
    ax7.set_ylabel('% Change', fontsize=10)
    ax7.set_title('Trade Count % Change', fontsize=12, fontweight='bold')
    ax7.set_xticks(x)
    ax7.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax7.grid(True, alpha=0.3)
    ax7.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # 8. P&L % Change
    ax8 = fig.add_subplot(gs[2, 1])
    colors = ['green' if val > 0 else 'red' for val in comparison['pnl_pct']]
    ax8.bar(x, comparison['pnl_pct'], color=colors, alpha=0.7)
    ax8.set_xlabel('Security', fontsize=10)
    ax8.set_ylabel('% Change', fontsize=10)
    ax8.set_title('P&L % Change', fontsize=12, fontweight='bold')
    ax8.set_xticks(x)
    ax8.set_xticklabels(securities, rotation=45, ha='right', fontsize=8)
    ax8.grid(True, alpha=0.3)
    ax8.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # 9. Summary Statistics
    ax9 = fig.add_subplot(gs[2, 2])
    ax9.axis('off')
    
    summary_text = f"""AGGREGATE SUMMARY

v1_baseline:
  Total Trades: {comparison['total_trades_v1'].sum():,.0f}
  Total P&L: {comparison['total_pnl_v1'].sum():,.2f} AED
  Avg P&L/Trade: {comparison['total_pnl_v1'].sum()/comparison['total_trades_v1'].sum():,.4f}

v2_price_follow_qty_cooldown:
  Total Trades: {comparison['total_trades_v2'].sum():,.0f}
  Total P&L: {comparison['total_pnl_v2'].sum():,.2f} AED
  Avg P&L/Trade: {comparison['total_pnl_v2'].sum()/comparison['total_trades_v2'].sum():,.4f}

Change:
  Trades: {comparison['trade_diff'].sum():+,.0f} ({(comparison['trade_diff'].sum()/comparison['total_trades_v1'].sum()*100):+.2f}%)
  P&L: {comparison['pnl_diff'].sum():+,.2f} ({(comparison['pnl_diff'].sum()/comparison['total_pnl_v1'].sum()*100):+.2f}%)
"""
    
    ax9.text(0.1, 0.5, summary_text, fontsize=10, family='monospace',
             verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.suptitle('Strategy Comparison: v1_baseline vs v2_price_follow_qty_cooldown', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    # Save figure
    plot_file = output_dir / 'detailed_comparison.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved visualization to: {plot_file}")


def main():
    """Main execution function."""
    
    print("="*100)
    print("DETAILED STRATEGY COMPARISON")
    print("="*100)
    
    # Define paths
    base_dir = Path('output')
    comparison_dir = base_dir / 'comparison'
    comparison_dir.mkdir(parents=True, exist_ok=True)
    
    # Load strategy results
    print("\nLoading strategy results...")
    v1_df = load_strategy_summary('v1_baseline', base_dir)
    v2_df = load_strategy_summary('v2_price_follow_qty_cooldown', base_dir)
    
    if v1_df is None or v2_df is None:
        print("\nERROR: Could not load one or both strategy results")
        print("Make sure both strategies have been run and have backtest_summary.csv files")
        return 1
    
    # Create comparison
    comparison = create_detailed_comparison(v1_df, v2_df, comparison_dir)
    
    # Print report
    print_comparison_report(comparison)
    
    # Generate visualizations
    generate_visualizations(comparison, comparison_dir)
    
    print("\n" + "="*100)
    print(f"COMPARISON COMPLETE!")
    print(f"All outputs saved to: {comparison_dir}/")
    print("="*100 + "\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
