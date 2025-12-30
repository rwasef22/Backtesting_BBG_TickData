"""Strategy comparison tools for evaluating multiple strategy variations.

This module provides utilities to compare performance metrics across
different strategy variations and generate comparison reports.

Usage:
    python scripts/compare_strategies.py  # Compare v1 vs v2
    python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown
    python scripts/compare_strategies.py --all --output comparison_report.csv
"""
import argparse
import os
import sys
from typing import List, Dict
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def load_strategy_results(strategy_name: str, output_dir: str = 'output') -> Dict:
    """Load results for a strategy.
    
    Args:
        strategy_name: Strategy identifier
        output_dir: Base output directory
        
    Returns:
        Dictionary with strategy metrics
    """
    strategy_path = os.path.join(output_dir, strategy_name)
    summary_path = os.path.join(strategy_path, 'backtest_summary.csv')
    
    if not os.path.exists(summary_path):
        print(f"Warning: No results found for {strategy_name} at {summary_path}")
        return None
    
    summary_df = pd.read_csv(summary_path)
    
    # Aggregate metrics
    metrics = {
        'strategy': strategy_name,
        'total_trades': summary_df['trades'].sum(),
        'total_pnl': summary_df['realized_pnl'].sum(),
        'num_securities': len(summary_df),
        'avg_pnl_per_security': summary_df['realized_pnl'].mean(),
        'avg_trades_per_security': summary_df['trades'].mean(),
        'total_market_dates': summary_df['market_dates'].sum(),
        'total_strategy_dates': summary_df['strategy_dates'].sum(),
    }
    
    # Calculate trading day coverage
    if metrics['total_market_dates'] > 0:
        metrics['trading_day_coverage'] = (
            metrics['total_strategy_dates'] / metrics['total_market_dates'] * 100
        )
    else:
        metrics['trading_day_coverage'] = 0.0
    
    return metrics


def compare_strategies(strategy_names: List[str], output_dir: str = 'output') -> pd.DataFrame:
    """Compare multiple strategies.
    
    Args:
        strategy_names: List of strategy identifiers
        output_dir: Base output directory
        
    Returns:
        DataFrame with comparison metrics
    """
    results = []
    
    for strategy in strategy_names:
        metrics = load_strategy_results(strategy, output_dir)
        if metrics:
            results.append(metrics)
    
    if not results:
        print("No strategy results found for comparison")
        return None
    
    df = pd.DataFrame(results)
    
    # Sort by total P&L descending
    df = df.sort_values('total_pnl', ascending=False)
    
    return df


def plot_comparison(comparison_df: pd.DataFrame, output_path: str = None):
    """Create visualization comparing strategies.
    
    Args:
        comparison_df: Comparison DataFrame
        output_path: Path to save plot (if None, displays)
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Strategy Comparison', fontsize=16, fontweight='bold')
    
    # P&L comparison
    ax1 = axes[0, 0]
    strategies = comparison_df['strategy']
    pnls = comparison_df['total_pnl']
    colors = ['green' if x > 0 else 'red' for x in pnls]
    ax1.barh(strategies, pnls, color=colors, alpha=0.7)
    ax1.set_xlabel('Total P&L (AED)', fontweight='bold')
    ax1.set_title('Total Realized P&L', fontweight='bold')
    ax1.axvline(x=0, color='black', linestyle='--', linewidth=0.5)
    ax1.grid(axis='x', alpha=0.3)
    
    # Trades comparison
    ax2 = axes[0, 1]
    trades = comparison_df['total_trades']
    ax2.barh(strategies, trades, color='steelblue', alpha=0.7)
    ax2.set_xlabel('Number of Trades', fontweight='bold')
    ax2.set_title('Total Trades Executed', fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)
    
    # Average P&L per security
    ax3 = axes[1, 0]
    avg_pnl = comparison_df['avg_pnl_per_security']
    colors = ['green' if x > 0 else 'red' for x in avg_pnl]
    ax3.barh(strategies, avg_pnl, color=colors, alpha=0.7)
    ax3.set_xlabel('Average P&L per Security (AED)', fontweight='bold')
    ax3.set_title('Avg P&L per Security', fontweight='bold')
    ax3.axvline(x=0, color='black', linestyle='--', linewidth=0.5)
    ax3.grid(axis='x', alpha=0.3)
    
    # Trading day coverage
    ax4 = axes[1, 1]
    coverage = comparison_df['trading_day_coverage']
    ax4.barh(strategies, coverage, color='darkorange', alpha=0.7)
    ax4.set_xlabel('Coverage (%)', fontweight='bold')
    ax4.set_title('Trading Day Coverage', fontweight='bold')
    ax4.set_xlim(0, 100)
    ax4.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved comparison plot: {output_path}")
    else:
        plt.show()
    
    plt.close()


def find_all_strategies(output_dir: str = 'output') -> List[str]:
    """Find all strategies with results in output directory.
    
    Args:
        output_dir: Base output directory
        
    Returns:
        List of strategy names
    """
    if not os.path.exists(output_dir):
        return []
    
    strategies = []
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path):
            summary_path = os.path.join(item_path, 'backtest_summary.csv')
            if os.path.exists(summary_path):
                strategies.append(item)
    
    return sorted(strategies)


def main():
    parser = argparse.ArgumentParser(
        description="Compare performance across strategy variations"
    )
    parser.add_argument(
        'strategies',
        nargs='*',
        help='Strategy names to compare (e.g., v1_baseline v2_aggressive_refill)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Compare all strategies found in output directory'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Base output directory (default: output)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='output/comparison/strategy_comparison.csv',
        help='Path to save comparison CSV (default: output/comparison/strategy_comparison.csv)'
    )
    parser.add_argument(
        '--plot',
        type=str,
        default='output/comparison/strategy_comparison.png',
        help='Path to save comparison plot (default: output/comparison/strategy_comparison.png)'
    )
    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='Skip generating plots'
    )
    
    args = parser.parse_args()
    
    # Determine which strategies to compare
    if args.all:
        strategies = find_all_strategies(args.output_dir)
        if not strategies:
            print(f"No strategies found in {args.output_dir}")
            sys.exit(1)
        print(f"Found {len(strategies)} strategies: {', '.join(strategies)}")
    elif args.strategies:
        strategies = args.strategies
    else:
        # Default: compare v1 vs v2
        strategies = ['v1_baseline', 'v2_price_follow_qty_cooldown']
        print("No strategies specified, comparing v1_baseline vs v2_price_follow_qty_cooldown")
    
    print(f"\n{'='*80}")
    print("STRATEGY COMPARISON")
    print(f"{'='*80}")
    print(f"Comparing: {', '.join(strategies)}")
    print(f"{'='*80}\n")
    
    # Load and compare
    comparison_df = compare_strategies(strategies, args.output_dir)
    
    if comparison_df is None or len(comparison_df) == 0:
        print("No data to compare")
        sys.exit(1)
    
    # Print comparison table
    print("\nCOMPARISON METRICS:")
    print("="*80)
    print(comparison_df.to_string(index=False))
    print("="*80)
    
    # Identify best strategy
    best_strategy = comparison_df.iloc[0]['strategy']
    best_pnl = comparison_df.iloc[0]['total_pnl']
    print(f"\nBest Strategy: {best_strategy} (P&L: {best_pnl:,.2f} AED)")
    
    # Save CSV
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    comparison_df.to_csv(args.output, index=False)
    print(f"\nSaved comparison CSV: {args.output}")
    
    # Generate plots
    if not args.no_plot:
        os.makedirs(os.path.dirname(args.plot), exist_ok=True)
        plot_comparison(comparison_df, args.plot)
    
    print(f"\n{'='*80}")
    print("DONE!")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
