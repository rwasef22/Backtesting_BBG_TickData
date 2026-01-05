"""Comprehensive parameter sweep for both V1 and V2 strategies.

This script runs parameter sweeps on both strategies with:
- Progress checkpointing (resume on interruption)
- Advanced metrics: Sharpe ratio, max drawdown, Calmar ratio
- Per-security analysis
- Consolidated comparison report

Usage:
    python scripts/comprehensive_sweep.py --max-sheets 5  # Quick test
    python scripts/comprehensive_sweep.py  # Full run
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.mm_handler import create_mm_handler
from src.strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from src.strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from src.strategies.v3_liquidity_monitor.handler import create_v3_liquidity_monitor_handler
from src.parquet_utils import ensure_parquet_data


class AdvancedMetricsCalculator:
    """Calculate advanced investment metrics from trade history."""
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio.
        
        Args:
            returns: Series of daily returns
            risk_free_rate: Annual risk-free rate (default: 0)
            
        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = (excess_returns.mean() / returns.std()) * np.sqrt(252)
        return sharpe
    
    @staticmethod
    def calculate_max_drawdown(cumulative_pnl: pd.Series) -> tuple:
        """Calculate maximum drawdown and recovery info.
        
        Args:
            cumulative_pnl: Series of cumulative P&L values
            
        Returns:
            Tuple of (max_drawdown, max_drawdown_pct, duration_days)
        """
        if len(cumulative_pnl) == 0:
            return 0.0, 0.0, 0
        
        # Calculate running maximum
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_dd = drawdown.min()
        
        # Calculate percentage drawdown
        max_dd_pct = (max_dd / running_max.loc[drawdown.idxmin()]) * 100 if running_max.loc[drawdown.idxmin()] != 0 else 0
        
        # Find drawdown duration
        in_drawdown = drawdown < 0
        if in_drawdown.any():
            dd_periods = in_drawdown.astype(int).groupby((in_drawdown != in_drawdown.shift()).cumsum()).sum()
            max_dd_duration = dd_periods.max() if len(dd_periods) > 0 else 0
        else:
            max_dd_duration = 0
        
        return max_dd, max_dd_pct, max_dd_duration
    
    @staticmethod
    def calculate_calmar_ratio(returns: pd.Series, cumulative_pnl: pd.Series) -> float:
        """Calculate Calmar ratio (annualized return / max drawdown).
        
        Args:
            returns: Series of daily returns
            cumulative_pnl: Series of cumulative P&L
            
        Returns:
            Calmar ratio
        """
        if len(returns) == 0:
            return 0.0
        
        annual_return = returns.mean() * 252
        _, max_dd_pct, _ = AdvancedMetricsCalculator.calculate_max_drawdown(cumulative_pnl)
        
        if abs(max_dd_pct) < 0.001:  # Avoid division by zero
            return 0.0
        
        return (annual_return / abs(max_dd_pct)) * 100
    
    @staticmethod
    def calculate_win_rate(trades: list) -> dict:
        """Calculate win rate and related statistics.
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            Dictionary with win/loss statistics
        """
        if not trades:
            return {
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'total_wins': 0,
                'total_losses': 0
            }
        
        pnls = [t['realized_pnl'] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        return {
            'win_rate': (len(wins) / len(pnls) * 100) if pnls else 0.0,
            'loss_rate': (len(losses) / len(pnls) * 100) if pnls else 0.0,
            'avg_win': np.mean(wins) if wins else 0.0,
            'avg_loss': np.mean(losses) if losses else 0.0,
            'profit_factor': (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else 0.0,
            'total_wins': len(wins),
            'total_losses': len(losses)
        }


def create_config_with_interval(base_config: dict, interval_sec: int) -> dict:
    """Create config with specified refill interval."""
    new_config = {}
    for security, params in base_config.items():
        new_params = params.copy()
        new_params['refill_interval_sec'] = interval_sec
        new_config[security] = new_params
    return new_config


def format_strategy_name(strategy: str) -> str:
    """Format strategy name for display (e.g., 'v2_1' -> 'V2.1')."""
    return strategy.replace('_', '.').upper()


def compute_per_security_metrics(results: dict, interval_sec: int, strategy: str) -> list:
    """Compute metrics for each individual security.
    
    Args:
        results: Backtest results dictionary
        interval_sec: Refill interval used
        strategy: Strategy name ('v1' or 'v2')
        
    Returns:
        List of dictionaries with per-security metrics
    """
    calc = AdvancedMetricsCalculator()
    per_security_metrics = []
    
    for security, data in results.items():
        trades = data.get('trades', [])
        if len(trades) == 0:
            continue
        
        # Basic metrics
        pnl = data.get('pnl', 0.0)
        position = data.get('position', 0)
        num_trades = len(trades)
        
        # Calculate volume
        volume = sum(t['fill_price'] * t['fill_qty'] for t in trades)
        
        # Time series analysis
        trades_df = pd.DataFrame(trades)
        trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
        trades_df = trades_df.sort_values('timestamp')
        trades_df['cumulative_pnl'] = trades_df['realized_pnl'].cumsum()
        
        # Daily aggregation
        daily = trades_df.groupby(trades_df['timestamp'].dt.date).agg({
            'realized_pnl': 'sum',
            'cumulative_pnl': 'last'
        })
        
        # Calculate metrics
        sharpe = calc.calculate_sharpe_ratio(daily['realized_pnl'])
        max_dd, max_dd_pct, dd_duration = calc.calculate_max_drawdown(daily['cumulative_pnl'])
        calmar = calc.calculate_calmar_ratio(daily['realized_pnl'], daily['cumulative_pnl'])
        win_stats = calc.calculate_win_rate(trades)
        
        per_security_metrics.append({
            'strategy': strategy,
            'interval_sec': interval_sec,
            'security': security,
            'trades': num_trades,
            'pnl': pnl,
            'volume': volume,
            'position': position,
            'avg_pnl_per_trade': pnl / num_trades if num_trades > 0 else 0,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'calmar_ratio': calmar,
            'win_rate': win_stats['win_rate'],
            'profit_factor': win_stats['profit_factor'],
            'trading_days': len(daily),
            'trades_per_day': num_trades / len(daily) if len(daily) > 0 else 0
        })
    
    return per_security_metrics


def compute_comprehensive_metrics(results: dict, interval_sec: int, strategy: str) -> dict:
    """Compute comprehensive metrics including advanced investment metrics.
    
    Args:
        results: Backtest results dictionary
        interval_sec: Refill interval used
        strategy: Strategy name ('v1' or 'v2')
        
    Returns:
        Dictionary with comprehensive metrics
    """
    calc = AdvancedMetricsCalculator()
    
    # Aggregate basic metrics
    total_trades = 0
    total_pnl = 0.0
    total_volume = 0.0
    securities_traded = 0
    
    # Collect all trades for time-series analysis
    all_trades = []
    
    for security, data in results.items():
        trades = data.get('trades', [])
        if len(trades) > 0:
            securities_traded += 1
            total_trades += len(trades)
            total_pnl += data.get('pnl', 0.0)
            
            for trade in trades:
                trade['security'] = security
                all_trades.append(trade)
                total_volume += trade['fill_price'] * trade['fill_qty']
    
    # Create trade time series for advanced metrics
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
        trades_df = trades_df.sort_values('timestamp')
        
        # Calculate cumulative P&L
        trades_df['cumulative_pnl'] = trades_df['realized_pnl'].cumsum()
        
        # Daily aggregation for Sharpe/drawdown
        daily = trades_df.groupby(trades_df['timestamp'].dt.date).agg({
            'realized_pnl': 'sum',
            'cumulative_pnl': 'last'
        })
        
        # Calculate returns
        daily['returns'] = daily['realized_pnl']
        
        # Advanced metrics
        sharpe = calc.calculate_sharpe_ratio(daily['returns'])
        max_dd, max_dd_pct, dd_duration = calc.calculate_max_drawdown(daily['cumulative_pnl'])
        calmar = calc.calculate_calmar_ratio(daily['returns'], daily['cumulative_pnl'])
        win_stats = calc.calculate_win_rate(all_trades)
        
        # Additional metrics
        avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
        trading_days = len(daily)
        trades_per_day = total_trades / trading_days if trading_days > 0 else 0
        
    else:
        sharpe = max_dd = max_dd_pct = dd_duration = calmar = 0.0
        win_stats = calc.calculate_win_rate([])
        avg_trade_size = trading_days = trades_per_day = 0
    
    return {
        'strategy': strategy,
        'interval_sec': interval_sec,
        'interval_min': interval_sec / 60,
        
        # Basic metrics
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'total_volume': total_volume,
        'securities_traded': securities_traded,
        'avg_pnl_per_trade': total_pnl / total_trades if total_trades > 0 else 0,
        'avg_pnl_per_security': total_pnl / securities_traded if securities_traded > 0 else 0,
        'avg_trade_size': avg_trade_size,
        
        # Trading activity
        'trading_days': trading_days,
        'trades_per_day': trades_per_day,
        
        # Risk metrics
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'max_drawdown_pct': max_dd_pct,
        'drawdown_duration_days': dd_duration,
        'calmar_ratio': calmar,
        
        # Win/Loss statistics
        'win_rate': win_stats['win_rate'],
        'loss_rate': win_stats['loss_rate'],
        'avg_win': win_stats['avg_win'],
        'avg_loss': win_stats['avg_loss'],
        'profit_factor': win_stats['profit_factor'],
        'total_wins': win_stats['total_wins'],
        'total_losses': win_stats['total_losses']
    }


def compute_comprehensive_metrics_with_params(results: dict, param_value: float, strategy: str, param_name: str) -> dict:
    """Compute comprehensive metrics with flexible parameter tracking.
    
    Args:
        results: Backtest results dictionary
        param_value: Parameter value used
        strategy: Strategy name
        param_name: Name of the parameter being swept
        
    Returns:
        Dictionary with comprehensive metrics
    """
    # Use existing compute function
    if param_name == 'interval_sec':
        metrics = compute_comprehensive_metrics(results, int(param_value), strategy)
    else:
        metrics = compute_comprehensive_metrics(results, 60, strategy)  # Default interval for display
        metrics[param_name] = param_value
        # Keep interval_sec for backward compatibility
        if param_name != 'interval_sec' and 'interval_sec' not in metrics:
            metrics['interval_sec'] = 60
    
    return metrics


def compute_per_security_metrics_with_params(results: dict, param_value: float, strategy: str, param_name: str) -> list:
    """Compute per-security metrics with flexible parameter tracking.
    
    Args:
        results: Backtest results dictionary
        param_value: Parameter value used
        strategy: Strategy name
        param_name: Name of the parameter being swept
        
    Returns:
        List of per-security metric dictionaries
    """
    if param_name == 'interval_sec':
        metrics = compute_per_security_metrics(results, int(param_value), strategy)
    else:
        metrics = compute_per_security_metrics(results, 60, strategy)
        for m in metrics:
            m[param_name] = param_value
    
    return metrics


def run_single_backtest_with_params(strategy: str, param_config: dict, base_config: dict,
                                    data_path: str, max_sheets: int = None,
                                    chunk_size: int = 100000, sheet_names_filter: list = None) -> dict:
    """Run single backtest with flexible parameter configuration.
    
    Args:
        strategy: 'v1', 'v2', 'v2_1', or 'v3'
        param_config: Dictionary of parameters to set (e.g., {'refill_interval_sec': 60})
        base_config: Base configuration
        data_path: Path to data file
        max_sheets: Max sheets to process
        chunk_size: Chunk size
        sheet_names_filter: List of sheet names to process (optional)
        
    Returns:
        Backtest results dictionary
    """
    # Create config with custom parameters
    config = {}
    for security, sec_config in base_config.items():
        config[security] = sec_config.copy()
        config[security].update(param_config)
    
    # Create appropriate handler
    if strategy == 'v1':
        handler = create_mm_handler(config=config)
    elif strategy == 'v2':
        handler = create_v2_price_follow_qty_cooldown_handler(config=config)
    elif strategy == 'v2_1':
        handler = create_v2_1_stop_loss_handler(config=config)
    elif strategy == 'v3':
        handler = create_v3_liquidity_monitor_handler(config=config)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    # Run backtest
    start_time = time.time()
    backtest = MarketMakingBacktest()
    
    try:
        # Check if we should use Parquet (from main's data_path determination)
        if data_path.endswith('.xlsx'):
            # Excel format
            results = backtest.run_streaming(
                file_path=data_path,
                handler=handler,
                max_sheets=max_sheets,
                chunk_size=chunk_size,
                sheet_names_filter=sheet_names_filter
            )
        else:
            # Parquet format  
            results = backtest.run_parquet_streaming(
                parquet_dir=data_path,
                handler=handler,
                max_files=max_sheets,
                chunk_size=chunk_size
            )
        elapsed = time.time() - start_time
        print(f"✓ Completed in {elapsed:.1f} seconds")
        return results
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def run_single_backtest(strategy: str, interval_sec: int, base_config: dict, 
                       data_path: str, max_sheets: int = None, 
                       chunk_size: int = 100000, sheet_names_filter: list = None) -> dict:
    """Run single backtest for given strategy and interval.
    
    Args:
        strategy: 'v1', 'v2', 'v2_1', or 'v3'
        interval_sec: Refill interval
        base_config: Base configuration
        data_path: Path to data file
        max_sheets: Max sheets to process
        chunk_size: Chunk size
        sheet_names_filter: List of sheet names to process (optional)
        
    Returns:
        Backtest results dictionary
    """
    print(f"\n{'='*80}")
    print(f"Testing {format_strategy_name(strategy)} - Interval: {interval_sec}s ({interval_sec/60:.1f}m)")
    print(f"{'='*80}")
    
    # Create config
    config = create_config_with_interval(base_config, interval_sec)
    
    # Create appropriate handler
    if strategy == 'v1':
        handler = create_mm_handler(config=config)
    elif strategy == 'v2':
        handler = create_v2_price_follow_qty_cooldown_handler(config=config)
    elif strategy == 'v2_1':
        handler = create_v2_1_stop_loss_handler(config=config)
    elif strategy == 'v3':
        handler = create_v3_liquidity_monitor_handler(config=config)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    # Run backtest
    start_time = time.time()
    backtest = MarketMakingBacktest()
    
    try:
        results = backtest.run_streaming(
            file_path=data_path,
            handler=handler,
            max_sheets=max_sheets,
            chunk_size=chunk_size,
            sheet_names_filter=sheet_names_filter
        )
        elapsed = time.time() - start_time
        print(f"✓ Completed in {elapsed:.1f} seconds")
        return results
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def save_checkpoint(metrics_list: list, checkpoint_path: Path):
    """Save progress checkpoint."""
    df = pd.DataFrame(metrics_list)
    df.to_csv(checkpoint_path, index=False)


def load_checkpoint(checkpoint_path: Path) -> list:
    """Load progress from checkpoint."""
    if checkpoint_path.exists():
        df = pd.read_csv(checkpoint_path)
        return df.to_dict('records')
    return []


def plot_cumulative_pnl_by_strategy(all_results: dict, output_dir: Path, strategies: list = None):
    """Plot cumulative PnL over time for each strategy with different lines per interval.
    
    Args:
        all_results: Dictionary mapping (strategy, interval) -> results dict
        output_dir: Output directory
        strategies: List of strategies to plot (default: all available)
    """
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
        ax.set_title(f'{format_strategy_name(strategy)} Strategy: Cumulative P&L Over Time', 
                    fontweight='bold', fontsize=14)
        ax.legend(title='Refill Interval', fontsize=10)
        ax.grid(alpha=0.3)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
    
    plt.tight_layout()
    plot_path = output_dir / 'cumulative_pnl_by_strategy.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved cumulative P&L plot: {plot_path}")
    plt.close()


def plot_pnl_by_security(all_results: dict, output_dir: Path):
    """Plot P&L by security for each strategy-interval combination.
    
    Args:
        all_results: Dictionary mapping (strategy, interval) -> results dict
        output_dir: Output directory
    """
    pnl_plots_dir = output_dir / 'pnl_by_security_plots'
    pnl_plots_dir.mkdir(parents=True, exist_ok=True)
    
    for (strategy, interval), results in sorted(all_results.items()):
        # Collect per-security cumulative P&L
        security_data = {}
        
        for security, data in results.items():
            trades = data.get('trades', [])
            if not trades:
                continue
            
            trades_df = pd.DataFrame(trades)
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
            trades_df = trades_df.sort_values('timestamp')
            trades_df['cumulative_pnl'] = trades_df['realized_pnl'].cumsum()
            
            security_data[security] = trades_df[['timestamp', 'cumulative_pnl']]
        
        if not security_data:
            continue
        
        # Create plot
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = plt.cm.tab20(np.linspace(0, 1, len(security_data)))
        
        for idx, (security, df) in enumerate(sorted(security_data.items())):
            ax.plot(df['timestamp'], df['cumulative_pnl'], 
                   label=security, linewidth=2, alpha=0.7, color=colors[idx])
        
        ax.set_xlabel('Date', fontweight='bold', fontsize=12)
        ax.set_ylabel('Cumulative P&L (AED)', fontweight='bold', fontsize=12)
        ax.set_title(f'{format_strategy_name(strategy)} @ {interval}s: Cumulative P&L by Security', 
                    fontweight='bold', fontsize=14)
        ax.legend(loc='best', fontsize=9, ncol=2)
        ax.grid(alpha=0.3)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        
        plt.tight_layout()
        plot_path = pnl_plots_dir / f'{strategy}_{interval}s_pnl_by_security.png'
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    print(f"✓ Saved {len(all_results)} per-security P&L plots to {pnl_plots_dir.name}/")


def create_comparison_plots(all_metrics_df: pd.DataFrame, output_dir: Path):
    """Create comprehensive comparison plots for all available strategies."""
    
    # Get all available strategies
    strategies = sorted(all_metrics_df['strategy'].unique())
    num_strategies = len(strategies)
    
    # Define colors for up to 6 strategies
    strategy_colors = {
        'v1': 'steelblue',
        'v2': 'coral',
        'v2_1': 'mediumorchid',
        'v3': 'mediumseagreen',
        'v4': 'gold',
        'v5': 'mediumpurple'
    }
    
    # Define markers for scatter plots
    strategy_markers = {
        'v1': 'o',
        'v2': 's',
        'v2_1': 'D',
        'v3': '^',
        'v4': 'P',
        'v5': 'v'
    }
    
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)
    
    # Get strategy data
    strategy_data = {s: all_metrics_df[all_metrics_df['strategy'] == s].sort_values('interval_sec') 
                     for s in strategies}
    
    intervals = sorted(all_metrics_df['interval_sec'].unique())
    x = np.arange(len(intervals))
    width = 0.8 / num_strategies  # Adjust width based on number of strategies
    
    # 1. Total P&L
    ax1 = fig.add_subplot(gs[0, 0])
    for i, strategy in enumerate(strategies):
        offset = width * (i - (num_strategies - 1) / 2)
        ax1.bar(x + offset, strategy_data[strategy]['total_pnl'], width, 
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
               label=format_strategy_name(strategy), color=strategy_colors[strategy], alpha=0.8, edgecolor='black')
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
                        marker=strategy_markers[strategy], label=format_strategy_name(strategy) if i == 0 else '')
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
                 label=format_strategy_name(strategy), color=strategy_colors[strategy])
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
                 label=format_strategy_name(strategy), color=strategy_colors[strategy])
    ax12.set_xlabel('Interval (sec)', fontweight='bold')
    ax12.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax12.set_title('P&L Trend', fontweight='bold', fontsize=12)
    ax12.legend()
    ax12.grid(alpha=0.3)
    ax12.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    # Update title to reflect all strategies
    title_strategies = ' vs '.join([format_strategy_name(s) for s in strategies])
    fig.suptitle(f'{title_strategies}: Comprehensive Comparison', 
                 fontsize=18, fontweight='bold', y=0.995)
    
    plot_path = output_dir / 'comprehensive_comparison.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved comparison plot: {plot_path}")
    plt.close()


def regenerate_comprehensive_plots(output_dir: Path):
    """Regenerate all comparison plots from the comprehensive_results.csv file.
    
    This function reads the saved CSV and regenerates:
    1. Cumulative P&L by strategy plot
    2. Comprehensive comparison plot (12-panel grid)
    
    Args:
        output_dir: Output directory containing comprehensive_results.csv
    """
    csv_path = output_dir / 'comprehensive_results.csv'
    
    if not csv_path.exists():
        print(f"  ⚠️  No comprehensive_results.csv found, skipping plot regeneration")
        return
    
    # Load data
    df = pd.read_csv(csv_path)
    strategies = sorted(df['strategy'].unique())
    
    print(f"  [DATA] Loading data from {csv_path.name}")
    print(f"  [INFO] Strategies found: {[format_strategy_name(s) for s in strategies]}")
    print(f"  📝 Total rows: {len(df)}")
    
    # Strategy colors and markers
    strategy_colors = {
        'v1': 'steelblue',
        'v2': 'coral',
        'v2_1': 'mediumorchid',
        'v3': 'mediumseagreen'
    }
    strategy_markers = {
        'v1': 'o',
        'v2': 's',
        'v2_1': 'D',
        'v3': '^'
    }
    
    # 1. Regenerate cumulative P&L plot (simple version from CSV)
    fig, ax = plt.subplots(figsize=(12, 7))
    for strategy in strategies:
        data = df[df['strategy'] == strategy].sort_values('interval_sec')
        ax.plot(data['interval_sec'], data['total_pnl'],
               marker=strategy_markers.get(strategy, 'o'), linewidth=2.5, markersize=10,
               label=format_strategy_name(strategy), color=strategy_colors.get(strategy, 'gray'))
    
    ax.set_xlabel('Interval (sec)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Total P&L (AED)', fontweight='bold', fontsize=12)
    ax.set_title('Cumulative P&L by Strategy', fontweight='bold', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
    
    pnl_plot_path = output_dir / 'cumulative_pnl_by_strategy.png'
    plt.savefig(pnl_plot_path, dpi=150, bbox_inches='tight')
    print(f"  [OK] Regenerated: {pnl_plot_path.name}")
    plt.close()
    
    # 2. Regenerate comprehensive comparison plot
    create_comparison_plots(df, output_dir)
    print(f"  [OK] Regenerated: comprehensive_comparison.png")


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive parameter sweep with multiple strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fresh V2 vs V2.1 sweep with custom intervals
  python scripts/comprehensive_sweep.py --strategies v2 v2_1 --fresh --intervals 30 60 120
  
  # Continue from checkpoint, add V3 to existing results
  python scripts/comprehensive_sweep.py --strategies v3 --continue
  
  # Sweep cooldown parameter (30-600s) for V2
  python scripts/comprehensive_sweep.py --strategies v2 --sweep-param cooldown --param-range 30 600 30
  
  # Sweep stop-loss threshold (1-10%) for V2.1
  python scripts/comprehensive_sweep.py --strategies v2_1 --sweep-param threshold --param-range 1 10 1
        """)
    
    # Basic config
    parser.add_argument('--v1-config', type=str, default='configs/v1_baseline_config.json')
    parser.add_argument('--v2-config', type=str, default='configs/v2_price_follow_qty_cooldown_config.json')
    parser.add_argument('--v3-config', type=str, default='configs/v3_liquidity_monitor_config.json')
    parser.add_argument('--data', type=str, default='data/raw/TickData.xlsx')
    parser.add_argument('--max-sheets', type=int, default=None)
    parser.add_argument('--sheet-names', type=str, nargs='+', default=None,
                       help='Specific sheet names to process (e.g., "ADNOCGAS UH Equity")')
    parser.add_argument('--chunk-size', type=int, default=100000)
    parser.add_argument('--output-dir', type=str, default='output/comprehensive_sweep')
    
    # Strategy selection
    parser.add_argument('--strategies', type=str, nargs='+', default=['v1', 'v2'], 
                       choices=['v1', 'v2', 'v2_1', 'v3'],
                       help='Strategies to test: v1, v2, v2_1, v3 (default: v1 v2)')
    
    # Parameter sweep configuration
    parser.add_argument('--sweep-param', type=str, default='interval',
                       choices=['interval', 'cooldown', 'threshold'],
                       help='Parameter to sweep: interval (refill_interval_sec), cooldown (min_cooldown_sec), threshold (stop_loss_threshold_pct)')
    parser.add_argument('--intervals', type=int, nargs='+', default=None,
                       help='Intervals to test (default: 30 60 120 180 300). Only used if --sweep-param=interval')
    parser.add_argument('--param-range', type=float, nargs=3, default=None,
                       metavar=('START', 'END', 'STEP'),
                       help='Parameter range: start end step (e.g., --param-range 30 600 30 for cooldown)')
    
    # Execution mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--fresh', action='store_true', 
                           help='Start fresh sweep, delete existing checkpoint and results')
    mode_group.add_argument('--continue', dest='continue_mode', action='store_true',
                           help='Continue from checkpoint, only run incomplete configurations (default)')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip strategies that already have results in checkpoint (useful for adding new strategies)')
    
    args = parser.parse_args()
    
    # Ensure Parquet data exists (auto-convert if needed)
    print("\nChecking data format...")
    try:
        parquet_dir = ensure_parquet_data(
            excel_path=args.data,
            parquet_dir='data/parquet',
            max_sheets=args.max_sheets
        )
        use_parquet = True
        data_path = parquet_dir
        print(f"Using Parquet format: {parquet_dir}\n")
    except Exception as e:
        print(f"Parquet setup failed: {e}")
        print(f"Falling back to Excel format: {args.data}\n")
        use_parquet = False
        data_path = args.data
    
    # Determine parameter sweep configuration
    if args.sweep_param == 'interval':
        if args.intervals is None:
            sweep_values = [30, 60, 120, 180, 300]
        else:
            sweep_values = args.intervals
        param_name = 'interval_sec'
        param_display = 'Interval (sec)'
    elif args.sweep_param == 'cooldown':
        if args.param_range is None:
            print("ERROR: --param-range required when sweeping cooldown")
            print("Example: --param-range 30 600 30")
            sys.exit(1)
        start, end, step = args.param_range
        sweep_values = list(range(int(start), int(end) + 1, int(step)))
        param_name = 'min_cooldown_sec'
        param_display = 'Cooldown (sec)'
    elif args.sweep_param == 'threshold':
        if args.param_range is None:
            print("ERROR: --param-range required when sweeping threshold")
            print("Example: --param-range 1 10 1")
            sys.exit(1)
        start, end, step = args.param_range
        sweep_values = [round(x, 2) for x in np.arange(start, end + step, step)]
        param_name = 'stop_loss_threshold_pct'
        param_display = 'Stop Loss Threshold (%)'
    
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE PARAMETER SWEEP")
    print(f"{'='*80}")
    print(f"Strategies: {', '.join([format_strategy_name(s) for s in args.strategies])}")
    if 'v3' in args.strategies:
        print(f"WARNING: V3 was abandoned due to poor performance")
        print(f"         See output/v3_abandoned/V3_ABANDONMENT_REPORT.md")
    print(f"Sweep Parameter: {param_display}")
    print(f"Values: {sweep_values}")
    print(f"Data: {args.data}")
    print(f"Max Sheets: {args.max_sheets or 'All'}")
    print(f"Sheet Filter: {args.sheet_names if args.sheet_names else 'None'}")
    print(f"Output: {args.output_dir}")
    
    # Determine execution mode
    if args.fresh:
        mode_str = "Fresh start (deleting checkpoint)"
    elif args.continue_mode:
        mode_str = "Continue from checkpoint"
    elif args.skip_existing:
        mode_str = f"Skip existing strategies, run only incomplete"
    else:
        mode_str = "Continue from checkpoint (default)"
    print(f"Execution Mode: {mode_str}")
    print(f"{'='*80}\n")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Checkpoint file
    checkpoint_path = output_dir / 'checkpoint.csv'
    
    # Load existing progress or start fresh
    if args.fresh:
        print("[FRESH] Starting new sweep")
        if checkpoint_path.exists():
            print(f"   Deleting checkpoint: {checkpoint_path}")
            checkpoint_path.unlink()
        # Delete old per-interval folders
        for folder in output_dir.glob('*_*s'):
            if folder.is_dir():
                print(f"   Deleting old results: {folder.name}")
                import shutil
                shutil.rmtree(folder)
        print("   All previous results cleared\n")
        all_metrics = []
        completed = set()
    elif args.skip_existing or args.continue_mode:
        all_metrics = load_checkpoint(checkpoint_path)
        if args.skip_existing:
            # Only skip strategies that already have results
            existing_strategies = set(m['strategy'] for m in all_metrics)
            skip_strategies = [s for s in args.strategies if s in existing_strategies]
            completed = {(m['strategy'], m.get(param_name, m.get('interval_sec'))) for m in all_metrics if m['strategy'] in skip_strategies}
            print(f"[DATA] Loaded {len(all_metrics)} existing results")
            print(f"   Skipping existing strategies: {skip_strategies}")
            print(f"   Will run: {[s for s in args.strategies if s not in skip_strategies]}")
            print(f"   {len(completed)} configurations marked as completed\n")
        else:
            # Continue mode: skip any matching (strategy, param) combination
            completed = {(m['strategy'], m.get(param_name, m.get('interval_sec'))) for m in all_metrics}
            print(f"▶️  Continuing from checkpoint")
            print(f"   Loaded {len(all_metrics)} existing results")
            print(f"   {len(completed)} configurations already completed\n")
    else:
        # Default: continue from checkpoint
        all_metrics = load_checkpoint(checkpoint_path)
        completed = {(m['strategy'], m.get(param_name, m.get('interval_sec'))) for m in all_metrics}
        print(f"▶️  Continuing from checkpoint (default)")
        print(f"   Loaded {len(all_metrics)} existing results")
        print(f"   {len(completed)} configurations already completed\n")
        all_metrics = load_checkpoint(checkpoint_path)
        completed = {(m['strategy'], m['interval_sec']) for m in all_metrics}
        print(f"Found {len(completed)} completed runs from checkpoint\n")
    
    # Load configs
    configs = {}
    if 'v1' in args.strategies:
        configs['v1'] = load_strategy_config(args.v1_config)
        print(f"Loaded V1 config: {len(configs['v1'])} securities")
    if 'v2' in args.strategies or 'v2_1' in args.strategies:
        v2_config = load_strategy_config(args.v2_config)
        if 'v2' in args.strategies:
            configs['v2'] = v2_config
            print(f"Loaded V2 config: {len(configs['v2'])} securities")
        if 'v2_1' in args.strategies:
            configs['v2_1'] = v2_config
            print(f"Loaded V2.1 config: {len(configs['v2_1'])} securities")
    if 'v3' in args.strategies:
        configs['v3'] = load_strategy_config(args.v3_config)
        print(f"Loaded V3 config: {len(configs['v3'])} securities")
    
    # Run sweeps
    total_runs = len(args.strategies) * len(sweep_values)
    skipped = len(completed)
    current_run = 0
    
    # Storage for per-security metrics across all runs
    all_per_security_metrics = []
    
    # Storage for results to plot cumulative PnL
    all_results = {}
    
    for strategy in args.strategies:
        for param_value in sweep_values:
            # Skip if already completed
            if (strategy, param_value) in completed:
                print(f"⏭️  [{current_run + skipped + 1}/{total_runs}] Skipping {format_strategy_name(strategy)} {param_name}={param_value} (already completed)")
                continue
            
            current_run += 1
            print(f"\n{'='*80}")
            print(f"[RUN] [{current_run}/{total_runs - skipped}] Running {format_strategy_name(strategy)} - {param_display}={param_value}")
            print(f"{'='*80}")
            
            try:
                # Create config with parameter
                if args.sweep_param == 'interval':
                    param_config = {'refill_interval_sec': param_value}
                elif args.sweep_param == 'cooldown':
                    param_config = {'min_cooldown_sec': param_value, 'refill_interval_sec': 60}  # Default interval
                elif args.sweep_param == 'threshold':
                    param_config = {'stop_loss_threshold_pct': param_value, 'refill_interval_sec': 60}  # Default interval
                
                # Run backtest
                results = run_single_backtest_with_params(
                    strategy=strategy,
                    param_config=param_config,
                    base_config=configs[strategy],
                    data_path=args.data,
                    max_sheets=args.max_sheets,
                    chunk_size=args.chunk_size,
                    sheet_names_filter=args.sheet_names
                )
                
                if results is not None:
                    # Store results for plotting
                    all_results[(strategy, param_value)] = results
                    
                    # Compute aggregate metrics with parameter tracking
                    metrics = compute_comprehensive_metrics_with_params(
                        results, param_value, strategy, param_name
                    )
                    all_metrics.append(metrics)
                    
                    # Compute per-security metrics
                    per_sec_metrics = compute_per_security_metrics_with_params(
                        results, param_value, strategy, param_name
                    )
                    all_per_security_metrics.extend(per_sec_metrics)
                    
                    # Save per-security results
                    if args.sweep_param == 'interval':
                        param_dir = output_dir / f"{strategy}_{param_value}s"
                    else:
                        param_dir = output_dir / f"{strategy}_{args.sweep_param}_{param_value}"
                    param_dir.mkdir(parents=True, exist_ok=True)
                    
                    per_security_rows = []
                    for security, data in results.items():
                        trades = data.get('trades', [])
                        if len(trades) > 0:
                            # Save trade-level data
                            trades_df = pd.DataFrame(trades)
                            # Round PNL and position values to integers
                            if 'realized_pnl' in trades_df.columns:
                                trades_df['realized_pnl'] = trades_df['realized_pnl'].round(0).astype(int)
                            if 'pnl' in trades_df.columns:
                                trades_df['pnl'] = trades_df['pnl'].round(0).astype(int)
                            if 'position' in trades_df.columns:
                                trades_df['position'] = trades_df['position'].round(0).astype(int)
                            trades_path = param_dir / f"{security}_trades.csv"
                            trades_df.to_csv(trades_path, index=False)
                            
                            # Add to per-security summary (keep exact values, round only in DataFrame)
                            per_security_rows.append({
                                'security': security,
                                'trades': len(trades),
                                'pnl': data.get('pnl', 0.0),
                                'position': data.get('position', 0),
                                'entry_price': data.get('entry_price', 0)
                            })
                    
                    if per_security_rows:
                        summary_df = pd.DataFrame(per_security_rows)
                        # Round only for output display
                        if 'pnl' in summary_df.columns:
                            summary_df['pnl'] = summary_df['pnl'].round(0).astype(int)
                        if 'position' in summary_df.columns:
                            summary_df['position'] = summary_df['position'].round(0).astype(int)
                        summary_path = param_dir / 'per_security_summary.csv'
                        summary_df.to_csv(summary_path, index=False)
                        print(f"  ✓ Saved per-security results to {param_dir.name}/")
                    
                    # Save checkpoint
                    save_checkpoint(all_metrics, checkpoint_path)
                    
                    # Print summary
                    print(f"\n{format_strategy_name(strategy)} @ {param_display}={param_value} Summary:")
                    print(f"  Trades: {metrics['total_trades']:,}")
                    print(f"  P&L: {metrics['total_pnl']:,.2f} AED")
                    print(f"  Sharpe: {metrics['sharpe_ratio']:.3f}")
                    print(f"  Max DD: {metrics['max_drawdown_pct']:.2f}%")
                    print(f"  Win Rate: {metrics['win_rate']:.1f}%")
                    print(f"  Loss Rate: {metrics['loss_rate']:.1f}%")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user. Progress saved to checkpoint.")
                sys.exit(0)
            except Exception as e:
                print(f"\n[ERROR] Error in {strategy} @ {param_display}={param_value}: {e}")
                import traceback
                traceback.print_exc()
    
    # Create final reports
    print(f"\n{'='*80}")
    print("GENERATING FINAL REPORTS")
    print(f"{'='*80}\n")
    
    # Create DataFrame
    metrics_df = pd.DataFrame(all_metrics)
    
    # Save comprehensive results
    results_path = output_dir / 'comprehensive_results.csv'
    metrics_df.to_csv(results_path, index=False)
    print(f"✓ Saved results: {results_path}")
    
    # Save per-security summary across all strategies/intervals
    if all_per_security_metrics:
        per_sec_df = pd.DataFrame(all_per_security_metrics)
        per_sec_path = output_dir / 'per_security_summary.csv'
        per_sec_df.to_csv(per_sec_path, index=False)
        print(f"✓ Saved per-security summary: {per_sec_path}")
        
        # Create pivot table for easier comparison
        pivot_pnl = per_sec_df.pivot_table(
            index='security',
            columns=['strategy', 'interval_sec'],
            values='pnl',
            aggfunc='sum'
        )
        pivot_path = output_dir / 'per_security_pnl_pivot.csv'
        pivot_pnl.to_csv(pivot_path)
        print(f"✓ Saved per-security P&L pivot: {pivot_path}")
    
    # Create comparison table (adapt to available strategies)
    available_strategies = sorted(metrics_df['strategy'].unique())
    
    if len(available_strategies) >= 2:
        # Create comparison for available strategies
        intervals = sorted(metrics_df['interval_sec'].unique())
        comparison_data = {'Interval (sec)': intervals}
        
        for strategy in available_strategies:
            strat_df = metrics_df[metrics_df['strategy'] == strategy].sort_values('interval_sec')
            
            # Create a complete series aligned with all intervals
            pnl_series = pd.Series(index=intervals, dtype=float)
            trades_series = pd.Series(index=intervals, dtype=int)
            sharpe_series = pd.Series(index=intervals, dtype=float)
            dd_series = pd.Series(index=intervals, dtype=float)
            win_series = pd.Series(index=intervals, dtype=float)
            
            # Fill in available data
            for _, row in strat_df.iterrows():
                interval = row['interval_sec']
                pnl_series[interval] = row['total_pnl']
                trades_series[interval] = row['total_trades']
                sharpe_series[interval] = row['sharpe_ratio']
                dd_series[interval] = row['max_drawdown_pct']
                win_series[interval] = row['win_rate']
            
            comparison_data[f'{format_strategy_name(strategy)} P&L'] = pnl_series.values
            comparison_data[f'{format_strategy_name(strategy)} Trades'] = trades_series.values
            comparison_data[f'{format_strategy_name(strategy)} Sharpe'] = sharpe_series.values
            comparison_data[f'{format_strategy_name(strategy)} Max DD%'] = dd_series.values
            comparison_data[f'{format_strategy_name(strategy)} Win%'] = win_series.values
        
        comparison = pd.DataFrame(comparison_data)
        comparison_path = output_dir / 'comparison_table.csv'
        comparison.to_csv(comparison_path, index=False)
        print(f"✓ Saved comparison table: {comparison_path}")
        
        # Display comparison table in terminal
        print(f"\n{'='*120}")
        print("STRATEGY COMPARISON TABLE")
        print(f"{'='*120}")
        print(comparison.to_string(index=False))
        print(f"{'='*120}\n")
        
        # Create comparison plots for all available strategies
        create_comparison_plots(metrics_df, output_dir)
    
    # Generate all plots (cumulative P&L + comprehensive comparison)
    if all_results:
        print(f"\n[PLOTS] Generating cumulative P&L plots...")
        available_strategies = sorted(set(strat for strat, _ in all_results.keys()))
        plot_cumulative_pnl_by_strategy(all_results, output_dir, strategies=available_strategies)
        plot_pnl_by_security(all_results, output_dir)
    
    # Regenerate comprehensive comparison plot with ALL data from CSV
    print(f"\n[PLOT] Regenerating comprehensive comparison plot with all data...")
    regenerate_comprehensive_plots(output_dir)
    
    # Find best configurations
    print(f"\n{'='*80}")
    print("BEST CONFIGURATIONS")
    print(f"{'='*80}\n")
    
    for strategy in args.strategies:
        strat_df = metrics_df[metrics_df['strategy'] == strategy]
        
        if len(strat_df) == 0:
            continue
        
        best_pnl = strat_df.loc[strat_df['total_pnl'].idxmax()]
        best_sharpe = strat_df.loc[strat_df['sharpe_ratio'].idxmax()]
        
        param_value_pnl = best_pnl.get(param_name, best_pnl.get('interval_sec', 'N/A'))
        param_value_sharpe = best_sharpe.get(param_name, best_sharpe.get('interval_sec', 'N/A'))
        
        print(f"{format_strategy_name(strategy)} Best by P&L:")
        print(f"  {param_display}: {param_value_pnl}")
        print(f"  P&L: {best_pnl['total_pnl']:,.2f} AED")
        print(f"  Sharpe: {best_pnl['sharpe_ratio']:.3f}")
        print(f"  Max DD: {best_pnl['max_drawdown_pct']:.2f}%")
        print(f"  Win Rate: {best_pnl['win_rate']:.1f}%\n")
        
        print(f"{format_strategy_name(strategy)} Best by Sharpe:")
        print(f"  {param_display}: {param_value_sharpe}")
        print(f"  P&L: {best_sharpe['total_pnl']:,.2f} AED")
        print(f"  Sharpe: {best_sharpe['sharpe_ratio']:.3f}")
        print(f"  Max DD: {best_sharpe['max_drawdown_pct']:.2f}%")
        print(f"  Win Rate: {best_sharpe['win_rate']:.1f}%\n")
    
    print(f"{'='*80}")
    print("[COMPLETE] SWEEP COMPLETE!")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
