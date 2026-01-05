"""Fast parameter sweep using parallel processing.

This script runs parameter sweeps more efficiently by:
1. Running each scenario (strategy + interval) sequentially
2. But using parallel processing WITHIN each scenario for securities

This is more reliable on Windows and still fast because most time
is spent within each scenario processing securities.

Expected speedup: ~3-4x compared to fully sequential

Outputs:
- sweep_results.csv: Comprehensive metrics for all scenarios
- per_security_summary.csv: Per-security metrics across all scenarios
- per_security_pnl_pivot.csv: Pivot table of P&L by security
- comparison_table.csv: Side-by-side strategy comparison
- comprehensive_comparison.png: 12-panel comparison plot
- cumulative_pnl_by_strategy.png: P&L over time by strategy
- pnl_by_security_plots/: Per-security P&L plots for each scenario

Usage:
    # Quick test (5 sheets, 3 intervals)
    python scripts/fast_sweep.py --max-sheets 5 --intervals 30 60 120
    
    # Full production run
    python scripts/fast_sweep.py --intervals 10 30 60 120 300 600
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from multiprocessing import cpu_count
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config_loader import load_strategy_config
from src.parquet_utils import ensure_parquet_data
from src.parallel_backtest import run_parallel_backtest_parquet


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_strategy_name(strategy: str) -> str:
    """Format strategy name for display."""
    name_map = {
        'v1': 'V1 Baseline',
        'v2': 'V2 Price Follow',
        'v2_1': 'V2.1 Stop Loss',
        'v3': 'V3 Liquidity'
    }
    return name_map.get(strategy, strategy.upper())


def calculate_metrics(trades: list) -> dict:
    """Calculate comprehensive metrics from trade list."""
    if not trades:
        return {
            'total_trades': 0, 'total_pnl': 0, 'sharpe_ratio': 0,
            'max_drawdown': 0, 'max_drawdown_pct': 0, 'calmar_ratio': 0,
            'win_rate': 0, 'profit_factor': 0, 'avg_pnl_per_trade': 0
        }
    
    df = pd.DataFrame(trades)
    
    # Basic metrics
    total_trades = len(df)
    total_pnl = df['realized_pnl'].sum() if 'realized_pnl' in df.columns else df.get('pnl', pd.Series([0])).iloc[-1]
    
    # P&L series
    if 'pnl' in df.columns:
        cumulative_pnl = df['pnl']
    elif 'realized_pnl' in df.columns:
        cumulative_pnl = df['realized_pnl'].cumsum()
    else:
        cumulative_pnl = pd.Series([0])
    
    # Daily returns
    if 'timestamp' in df.columns:
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        daily_pnl = df.groupby('date')['realized_pnl'].sum() if 'realized_pnl' in df.columns else pd.Series([0])
    else:
        daily_pnl = pd.Series([total_pnl])
    
    # Sharpe ratio (annualized)
    if len(daily_pnl) > 1 and daily_pnl.std() > 0:
        sharpe_ratio = (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0
    
    # Max drawdown
    if len(cumulative_pnl) > 0:
        running_max = cumulative_pnl.cummax()
        drawdown = cumulative_pnl - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / running_max.replace(0, 1).max()) * 100 if running_max.max() > 0 else 0
    else:
        max_drawdown = 0
        max_drawdown_pct = 0
    
    # Calmar ratio
    if max_drawdown < 0:
        calmar_ratio = total_pnl / abs(max_drawdown)
    else:
        calmar_ratio = total_pnl if total_pnl > 0 else 0
    
    # Win/loss metrics
    if 'realized_pnl' in df.columns:
        wins = df[df['realized_pnl'] > 0]
        losses = df[df['realized_pnl'] < 0]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        
        gross_profit = wins['realized_pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['realized_pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
    else:
        win_rate = 0
        profit_factor = 0
    
    avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
    
    return {
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': max_drawdown_pct,
        'calmar_ratio': calmar_ratio,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_pnl_per_trade': avg_pnl_per_trade
    }


def get_handler_info(strategy: str) -> tuple:
    """Get handler module and function for a strategy."""
    strategy_map = {
        'v1': ('v1_baseline', 'create_v1_handler'),
        'v2': ('v2_price_follow_qty_cooldown', 'create_v2_price_follow_qty_cooldown_handler'),
        'v2_1': ('v2_1_stop_loss', 'create_v2_1_stop_loss_handler'),
    }
    
    folder, function = strategy_map.get(strategy, (None, None))
    if folder:
        return f"src.strategies.{folder}.handler", function
    return None, None


def run_single_scenario(
    strategy: str,
    interval_sec: int,
    base_config: dict,
    parquet_dir: str,
    max_sheets: int,
    chunk_size: int,
    workers: int,
    output_dir: str,
    collect_trades: bool = False
) -> dict:
    """Run a single sweep scenario using parallel backtest for securities."""
    
    scenario_id = f"{strategy}_{interval_sec}s"
    start_time = time.time()
    
    # Modify config with interval
    config = {}
    for security, sec_config in base_config.items():
        config[security] = sec_config.copy()
        config[security]['refill_interval_sec'] = interval_sec
    
    # Get handler info
    handler_module, handler_function = get_handler_info(strategy)
    if handler_module is None:
        return {'scenario_id': scenario_id, 'error': f'Unknown strategy: {strategy}'}
    
    try:
        # Use the existing parallel backtest infrastructure
        results = run_parallel_backtest_parquet(
            parquet_dir=parquet_dir,
            handler_module=handler_module,
            handler_function=handler_function,
            config=config,
            max_files=max_sheets,
            chunk_size=chunk_size,
            max_workers=workers,
            output_dir=None,  # Don't write CSVs for each security
            write_csv=False
        )
        
        # Aggregate all trades
        all_trades = []
        per_security_metrics = {}
        per_security_trades = {}  # For plotting
        total_trades = 0
        
        for security, sec_result in results.items():
            trades = sec_result.get('trades', [])
            all_trades.extend(trades)
            total_trades += len(trades)
            
            sec_pnl = sum(t.get('realized_pnl', 0) for t in trades) if trades else sec_result.get('pnl', 0)
            
            # Calculate per-security metrics
            sec_metrics = calculate_metrics(trades)
            per_security_metrics[security] = {
                'trades': len(trades),
                'pnl': sec_pnl,
                'position': sec_result.get('position', 0),
                'sharpe_ratio': sec_metrics.get('sharpe_ratio', 0),
                'max_drawdown': sec_metrics.get('max_drawdown', 0),
                'max_drawdown_pct': sec_metrics.get('max_drawdown_pct', 0),
                'win_rate': sec_metrics.get('win_rate', 0)
            }
            
            # Store trades for plotting (optional)
            if collect_trades and trades:
                per_security_trades[security] = trades
        
        # Calculate aggregate metrics
        metrics = calculate_metrics(all_trades)
        
        elapsed = time.time() - start_time
        
        # Save per-security results
        scenario_output_dir = Path(output_dir) / scenario_id
        scenario_output_dir.mkdir(parents=True, exist_ok=True)
        
        summary_df = pd.DataFrame([
            {'security': sec, **data} for sec, data in per_security_metrics.items()
        ])
        summary_df.to_csv(scenario_output_dir / 'per_security_summary.csv', index=False)
        
        # Also save trade files if collecting trades (needed for cumulative P&L plots)
        if collect_trades and per_security_trades:
            for security, trades in per_security_trades.items():
                if trades:
                    trades_df = pd.DataFrame(trades)
                    trades_df.to_csv(scenario_output_dir / f'{security}_trades.csv', index=False)
        
        result = {
            'scenario_id': scenario_id,
            'strategy': strategy,
            'interval_sec': interval_sec,
            'elapsed': elapsed,
            'total_trades': total_trades,
            'securities': len(results),
            'metrics': metrics,
            'per_security': per_security_metrics
        }
        
        if collect_trades:
            result['all_trades'] = all_trades
            result['per_security_trades'] = per_security_trades
        
        return result
        
    except Exception as e:
        import traceback
        return {
            'scenario_id': scenario_id,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


# =============================================================================
# PLOTTING FUNCTIONS
# =============================================================================

def plot_cumulative_pnl_by_strategy(all_results: dict, output_dir: Path):
    """Plot cumulative P&L over time for each strategy, one subplot per strategy.
    
    NOTE: The 'pnl' field in each trade is per-security cumulative P&L. 
    To get true portfolio P&L, we must sum realized_pnl across all trades sorted by time.
    """
    
    strategies = list(set(r['strategy'] for r in all_results.values() if 'error' not in r))
    if not strategies:
        print("  No results to plot")
        return
    
    # Color map for intervals
    colors = plt.cm.viridis(np.linspace(0, 0.9, 10))
    
    fig, axes = plt.subplots(1, len(strategies), figsize=(7 * len(strategies), 5))
    if len(strategies) == 1:
        axes = [axes]
    
    for ax, strategy in zip(axes, sorted(strategies)):
        ax.set_title(f'{format_strategy_name(strategy)} - Cumulative P&L')
        
        # Get all intervals for this strategy
        strat_results = {k: v for k, v in all_results.items() 
                        if 'error' not in v and v['strategy'] == strategy}
        
        if not strat_results:
            continue
        
        intervals = sorted(set(v['interval_sec'] for v in strat_results.values()))
        
        for i, interval in enumerate(intervals):
            key = f"{strategy}_{interval}s"
            if key not in all_results or 'all_trades' not in all_results[key]:
                continue
            
            trades = all_results[key]['all_trades']
            if not trades:
                continue
            
            df = pd.DataFrame(trades)
            if 'realized_pnl' not in df.columns:
                continue
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate TRUE portfolio cumulative P&L by summing realized_pnl across ALL securities
            # The 'pnl' column is per-security cumulative - NOT what we want for portfolio view
            df['portfolio_cumulative_pnl'] = df['realized_pnl'].cumsum()
            
            color = colors[i % len(colors)]
            ax.plot(df['timestamp'], df['portfolio_cumulative_pnl'], label=f'{interval}s', 
                   color=color, alpha=0.8, linewidth=1)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative P&L (AED)')
        ax.legend(title='Interval', loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'cumulative_pnl_by_strategy.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: cumulative_pnl_by_strategy.png")


def plot_pnl_by_security(all_results: dict, output_dir: Path):
    """Create per-security P&L plots for each scenario."""
    
    plots_dir = output_dir / 'pnl_by_security_plots'
    plots_dir.mkdir(exist_ok=True)
    
    colors = plt.cm.tab20(np.linspace(0, 1, 20))
    plot_count = 0
    
    for scenario_id, result in all_results.items():
        if 'error' in result or 'per_security_trades' not in result:
            continue
        
        per_security_trades = result['per_security_trades']
        if not per_security_trades:
            continue
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        strategy = result['strategy']
        interval = result['interval_sec']
        
        for i, (security, trades) in enumerate(sorted(per_security_trades.items())):
            if not trades:
                continue
            
            df = pd.DataFrame(trades)
            if 'pnl' not in df.columns:
                continue
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            color = colors[i % len(colors)]
            ax.plot(df['timestamp'], df['pnl'], label=security, 
                   color=color, alpha=0.7, linewidth=1)
        
        ax.set_title(f'{format_strategy_name(strategy)} @ {interval}s - P&L by Security')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative P&L (AED)')
        ax.legend(loc='upper left', ncol=4, fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        filename = f'{strategy}_{interval}s_pnl_by_security.png'
        plt.savefig(plots_dir / filename, dpi=150, bbox_inches='tight')
        plt.close()
        plot_count += 1
    
    print(f"  ✓ Saved: {plot_count} per-security plots to pnl_by_security_plots/")


def create_comparison_plots(results_df: pd.DataFrame, output_dir: Path):
    """Create 12-panel comprehensive comparison plot."""
    
    if results_df.empty:
        print("  No data for comparison plots")
        return
    
    strategies = results_df['strategy'].unique()
    colors = {'v1': '#1f77b4', 'v2': '#ff7f0e', 'v2_1': '#2ca02c', 'v3': '#d62728'}
    
    fig = plt.figure(figsize=(20, 16))
    gs = gridspec.GridSpec(4, 3, figure=fig, hspace=0.35, wspace=0.25)
    
    # Helper for bar plots
    def bar_plot(ax, metric, title, ylabel, format_func=lambda x: f'{x:,.0f}'):
        x = np.arange(len(results_df['interval_sec'].unique()))
        intervals = sorted(results_df['interval_sec'].unique())
        width = 0.25
        
        for i, strategy in enumerate(strategies):
            strat_data = results_df[results_df['strategy'] == strategy]
            strat_data = strat_data.set_index('interval_sec').reindex(intervals)
            values = strat_data[metric].fillna(0).values
            ax.bar(x + i * width, values, width, label=format_strategy_name(strategy), 
                  color=colors.get(strategy, '#333'))
        
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_xticks(x + width * (len(strategies) - 1) / 2)
        ax.set_xticklabels([f'{i}s' for i in intervals], fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, axis='y', alpha=0.3)
    
    # Plot 1: Total P&L
    ax1 = fig.add_subplot(gs[0, 0])
    bar_plot(ax1, 'total_pnl', 'Total P&L', 'P&L (AED)')
    
    # Plot 2: Total Trades
    ax2 = fig.add_subplot(gs[0, 1])
    bar_plot(ax2, 'total_trades', 'Total Trades', 'Trades')
    
    # Plot 3: Sharpe Ratio
    ax3 = fig.add_subplot(gs[0, 2])
    bar_plot(ax3, 'sharpe_ratio', 'Sharpe Ratio', 'Sharpe')
    
    # Plot 4: Max Drawdown %
    ax4 = fig.add_subplot(gs[1, 0])
    bar_plot(ax4, 'max_drawdown_pct', 'Max Drawdown %', 'Drawdown %')
    
    # Plot 5: Avg P&L per Trade
    ax5 = fig.add_subplot(gs[1, 1])
    bar_plot(ax5, 'avg_pnl_per_trade', 'Avg P&L per Trade', 'P&L/Trade (AED)')
    
    # Plot 6: Win Rate
    ax6 = fig.add_subplot(gs[1, 2])
    bar_plot(ax6, 'win_rate', 'Win Rate', 'Win Rate %')
    
    # Plot 7: Calmar Ratio
    ax7 = fig.add_subplot(gs[2, 0])
    bar_plot(ax7, 'calmar_ratio', 'Calmar Ratio', 'Calmar')
    
    # Plot 8: Profit Factor
    ax8 = fig.add_subplot(gs[2, 1])
    bar_plot(ax8, 'profit_factor', 'Profit Factor', 'Profit Factor')
    
    # Plot 9: Risk-Return Scatter
    ax9 = fig.add_subplot(gs[2, 2])
    for strategy in strategies:
        strat_data = results_df[results_df['strategy'] == strategy]
        ax9.scatter(abs(strat_data['max_drawdown_pct']), strat_data['total_pnl'],
                   c=colors.get(strategy, '#333'), label=format_strategy_name(strategy),
                   s=100, alpha=0.7)
        # Label points with interval
        for _, row in strat_data.iterrows():
            ax9.annotate(f"{int(row['interval_sec'])}s", 
                        (abs(row['max_drawdown_pct']), row['total_pnl']),
                        fontsize=7, alpha=0.8)
    ax9.set_xlabel('Max Drawdown % (abs)')
    ax9.set_ylabel('Total P&L (AED)')
    ax9.set_title('Risk-Return Trade-off')
    ax9.legend(fontsize=8)
    ax9.grid(True, alpha=0.3)
    
    # Plot 10: Sharpe Trend Line
    ax10 = fig.add_subplot(gs[3, 0])
    for strategy in strategies:
        strat_data = results_df[results_df['strategy'] == strategy].sort_values('interval_sec')
        ax10.plot(strat_data['interval_sec'], strat_data['sharpe_ratio'], 
                 'o-', label=format_strategy_name(strategy), color=colors.get(strategy, '#333'))
    ax10.set_xlabel('Interval (sec)')
    ax10.set_ylabel('Sharpe Ratio')
    ax10.set_title('Sharpe Ratio vs Interval')
    ax10.legend(fontsize=8)
    ax10.grid(True, alpha=0.3)
    
    # Plot 11: P&L Trend Line
    ax11 = fig.add_subplot(gs[3, 1])
    for strategy in strategies:
        strat_data = results_df[results_df['strategy'] == strategy].sort_values('interval_sec')
        ax11.plot(strat_data['interval_sec'], strat_data['total_pnl'], 
                 'o-', label=format_strategy_name(strategy), color=colors.get(strategy, '#333'))
    ax11.set_xlabel('Interval (sec)')
    ax11.set_ylabel('Total P&L (AED)')
    ax11.set_title('P&L vs Interval')
    ax11.legend(fontsize=8)
    ax11.grid(True, alpha=0.3)
    
    # Plot 12: Trade Count Trend
    ax12 = fig.add_subplot(gs[3, 2])
    for strategy in strategies:
        strat_data = results_df[results_df['strategy'] == strategy].sort_values('interval_sec')
        ax12.plot(strat_data['interval_sec'], strat_data['total_trades'], 
                 'o-', label=format_strategy_name(strategy), color=colors.get(strategy, '#333'))
    ax12.set_xlabel('Interval (sec)')
    ax12.set_ylabel('Total Trades')
    ax12.set_title('Trade Count vs Interval')
    ax12.legend(fontsize=8)
    ax12.grid(True, alpha=0.3)
    
    plt.savefig(output_dir / 'comprehensive_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: comprehensive_comparison.png")


def generate_comparison_table(results_df: pd.DataFrame, output_dir: Path):
    """Generate strategy comparison table (side-by-side)."""
    
    if results_df.empty:
        print("  No data for comparison table")
        return
    
    strategies = sorted(results_df['strategy'].unique())
    intervals = sorted(results_df['interval_sec'].unique())
    
    rows = []
    for interval in intervals:
        row = {'interval_sec': interval}
        for strategy in strategies:
            strat_data = results_df[(results_df['strategy'] == strategy) & 
                                   (results_df['interval_sec'] == interval)]
            if not strat_data.empty:
                r = strat_data.iloc[0]
                prefix = strategy.upper().replace('_', '')
                row[f'{prefix}_pnl'] = r['total_pnl']
                row[f'{prefix}_trades'] = r['total_trades']
                row[f'{prefix}_sharpe'] = r['sharpe_ratio']
                row[f'{prefix}_dd_pct'] = r['max_drawdown_pct']
                row[f'{prefix}_win_pct'] = r['win_rate']
        rows.append(row)
    
    comparison_df = pd.DataFrame(rows)
    comparison_df.to_csv(output_dir / 'comparison_table.csv', index=False)
    print(f"  ✓ Saved: comparison_table.csv")
    
    return comparison_df


def generate_per_security_pivot(all_results: dict, output_dir: Path):
    """Generate pivot table of P&L by security."""
    
    rows = []
    for scenario_id, result in all_results.items():
        if 'error' in result:
            continue
        per_security = result.get('per_security', {})
        for security, sec_data in per_security.items():
            rows.append({
                'security': security,
                'scenario': scenario_id,
                'strategy': result['strategy'],
                'interval_sec': result['interval_sec'],
                'pnl': sec_data.get('pnl', 0),
                'trades': sec_data.get('trades', 0)
            })
    
    if not rows:
        print("  No per-security data for pivot")
        return
    
    df = pd.DataFrame(rows)
    
    # Save full per-security summary
    df.to_csv(output_dir / 'per_security_summary.csv', index=False)
    print(f"  ✓ Saved: per_security_summary.csv")
    
    # Create pivot table
    pivot = df.pivot_table(
        index='security',
        columns='scenario',
        values='pnl',
        aggfunc='sum'
    )
    pivot.to_csv(output_dir / 'per_security_pnl_pivot.csv')
    print(f"  ✓ Saved: per_security_pnl_pivot.csv")


def run_sweep(
    strategies: list,
    intervals: list,
    v1_config_path: str,
    v2_config_path: str,
    parquet_dir: str,
    output_dir: str,
    max_sheets: int = None,
    chunk_size: int = 100000,
    workers: int = None,
    collect_trades: bool = True
) -> pd.DataFrame:
    """Run parameter sweep across strategies and intervals.
    
    Args:
        collect_trades: If True, collect trades for plotting (uses more memory)
    """
    
    if workers is None:
        workers = min(16, cpu_count())
    
    start_time = time.time()
    
    print("=" * 80)
    print("FAST PARAMETER SWEEP")
    print("=" * 80)
    print(f"Strategies: {strategies}")
    print(f"Intervals: {intervals}")
    print(f"Total scenarios: {len(strategies) * len(intervals)}")
    print(f"Workers per scenario: {workers}")
    print(f"Max sheets: {max_sheets or 'All'}")
    print(f"Output: {output_dir}")
    print(f"Collect trades for plots: {collect_trades}")
    print("=" * 80)
    
    # Load configs
    v1_config = load_strategy_config(v1_config_path)
    v2_config = load_strategy_config(v2_config_path)
    
    all_results = {}  # Store all results for plotting
    total_scenarios = len(strategies) * len(intervals)
    completed = 0
    
    for strategy in strategies:
        base_config = v1_config if strategy == 'v1' else v2_config
        
        for interval in intervals:
            completed += 1
            scenario_id = f"{strategy}_{interval}s"
            
            print(f"\n[{completed}/{total_scenarios}] Running {scenario_id}...")
            
            result = run_single_scenario(
                strategy=strategy,
                interval_sec=interval,
                base_config=base_config,
                parquet_dir=parquet_dir,
                max_sheets=max_sheets,
                chunk_size=chunk_size,
                workers=workers,
                output_dir=output_dir,
                collect_trades=collect_trades
            )
            
            if 'error' in result:
                print(f"  [X] Error: {result['error']}")
            else:
                metrics = result.get('metrics', {})
                print(f"  [OK] {result['total_trades']:,} trades, "
                      f"P&L: {metrics.get('total_pnl', 0):,.0f}, "
                      f"Sharpe: {metrics.get('sharpe_ratio', 0):.2f}, "
                      f"in {result['elapsed']:.1f}s")
            
            all_results[scenario_id] = result
    
    total_elapsed = time.time() - start_time
    
    # Build results DataFrame
    rows = []
    for r in all_results.values():
        if 'error' not in r:
            metrics = r.get('metrics', {})
            rows.append({
                'strategy': r['strategy'],
                'interval_sec': r['interval_sec'],
                'total_trades': r['total_trades'],
                'total_pnl': metrics.get('total_pnl', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                'calmar_ratio': metrics.get('calmar_ratio', 0),
                'win_rate': metrics.get('win_rate', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'avg_pnl_per_trade': metrics.get('avg_pnl_per_trade', 0),
                'elapsed_sec': r['elapsed'],
                'securities': r['securities']
            })
    
    results_df = pd.DataFrame(rows)
    
    if not results_df.empty:
        results_df = results_df.sort_values(['strategy', 'interval_sec'])
    
    # Save outputs
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)
    
    # 1. Main results CSV (comprehensive_results.csv equivalent)
    results_df.to_csv(output_path / 'sweep_results.csv', index=False)
    print(f"  ✓ Saved: sweep_results.csv")
    
    # 2. Per-security summary and pivot
    generate_per_security_pivot(all_results, output_path)
    
    # 3. Comparison table
    generate_comparison_table(results_df, output_path)
    
    # 4. Plots (if trades collected)
    if collect_trades:
        print("\nGenerating plots...")
        
        # Cumulative P&L by strategy
        plot_cumulative_pnl_by_strategy(all_results, output_path)
        
        # Per-security P&L plots
        plot_pnl_by_security(all_results, output_path)
        
        # Comprehensive comparison (12-panel)
        create_comparison_plots(results_df, output_path)
    else:
        print("\n  (Plots skipped - run with --plots to generate)")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SWEEP COMPLETE")
    print("=" * 80)
    print(f"Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
    print(f"Scenarios: {len(all_results)} completed")
    print(f"Results saved to: {output_dir}")
    
    if not results_df.empty:
        print("\n" + "=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)
        print(results_df.to_string(index=False))
        
        print("\n" + "-" * 80)
        print("BEST CONFIGURATIONS BY P&L")
        print("-" * 80)
        for strategy in results_df['strategy'].unique():
            strat_df = results_df[results_df['strategy'] == strategy]
            best = strat_df.loc[strat_df['total_pnl'].idxmax()]
            print(f"\n{format_strategy_name(strategy)}:")
            print(f"  Best interval: {int(best['interval_sec'])}s")
            print(f"  P&L: {best['total_pnl']:,.0f} AED")
            print(f"  Sharpe: {best['sharpe_ratio']:.2f}")
            print(f"  Trades: {int(best['total_trades']):,}")
            print(f"  Win Rate: {best['win_rate']:.1f}%")
    
    print("\n" + "=" * 80)
    print("OUTPUT FILES")
    print("=" * 80)
    print(f"  sweep_results.csv          - Comprehensive metrics")
    print(f"  per_security_summary.csv   - Per-security breakdown")
    print(f"  per_security_pnl_pivot.csv - P&L pivot by security")
    print(f"  comparison_table.csv       - Strategy comparison")
    if collect_trades:
        print(f"  comprehensive_comparison.png - 12-panel comparison")
        print(f"  cumulative_pnl_by_strategy.png - P&L over time")
        print(f"  pnl_by_security_plots/     - Per-security plots")
    print("=" * 80)
    
    return results_df


def main():
    parser = argparse.ArgumentParser(
        description='Fast parameter sweep for market-making strategies'
    )
    
    parser.add_argument('--strategies', nargs='+', default=['v1', 'v2', 'v2_1'],
                       help='Strategies to sweep (default: v1 v2 v2_1)')
    parser.add_argument('--intervals', nargs='+', type=int, 
                       default=[30, 60, 120, 180, 300],
                       help='Refill intervals in seconds')
    parser.add_argument('--v1-config', default='configs/v1_baseline_config.json',
                       help='Path to V1 config')
    parser.add_argument('--v2-config', default='configs/v2_price_follow_qty_cooldown_config.json',
                       help='Path to V2/V2.1 config')
    parser.add_argument('--output-dir', default='output/sweep',
                       help='Output directory')
    parser.add_argument('--max-sheets', type=int, default=None,
                       help='Limit securities for testing')
    parser.add_argument('--chunk-size', type=int, default=100000,
                       help='Rows per chunk')
    parser.add_argument('--workers', type=int, default=None,
                       help='Workers for parallel processing')
    parser.add_argument('--no-plots', action='store_true',
                       help='Skip plot generation (faster, less memory)')
    
    args = parser.parse_args()
    
    # Ensure Parquet data
    print("Checking data format...\n")
    try:
        parquet_dir = ensure_parquet_data(
            excel_path='data/raw/TickData.xlsx',
            parquet_dir='data/parquet',
            validate_data=True
        )
        print(f"Using Parquet format: {parquet_dir}\n")
    except Exception as e:
        print(f"ERROR: Could not setup Parquet data: {e}")
        sys.exit(1)
    
    # Run sweep
    results_df = run_sweep(
        strategies=args.strategies,
        intervals=args.intervals,
        v1_config_path=args.v1_config,
        v2_config_path=args.v2_config,
        parquet_dir=parquet_dir,
        output_dir=args.output_dir,
        max_sheets=args.max_sheets,
        chunk_size=args.chunk_size,
        workers=args.workers,
        collect_trades=not args.no_plots
    )
    
    return results_df


if __name__ == '__main__':
    main()
