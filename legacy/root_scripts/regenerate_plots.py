"""
Regenerate comprehensive sweep plots from existing CSV data.
No need to rerun the entire sweep - just reads the results and creates plots.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse


def load_all_trades_from_folders(output_dir: Path) -> dict:
    """Load all trade data from individual strategy/interval folders.
    
    Returns:
        Dictionary mapping (strategy, interval) -> results dict
    """
    all_results = {}
    
    # Find all strategy folders (v1_*, v2_*, v3_*, etc.)
    for strategy_folder in output_dir.glob('v*_*'):
        if not strategy_folder.is_dir():
            continue
        
        # Parse strategy and interval from folder name (e.g., "v1_30s" -> v1, 30)
        folder_name = strategy_folder.name
        parts = folder_name.split('_')
        if len(parts) != 2:
            continue
        
        strategy = parts[0]  # v1, v2, v3, etc.
        interval_str = parts[1].rstrip('s')  # Remove 's' from "30s"
        try:
            interval = int(interval_str)
        except ValueError:
            continue
        
        # Load trade files from this folder
        results_for_interval = {}
        
        for trades_file in strategy_folder.glob('*_trades.csv'):
            # Extract security name from filename
            security = trades_file.stem.replace('_trades', '')
            
            try:
                trades_df = pd.read_csv(trades_file)
                if len(trades_df) > 0:
                    # Convert to list of dictionaries
                    trades_list = trades_df.to_dict('records')
                    results_for_interval[security] = {'trades': trades_list}
            except Exception as e:
                print(f"Warning: Could not load {trades_file}: {e}")
                continue
        
        if results_for_interval:
            all_results[(strategy, interval)] = results_for_interval
    
    return all_results


def plot_cumulative_pnl_by_strategy(all_results: dict, output_dir: Path, strategies: list = None):
    """Plot cumulative PnL over time for each strategy with different lines per interval."""
    if strategies is None:
        strategies = sorted(set(strat for strat, _ in all_results.keys()))
    
    num_strategies = len(strategies)
    fig, axes = plt.subplots(1, num_strategies, figsize=(6*num_strategies, 6))
    if num_strategies == 1:
        axes = [axes]
    
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    
    for idx, strategy in enumerate(strategies):
        ax = axes[idx]
        
        color_idx = 0
        for (strat, interval), results in sorted(all_results.items()):
            if strat != strategy:
                continue
            
            # Collect all trades across securities
            all_trades = []
            for security, data in results.items():
                trades = data.get('trades', [])
                for trade in trades:
                    all_trades.append(trade)
            
            if not all_trades:
                continue
            
            # Create time series
            trades_df = pd.DataFrame(all_trades)
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
            trades_df = trades_df.sort_values('timestamp')
            trades_df['cumulative_pnl'] = trades_df['realized_pnl'].cumsum()
            
            # Plot
            ax.plot(trades_df['timestamp'], trades_df['cumulative_pnl'], 
                   label=f'{interval}s', linewidth=2, alpha=0.8, color=colors[color_idx])
            color_idx += 1
        
        ax.set_xlabel('Date', fontweight='bold', fontsize=12)
        ax.set_ylabel('Cumulative P&L (AED)', fontweight='bold', fontsize=12)
        ax.set_title(f'{strategy.upper()} Strategy: Cumulative P&L Over Time', 
                    fontweight='bold', fontsize=14)
        ax.legend(title='Refill Interval', fontsize=10)
        ax.grid(alpha=0.3)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
    
    plt.tight_layout()
    plot_path = output_dir / 'cumulative_pnl_by_strategy.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved cumulative P&L plot: {plot_path}")
    plt.close()


def create_comparison_plots(metrics_df: pd.DataFrame, output_dir: Path):
    """Create comprehensive comparison plots for all available strategies."""
    
    # Get all available strategies
    strategies = sorted(metrics_df['strategy'].unique())
    num_strategies = len(strategies)
    
    print(f"Creating comparison plots for {num_strategies} strategies: {strategies}")
    
    # Define colors for up to 5 strategies
    strategy_colors = {
        'v1': 'steelblue',
        'v2': 'coral',
        'v3': 'mediumseagreen',
        'v4': 'gold',
        'v5': 'mediumpurple'
    }
    
    # Define markers for scatter plots
    strategy_markers = {
        'v1': 'o',
        'v2': 's',
        'v3': '^',
        'v4': 'D',
        'v5': 'v'
    }
    
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)
    
    # Get strategy data
    strategy_data = {s: metrics_df[metrics_df['strategy'] == s].sort_values('interval_sec') 
                     for s in strategies}
    
    intervals = sorted(metrics_df['interval_sec'].unique())
    x = np.arange(len(intervals))
    width = 0.8 / num_strategies  # Adjust width based on number of strategies
    
    # 1. Total P&L
    ax1 = fig.add_subplot(gs[0, 0])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax1.bar(x + offset, strategy_data[strategy]['total_pnl'], width, 
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
        offset = width * (i - (num_strategies - 1) / 2)
        ax2.bar(x + offset, strategy_data[strategy]['total_trades'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax2.set_xlabel('Interval (sec)', fontweight='bold')
    ax2.set_ylabel('Number of Trades', fontweight='bold')
    ax2.set_title('Total Trades', fontweight='bold', fontsize=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(intervals)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    # 3. Sharpe Ratio
    ax3 = fig.add_subplot(gs[0, 2])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax3.bar(x + offset, strategy_data[strategy]['sharpe_ratio'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax3.set_xlabel('Interval (sec)', fontweight='bold')
    ax3.set_ylabel('Sharpe Ratio', fontweight='bold')
    ax3.set_title('Sharpe Ratio (Annualized)', fontweight='bold', fontsize=12)
    ax3.set_xticks(x)
    ax3.set_xticklabels(intervals)
    ax3.legend()
    ax3.grid(axis='y', alpha=0.3)
    ax3.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    # 4. Max Drawdown %
    ax4 = fig.add_subplot(gs[1, 0])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax4.bar(x + offset, strategy_data[strategy]['max_drawdown_pct'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax4.set_xlabel('Interval (sec)', fontweight='bold')
    ax4.set_ylabel('Drawdown (%)', fontweight='bold')
    ax4.set_title('Maximum Drawdown', fontweight='bold', fontsize=12)
    ax4.set_xticks(x)
    ax4.set_xticklabels(intervals)
    ax4.legend()
    ax4.grid(axis='y', alpha=0.3)
    
    # 5. Avg P&L per Trade
    ax5 = fig.add_subplot(gs[1, 1])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax5.bar(x + offset, strategy_data[strategy]['avg_pnl_per_trade'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax5.set_xlabel('Interval (sec)', fontweight='bold')
    ax5.set_ylabel('Avg P&L (AED)', fontweight='bold')
    ax5.set_title('Avg P&L per Trade', fontweight='bold', fontsize=12)
    ax5.set_xticks(x)
    ax5.set_xticklabels(intervals)
    ax5.legend()
    ax5.grid(axis='y', alpha=0.3)
    ax5.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    # 6. Win Rate
    ax6 = fig.add_subplot(gs[1, 2])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax6.bar(x + offset, strategy_data[strategy]['win_rate'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax6.set_xlabel('Interval (sec)', fontweight='bold')
    ax6.set_ylabel('Win Rate (%)', fontweight='bold')
    ax6.set_title('Win Rate', fontweight='bold', fontsize=12)
    ax6.set_xticks(x)
    ax6.set_xticklabels(intervals)
    ax6.set_ylim(0, 100)
    ax6.legend()
    ax6.grid(axis='y', alpha=0.3)
    
    # 7. Calmar Ratio
    ax7 = fig.add_subplot(gs[2, 0])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax7.bar(x + offset, strategy_data[strategy]['calmar_ratio'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax7.set_xlabel('Interval (sec)', fontweight='bold')
    ax7.set_ylabel('Calmar Ratio', fontweight='bold')
    ax7.set_title('Calmar Ratio', fontweight='bold', fontsize=12)
    ax7.set_xticks(x)
    ax7.set_xticklabels(intervals)
    ax7.legend()
    ax7.grid(axis='y', alpha=0.3)
    
    # 8. Profit Factor
    ax8 = fig.add_subplot(gs[2, 1])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax8.bar(x + offset, strategy_data[strategy]['profit_factor'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax8.set_xlabel('Interval (sec)', fontweight='bold')
    ax8.set_ylabel('Profit Factor', fontweight='bold')
    ax8.set_title('Profit Factor (Wins/Losses)', fontweight='bold', fontsize=12)
    ax8.set_xticks(x)
    ax8.set_xticklabels(intervals)
    ax8.axhline(1, color='black', linestyle='--', linewidth=0.5)
    ax8.legend()
    ax8.grid(axis='y', alpha=0.3)
    
    # 9. Trades per Day
    ax9 = fig.add_subplot(gs[2, 2])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax9.bar(x + offset, strategy_data[strategy]['trades_per_day'], width,
               label=strategy.upper(), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
    ax9.set_xlabel('Interval (sec)', fontweight='bold')
    ax9.set_ylabel('Trades/Day', fontweight='bold')
    ax9.set_title('Trades per Day', fontweight='bold', fontsize=12)
    ax9.set_xticks(x)
    ax9.set_xticklabels(intervals)
    ax9.legend()
    ax9.grid(axis='y', alpha=0.3)
    
    # 10. Risk-Return Scatter
    ax10 = fig.add_subplot(gs[3, 0])
    for strategy in strategies:
        data = strategy_data[strategy]
        for i, (dd, pnl, interval) in enumerate(zip(data['max_drawdown_pct'].abs(), 
                                                      data['total_pnl'], 
                                                      data['interval_sec'])):
            ax10.scatter(dd, pnl, s=200, alpha=0.7, c=strategy_colors[strategy], edgecolor='black', 
                        marker=strategy_markers[strategy], label=strategy.upper() if i == 0 else '')
            ax10.annotate(f'{int(interval)}s', (dd, pnl), fontsize=7, ha='center', 
                         va='bottom' if strategy == strategies[0] else 'top')
    
    ax10.set_xlabel('Max Drawdown % (abs)', fontweight='bold')
    ax10.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax10.set_title('Risk-Return Profile', fontweight='bold', fontsize=12)
    ax10.legend()
    ax10.grid(alpha=0.3)
    
    # 11. Sharpe vs Interval Line Plot
    ax11 = fig.add_subplot(gs[3, 1])
    for strategy in strategies:
        data = strategy_data[strategy]
        ax11.plot(data['interval_sec'], data['sharpe_ratio'], 
                 marker=strategy_markers[strategy], linewidth=2, markersize=8, 
                 label=strategy.upper(), color=strategy_colors[strategy])
    ax11.set_xlabel('Interval (sec)', fontweight='bold')
    ax11.set_ylabel('Sharpe Ratio', fontweight='bold')
    ax11.set_title('Sharpe Ratio Trend', fontweight='bold', fontsize=12)
    ax11.legend()
    ax11.grid(alpha=0.3)
    ax11.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    # 12. P&L vs Interval Line Plot
    ax12 = fig.add_subplot(gs[3, 2])
    for strategy in strategies:
        data = strategy_data[strategy]
        ax12.plot(data['interval_sec'], data['total_pnl'], 
                 marker=strategy_markers[strategy], linewidth=2, markersize=8,
                 label=strategy.upper(), color=strategy_colors[strategy])
    ax12.set_xlabel('Interval (sec)', fontweight='bold')
    ax12.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax12.set_title('P&L Trend', fontweight='bold', fontsize=12)
    ax12.legend()
    ax12.grid(alpha=0.3)
    ax12.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    # Update title to reflect all strategies
    title_strategies = ' vs '.join([s.upper() for s in strategies])
    fig.suptitle(f'{title_strategies}: Comprehensive Comparison', 
                 fontsize=18, fontweight='bold', y=0.995)
    
    plot_path = output_dir / 'comprehensive_comparison.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved comparison plot: {plot_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Regenerate plots from existing CSV data')
    parser.add_argument('--output-dir', type=str, default='output/comprehensive_sweep',
                       help='Directory containing the sweep results')
    parser.add_argument('--results-csv', type=str, default=None,
                       help='Path to comprehensive_results.csv or checkpoint.csv (default: auto-detect)')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    # Find results CSV
    if args.results_csv:
        results_path = Path(args.results_csv)
    else:
        # Try comprehensive_results.csv first, then checkpoint.csv
        results_path = output_dir / 'comprehensive_results.csv'
        if not results_path.exists():
            results_path = output_dir / 'checkpoint.csv'
    
    if not results_path.exists():
        print(f"Error: Could not find results CSV at {results_path}")
        return
    
    print(f"\n{'='*80}")
    print("REGENERATING PLOTS FROM EXISTING DATA")
    print(f"{'='*80}")
    print(f"Results CSV: {results_path}")
    print(f"Output Directory: {output_dir}")
    print(f"{'='*80}\n")
    
    # Load metrics
    print("Loading metrics data...")
    metrics_df = pd.read_csv(results_path)
    strategies = sorted(metrics_df['strategy'].unique())
    intervals = sorted(metrics_df['interval_sec'].unique())
    
    print(f"Found {len(metrics_df)} results:")
    print(f"  Strategies: {strategies}")
    print(f"  Intervals: {intervals}")
    print()
    
    # Create comparison plots
    print("Creating comparison plots...")
    create_comparison_plots(metrics_df, output_dir)
    
    # Load trade data and create cumulative P&L plots
    print("\nLoading trade data from folders...")
    all_results = load_all_trades_from_folders(output_dir)
    
    if all_results:
        print(f"Found trade data for {len(all_results)} strategy-interval combinations")
        print("\nCreating cumulative P&L plots...")
        plot_cumulative_pnl_by_strategy(all_results, output_dir, strategies=strategies)
    else:
        print("Warning: No trade data found in folders. Skipping cumulative P&L plots.")
    
    print(f"\n{'='*80}")
    print("PLOT REGENERATION COMPLETE!")
    print(f"All plots saved to: {output_dir}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
