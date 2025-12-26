"""Parameter sweep script for testing different refill intervals.

This script runs the v1_baseline strategy with different refill_interval_sec
values and compares the performance to find the optimal parameter.

Usage:
    python scripts/sweep_refill_intervals.py
    python scripts/sweep_refill_intervals.py --max-sheets 5  # Quick test
"""
import argparse
import json
import os
import sys
import time
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.mm_handler import create_mm_handler


def create_config_with_interval(base_config: dict, interval_sec: int) -> dict:
    """Create a new config with specified refill interval for all securities.
    
    Args:
        base_config: Original configuration
        interval_sec: Refill interval in seconds
        
    Returns:
        New config with updated interval
    """
    new_config = {}
    for security, params in base_config.items():
        new_params = params.copy()
        new_params['refill_interval_sec'] = interval_sec
        new_config[security] = new_params
    return new_config


def run_with_interval(interval_sec: int, base_config: dict, data_path: str, 
                     max_sheets: int = None, chunk_size: int = 100000) -> dict:
    """Run backtest with specified refill interval.
    
    Args:
        interval_sec: Refill interval in seconds
        base_config: Base configuration
        data_path: Path to Excel data file
        max_sheets: Maximum sheets to process
        chunk_size: Rows per chunk
        
    Returns:
        Results dictionary
    """
    print(f"\n{'='*80}")
    print(f"Testing Refill Interval: {interval_sec} seconds ({interval_sec/60:.1f} minutes)")
    print(f"{'='*80}")
    
    # Create config with this interval
    config = create_config_with_interval(base_config, interval_sec)
    
    # Create handler
    handler = create_mm_handler(config=config)
    
    # Run backtest
    start_time = time.time()
    backtest = MarketMakingBacktest()
    results = backtest.run_streaming(
        file_path=data_path,
        handler=handler,
        max_sheets=max_sheets,
        chunk_size=chunk_size,
        only_trades=False  # CRITICAL: Need to read bid/ask updates for orderbook
    )
    elapsed = time.time() - start_time
    
    print(f"Completed in {elapsed:.1f} seconds")
    
    return results


def compute_metrics(results: dict, interval_sec: int) -> dict:
    """Compute aggregate metrics from results.
    
    Args:
        results: Results dictionary
        interval_sec: Refill interval used
        
    Returns:
        Dictionary of metrics
    """
    total_trades = 0
    total_pnl = 0.0
    total_volume = 0.0
    securities_traded = 0
    total_market_days = 0
    total_strategy_days = 0
    
    for security, data in results.items():
        trades = data.get('trades', [])
        if len(trades) > 0:
            securities_traded += 1
            total_trades += len(trades)
            total_pnl += data.get('pnl', 0.0)
            
            # Calculate volume
            for trade in trades:
                total_volume += trade['fill_price'] * trade['fill_qty']
            
            total_market_days += len(data.get('market_dates', set()))
            total_strategy_days += len(data.get('strategy_dates', set()))
    
    # Calculate derived metrics
    avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
    avg_pnl_per_security = total_pnl / securities_traded if securities_traded > 0 else 0
    trading_day_coverage = (total_strategy_days / total_market_days * 100) if total_market_days > 0 else 0
    
    return {
        'refill_interval_sec': interval_sec,
        'refill_interval_min': interval_sec / 60,
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'total_volume': total_volume,
        'securities_traded': securities_traded,
        'avg_pnl_per_trade': avg_pnl_per_trade,
        'avg_pnl_per_security': avg_pnl_per_security,
        'total_market_days': total_market_days,
        'total_strategy_days': total_strategy_days,
        'trading_day_coverage': trading_day_coverage
    }


def plot_comparison(comparison_df: pd.DataFrame, output_path: str):
    """Create visualization comparing different intervals.
    
    Args:
        comparison_df: DataFrame with comparison metrics
        output_path: Path to save plot
    """
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Refill Interval Parameter Sweep', fontsize=16, fontweight='bold')
    
    intervals = comparison_df['refill_interval_sec']
    
    # Plot 1: Total P&L
    ax1 = axes[0, 0]
    colors = ['green' if x > 0 else 'red' for x in comparison_df['total_pnl']]
    ax1.bar(intervals, comparison_df['total_pnl'], color=colors, alpha=0.7, edgecolor='black')
    ax1.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax1.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax1.set_title('Total Realized P&L', fontweight='bold')
    ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax1.grid(axis='y', alpha=0.3)
    
    # Plot 2: Total Trades
    ax2 = axes[0, 1]
    ax2.bar(intervals, comparison_df['total_trades'], color='steelblue', alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax2.set_ylabel('Number of Trades', fontweight='bold')
    ax2.set_title('Total Trades Executed', fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # Plot 3: Average P&L per Trade
    ax3 = axes[0, 2]
    colors = ['green' if x > 0 else 'red' for x in comparison_df['avg_pnl_per_trade']]
    ax3.bar(intervals, comparison_df['avg_pnl_per_trade'], color=colors, alpha=0.7, edgecolor='black')
    ax3.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax3.set_ylabel('Avg P&L per Trade (AED)', fontweight='bold')
    ax3.set_title('Average P&L per Trade', fontweight='bold')
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax3.grid(axis='y', alpha=0.3)
    
    # Plot 4: Trading Day Coverage
    ax4 = axes[1, 0]
    ax4.bar(intervals, comparison_df['trading_day_coverage'], color='darkorange', alpha=0.7, edgecolor='black')
    ax4.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax4.set_ylabel('Coverage (%)', fontweight='bold')
    ax4.set_title('Trading Day Coverage', fontweight='bold')
    ax4.set_ylim(0, 100)
    ax4.grid(axis='y', alpha=0.3)
    
    # Plot 5: P&L vs Trades (scatter)
    ax5 = axes[1, 1]
    scatter = ax5.scatter(comparison_df['total_trades'], comparison_df['total_pnl'], 
                         s=200, c=intervals, cmap='viridis', alpha=0.7, edgecolor='black')
    for i, interval in enumerate(intervals):
        ax5.annotate(f'{interval:.0f}s', 
                    (comparison_df['total_trades'].iloc[i], comparison_df['total_pnl'].iloc[i]),
                    fontsize=10, ha='center', va='bottom')
    ax5.set_xlabel('Total Trades', fontweight='bold')
    ax5.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax5.set_title('P&L vs Trade Count', fontweight='bold')
    ax5.grid(alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax5)
    cbar.set_label('Refill Interval (sec)', fontweight='bold')
    
    # Plot 6: Average P&L per Security
    ax6 = axes[1, 2]
    colors = ['green' if x > 0 else 'red' for x in comparison_df['avg_pnl_per_security']]
    ax6.bar(intervals, comparison_df['avg_pnl_per_security'], color=colors, alpha=0.7, edgecolor='black')
    ax6.set_xlabel('Refill Interval (seconds)', fontweight='bold')
    ax6.set_ylabel('Avg P&L per Security (AED)', fontweight='bold')
    ax6.set_title('Average P&L per Security', fontweight='bold')
    ax6.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax6.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved comparison plot: {output_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Sweep refill interval parameter and compare performance"
    )
    parser.add_argument(
        '--config',
        type=str,
        default='configs/v1_baseline_config.json',
        help='Base config file (default: configs/v1_baseline_config.json)'
    )
    parser.add_argument(
        '--data',
        type=str,
        default='data/raw/TickData.xlsx',
        help='Path to input Excel file (default: data/raw/TickData.xlsx)'
    )
    parser.add_argument(
        '--intervals',
        type=int,
        nargs='+',
        default=[60, 120, 180, 300, 600],
        help='Refill intervals to test in seconds (default: 60 120 180 300 600)'
    )
    parser.add_argument(
        '--max-sheets',
        type=int,
        default=None,
        help='Maximum number of sheets to process (default: all)'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=100000,
        help='Rows per chunk (default: 100000)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output/parameter_sweep',
        help='Output directory (default: output/parameter_sweep)'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print("REFILL INTERVAL PARAMETER SWEEP")
    print(f"{'='*80}")
    print(f"Base Config: {args.config}")
    print(f"Data: {args.data}")
    print(f"Intervals: {[f'{x}s ({x/60:.1f}m)' for x in args.intervals]}")
    print(f"Max Sheets: {args.max_sheets or 'All'}")
    print(f"Output: {args.output_dir}")
    print(f"{'='*80}\n")
    
    # Load base configuration
    print("Loading base configuration...")
    base_config = load_strategy_config(args.config)
    print(f"Loaded config for {len(base_config)} securities\n")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run backtest for each interval
    all_metrics = []
    
    for interval_sec in args.intervals:
        # Run backtest
        results = run_with_interval(
            interval_sec=interval_sec,
            base_config=base_config,
            data_path=args.data,
            max_sheets=args.max_sheets,
            chunk_size=args.chunk_size
        )
        
        # Compute metrics
        metrics = compute_metrics(results, interval_sec)
        all_metrics.append(metrics)
        
        # Save detailed results
        interval_dir = os.path.join(args.output_dir, f'interval_{interval_sec}s')
        os.makedirs(interval_dir, exist_ok=True)
        
        # Save per-security results
        summary_rows = []
        for security, data in results.items():
            trades = data.get('trades', [])
            if len(trades) > 0:
                # Save trade timeseries
                trades_df = pd.DataFrame(trades)
                csv_path = os.path.join(interval_dir, f"{security}_trades.csv")
                trades_df.to_csv(csv_path, index=False)
                
                # Add to summary
                summary_rows.append({
                    'security': security,
                    'trades': len(trades),
                    'pnl': data.get('pnl', 0.0),
                    'position': data.get('position', 0),
                    'market_dates': len(data.get('market_dates', set())),
                    'strategy_dates': len(data.get('strategy_dates', set()))
                })
        
        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            summary_path = os.path.join(interval_dir, 'summary.csv')
            summary_df.to_csv(summary_path, index=False)
        
        # Print summary for this interval
        print(f"\nInterval {interval_sec}s ({interval_sec/60:.1f}m) Results:")
        print(f"  Trades: {metrics['total_trades']:,}")
        print(f"  P&L: {metrics['total_pnl']:,.2f} AED")
        print(f"  Avg P&L/Trade: {metrics['avg_pnl_per_trade']:.2f} AED")
        print(f"  Coverage: {metrics['trading_day_coverage']:.1f}%")
    
    # Create comparison DataFrame
    comparison_df = pd.DataFrame(all_metrics)
    comparison_df = comparison_df.sort_values('refill_interval_sec')
    
    # Save comparison CSV
    comparison_path = os.path.join(args.output_dir, 'interval_comparison.csv')
    comparison_df.to_csv(comparison_path, index=False)
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print(f"{'='*80}")
    print(comparison_df.to_string(index=False))
    print(f"{'='*80}")
    
    # Identify best interval
    best_idx = comparison_df['total_pnl'].idxmax()
    best_row = comparison_df.iloc[best_idx]
    print(f"\nBest Interval: {best_row['refill_interval_sec']:.0f}s ({best_row['refill_interval_min']:.1f}m)")
    print(f"  Total P&L: {best_row['total_pnl']:,.2f} AED")
    print(f"  Total Trades: {best_row['total_trades']:,.0f}")
    print(f"  Avg P&L per Trade: {best_row['avg_pnl_per_trade']:.2f} AED")
    print(f"  Coverage: {best_row['trading_day_coverage']:.1f}%")
    
    # Create visualization
    plot_path = os.path.join(args.output_dir, 'interval_comparison.png')
    plot_comparison(comparison_df, plot_path)
    
    print(f"\n{'='*80}")
    print("DONE!")
    print(f"Results saved to: {args.output_dir}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
