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


def run_single_backtest(strategy: str, interval_sec: int, base_config: dict, 
                       data_path: str, max_sheets: int = None, 
                       chunk_size: int = 100000, sheet_names_filter: list = None) -> dict:
    """Run single backtest for given strategy and interval.
    
    Args:
        strategy: 'v1' or 'v2'
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
    print(f"Testing {strategy.upper()} - Interval: {interval_sec}s ({interval_sec/60:.1f}m)")
    print(f"{'='*80}")
    
    # Create config
    config = create_config_with_interval(base_config, interval_sec)
    
    # Create appropriate handler
    if strategy == 'v1':
        handler = create_mm_handler(config=config)
    else:
        handler = create_v2_price_follow_qty_cooldown_handler(config=config)
    
    # Run backtest
    start_time = time.time()
    backtest = MarketMakingBacktest()
    
    try:
        results = backtest.run_streaming(
            file_path=data_path,
            handler=handler,
            max_sheets=max_sheets,
            chunk_size=chunk_size,
            only_trades=False,
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


def plot_cumulative_pnl_by_strategy(all_results: dict, output_dir: Path):
    """Plot cumulative PnL over time for each strategy with different lines per interval.
    
    Args:
        all_results: Dictionary mapping (strategy, interval) -> results dict
        output_dir: Output directory
    """
    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    
    for idx, strategy in enumerate(['v1', 'v2']):
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
        ax.set_title(f'{strategy.upper()} @ {interval}s: Cumulative P&L by Security', 
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
    """Create comprehensive comparison plots."""
    
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)
    
    v1_data = all_metrics_df[all_metrics_df['strategy'] == 'v1']
    v2_data = all_metrics_df[all_metrics_df['strategy'] == 'v2']
    
    intervals = sorted(all_metrics_df['interval_sec'].unique())
    x = np.arange(len(intervals))
    width = 0.35
    
    # 1. Total P&L
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.bar(x - width/2, v1_data['total_pnl'], width, label='V1', color='steelblue', alpha=0.8, edgecolor='black')
    ax1.bar(x + width/2, v2_data['total_pnl'], width, label='V2', color='coral', alpha=0.8, edgecolor='black')
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
    ax2.bar(x - width/2, v1_data['total_trades'], width, label='V1', color='steelblue', alpha=0.8, edgecolor='black')
    ax2.bar(x + width/2, v2_data['total_trades'], width, label='V2', color='coral', alpha=0.8, edgecolor='black')
    ax2.set_xlabel('Interval (sec)', fontweight='bold')
    ax2.set_ylabel('Number of Trades', fontweight='bold')
    ax2.set_title('Total Trades', fontweight='bold', fontsize=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(intervals)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    # 3. Sharpe Ratio
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.bar(x - width/2, v1_data['sharpe_ratio'], width, label='V1', color='green', alpha=0.8, edgecolor='black')
    ax3.bar(x + width/2, v2_data['sharpe_ratio'], width, label='V2', color='darkgreen', alpha=0.8, edgecolor='black')
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
    ax4.bar(x - width/2, v1_data['max_drawdown_pct'], width, label='V1', color='red', alpha=0.8, edgecolor='black')
    ax4.bar(x + width/2, v2_data['max_drawdown_pct'], width, label='V2', color='darkred', alpha=0.8, edgecolor='black')
    ax4.set_xlabel('Interval (sec)', fontweight='bold')
    ax4.set_ylabel('Drawdown (%)', fontweight='bold')
    ax4.set_title('Maximum Drawdown', fontweight='bold', fontsize=12)
    ax4.set_xticks(x)
    ax4.set_xticklabels(intervals)
    ax4.legend()
    ax4.grid(axis='y', alpha=0.3)
    
    # 5. Avg P&L per Trade
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.bar(x - width/2, v1_data['avg_pnl_per_trade'], width, label='V1', color='steelblue', alpha=0.8, edgecolor='black')
    ax5.bar(x + width/2, v2_data['avg_pnl_per_trade'], width, label='V2', color='coral', alpha=0.8, edgecolor='black')
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
    ax6.bar(x - width/2, v1_data['win_rate'], width, label='V1', color='green', alpha=0.8, edgecolor='black')
    ax6.bar(x + width/2, v2_data['win_rate'], width, label='V2', color='darkgreen', alpha=0.8, edgecolor='black')
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
    ax7.bar(x - width/2, v1_data['calmar_ratio'], width, label='V1', color='purple', alpha=0.8, edgecolor='black')
    ax7.bar(x + width/2, v2_data['calmar_ratio'], width, label='V2', color='darkviolet', alpha=0.8, edgecolor='black')
    ax7.set_xlabel('Interval (sec)', fontweight='bold')
    ax7.set_ylabel('Calmar Ratio', fontweight='bold')
    ax7.set_title('Calmar Ratio', fontweight='bold', fontsize=12)
    ax7.set_xticks(x)
    ax7.set_xticklabels(intervals)
    ax7.legend()
    ax7.grid(axis='y', alpha=0.3)
    
    # 8. Profit Factor
    ax8 = fig.add_subplot(gs[2, 1])
    ax8.bar(x - width/2, v1_data['profit_factor'], width, label='V1', color='orange', alpha=0.8, edgecolor='black')
    ax8.bar(x + width/2, v2_data['profit_factor'], width, label='V2', color='darkorange', alpha=0.8, edgecolor='black')
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
    ax9.bar(x - width/2, v1_data['trades_per_day'], width, label='V1', color='steelblue', alpha=0.8, edgecolor='black')
    ax9.bar(x + width/2, v2_data['trades_per_day'], width, label='V2', color='coral', alpha=0.8, edgecolor='black')
    ax9.set_xlabel('Interval (sec)', fontweight='bold')
    ax9.set_ylabel('Trades/Day', fontweight='bold')
    ax9.set_title('Trades per Day', fontweight='bold', fontsize=12)
    ax9.set_xticks(x)
    ax9.set_xticklabels(intervals)
    ax9.legend()
    ax9.grid(axis='y', alpha=0.3)
    
    # 10. Risk-Return Scatter
    ax10 = fig.add_subplot(gs[3, 0])
    # Plot V1 points with interval annotations
    for i, (dd, pnl, interval) in enumerate(zip(v1_data['max_drawdown_pct'].abs(), 
                                                  v1_data['total_pnl'], 
                                                  v1_data['interval_sec'])):
        ax10.scatter(dd, pnl, s=200, alpha=0.7, c='steelblue', edgecolor='black', 
                    marker='o', label='V1' if i == 0 else '')
        ax10.annotate(f'{int(interval)}s', (dd, pnl), fontsize=8, ha='center', va='bottom')
    
    # Plot V2 points with interval annotations
    for i, (dd, pnl, interval) in enumerate(zip(v2_data['max_drawdown_pct'].abs(), 
                                                  v2_data['total_pnl'], 
                                                  v2_data['interval_sec'])):
        ax10.scatter(dd, pnl, s=200, alpha=0.7, c='coral', edgecolor='black', 
                    marker='s', label='V2' if i == 0 else '')
        ax10.annotate(f'{int(interval)}s', (dd, pnl), fontsize=8, ha='center', va='top')
    
    ax10.set_xlabel('Max Drawdown % (abs)', fontweight='bold')
    ax10.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax10.set_title('Risk-Return Profile', fontweight='bold', fontsize=12)
    ax10.legend()
    ax10.grid(alpha=0.3)
    
    # 11. Sharpe vs Interval Line Plot
    ax11 = fig.add_subplot(gs[3, 1])
    ax11.plot(v1_data['interval_sec'], v1_data['sharpe_ratio'], 
             marker='o', linewidth=2, markersize=8, label='V1', color='steelblue')
    ax11.plot(v2_data['interval_sec'], v2_data['sharpe_ratio'], 
             marker='s', linewidth=2, markersize=8, label='V2', color='coral')
    ax11.set_xlabel('Interval (sec)', fontweight='bold')
    ax11.set_ylabel('Sharpe Ratio', fontweight='bold')
    ax11.set_title('Sharpe Ratio Trend', fontweight='bold', fontsize=12)
    ax11.legend()
    ax11.grid(alpha=0.3)
    ax11.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    # 12. P&L vs Interval Line Plot
    ax12 = fig.add_subplot(gs[3, 2])
    ax12.plot(v1_data['interval_sec'], v1_data['total_pnl'], 
             marker='o', linewidth=2, markersize=8, label='V1', color='steelblue')
    ax12.plot(v2_data['interval_sec'], v2_data['total_pnl'], 
             marker='s', linewidth=2, markersize=8, label='V2', color='coral')
    ax12.set_xlabel('Interval (sec)', fontweight='bold')
    ax12.set_ylabel('Total P&L (AED)', fontweight='bold')
    ax12.set_title('P&L Trend', fontweight='bold', fontsize=12)
    ax12.legend()
    ax12.grid(alpha=0.3)
    ax12.axhline(0, color='black', linestyle='--', linewidth=0.5)
    
    fig.suptitle('V1 Baseline vs V2 Price Follow: Comprehensive Comparison', 
                 fontsize=18, fontweight='bold', y=0.995)
    
    plot_path = output_dir / 'comprehensive_comparison.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved comparison plot: {plot_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Comprehensive V1 vs V2 parameter sweep")
    parser.add_argument('--v1-config', type=str, default='configs/v1_baseline_config.json')
    parser.add_argument('--v2-config', type=str, default='configs/v2_price_follow_qty_cooldown_config.json')
    parser.add_argument('--data', type=str, default='data/raw/TickData.xlsx')
    parser.add_argument('--intervals', type=int, nargs='+', default=[30, 60, 120, 180, 300])
    parser.add_argument('--max-sheets', type=int, default=None)
    parser.add_argument('--sheet-names', type=str, nargs='+', default=None,
                       help='Specific sheet names to process (e.g., "ADNOCGAS UH Equity")')
    parser.add_argument('--chunk-size', type=int, default=100000)
    parser.add_argument('--output-dir', type=str, default='output/comprehensive_sweep')
    parser.add_argument('--strategies', type=str, nargs='+', default=['v1', 'v2'], choices=['v1', 'v2'])
    parser.add_argument('--fresh', action='store_true', 
                       help='Start fresh sweep, ignoring any existing checkpoint')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print("COMPREHENSIVE PARAMETER SWEEP: V1 vs V2")
    print(f"{'='*80}")
    print(f"Strategies: {', '.join([s.upper() for s in args.strategies])}")
    print(f"Intervals: {args.intervals}")
    print(f"Data: {args.data}")
    print(f"Max Sheets: {args.max_sheets or 'All'}")
    print(f"Sheet Filter: {args.sheet_names if args.sheet_names else 'None'}")
    print(f"Output: {args.output_dir}")
    print(f"Mode: {'Fresh start (ignoring checkpoint)' if args.fresh else 'Resume from checkpoint'}")
    print(f"{'='*80}\n")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Checkpoint file
    checkpoint_path = output_dir / 'checkpoint.csv'
    
    # Load existing progress or start fresh
    if args.fresh:
        print("Starting fresh sweep (checkpoint ignored)\n")
        all_metrics = []
        completed = set()
    else:
        all_metrics = load_checkpoint(checkpoint_path)
        completed = {(m['strategy'], m['interval_sec']) for m in all_metrics}
        print(f"Found {len(completed)} completed runs from checkpoint\n")
    
    # Load configs
    configs = {}
    if 'v1' in args.strategies:
        configs['v1'] = load_strategy_config(args.v1_config)
        print(f"Loaded V1 config: {len(configs['v1'])} securities")
    if 'v2' in args.strategies:
        configs['v2'] = load_strategy_config(args.v2_config)
        print(f"Loaded V2 config: {len(configs['v2'])} securities")
    
    # Run sweeps
    total_runs = len(args.strategies) * len(args.intervals)
    current_run = len(completed)
    
    # Storage for per-security metrics across all runs
    all_per_security_metrics = []
    
    # Storage for results to plot cumulative PnL
    all_results = {}
    
    for strategy in args.strategies:
        for interval_sec in args.intervals:
            # Skip if already completed
            if (strategy, interval_sec) in completed:
                print(f"\n[{current_run + 1}/{total_runs}] Skipping {strategy.upper()} {interval_sec}s (already completed)")
                continue
            
            current_run += 1
            print(f"\n{'='*80}")
            print(f"[{current_run}/{total_runs}] Running {strategy.upper()} - {interval_sec}s")
            print(f"{'='*80}")
            
            try:
                # Run backtest
                results = run_single_backtest(
                    strategy=strategy,
                    interval_sec=interval_sec,
                    base_config=configs[strategy],
                    data_path=args.data,
                    max_sheets=args.max_sheets,
                    chunk_size=args.chunk_size,
                    sheet_names_filter=args.sheet_names
                )
                
                if results is not None:
                    # Store results for plotting
                    all_results[(strategy, interval_sec)] = results
                    
                    # Compute aggregate metrics
                    metrics = compute_comprehensive_metrics(results, interval_sec, strategy)
                    all_metrics.append(metrics)
                    
                    # Compute per-security metrics
                    per_sec_metrics = compute_per_security_metrics(results, interval_sec, strategy)
                    all_per_security_metrics.extend(per_sec_metrics)
                    
                    # Save per-security results
                    interval_dir = output_dir / f"{strategy}_{interval_sec}s"
                    interval_dir.mkdir(parents=True, exist_ok=True)
                    
                    per_security_rows = []
                    for security, data in results.items():
                        trades = data.get('trades', [])
                        if len(trades) > 0:
                            # Save trade-level data
                            trades_df = pd.DataFrame(trades)
                            trades_path = interval_dir / f"{security}_trades.csv"
                            trades_df.to_csv(trades_path, index=False)
                            
                            # Add to per-security summary
                            per_security_rows.append({
                                'security': security,
                                'trades': len(trades),
                                'pnl': data.get('pnl', 0.0),
                                'position': data.get('position', 0),
                                'entry_price': data.get('entry_price', 0)
                            })
                    
                    if per_security_rows:
                        summary_df = pd.DataFrame(per_security_rows)
                        summary_path = interval_dir / 'per_security_summary.csv'
                        summary_df.to_csv(summary_path, index=False)
                        print(f"  ✓ Saved per-security results to {interval_dir.name}/")
                    
                    # Save checkpoint
                    save_checkpoint(all_metrics, checkpoint_path)
                    
                    # Print summary
                    print(f"\n{strategy.upper()} @ {interval_sec}s Summary:")
                    print(f"  Trades: {metrics['total_trades']:,}")
                    print(f"  P&L: {metrics['total_pnl']:,.2f} AED")
                    print(f"  Sharpe: {metrics['sharpe_ratio']:.3f}")
                    print(f"  Max DD: {metrics['max_drawdown_pct']:.2f}%")
                    print(f"  Win Rate: {metrics['win_rate']:.1f}%")
                    print(f"  Loss Rate: {metrics['loss_rate']:.1f}%")
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Progress saved to checkpoint.")
                sys.exit(0)
            except Exception as e:
                print(f"\n✗ Error in {strategy} @ {interval_sec}s: {e}")
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
    
    # Create comparison table
    if 'v1' in args.strategies and 'v2' in args.strategies:
        v1_df = metrics_df[metrics_df['strategy'] == 'v1'].sort_values('interval_sec')
        v2_df = metrics_df[metrics_df['strategy'] == 'v2'].sort_values('interval_sec')
        
        comparison = pd.DataFrame({
            'Interval (sec)': v1_df['interval_sec'].values,
            
            # P&L
            'V1 P&L': v1_df['total_pnl'].values,
            'V2 P&L': v2_df['total_pnl'].values,
            'P&L Diff': (v2_df['total_pnl'].values - v1_df['total_pnl'].values),
            
            # Trades
            'V1 Trades': v1_df['total_trades'].values,
            'V2 Trades': v2_df['total_trades'].values,
            
            # Sharpe
            'V1 Sharpe': v1_df['sharpe_ratio'].values,
            'V2 Sharpe': v2_df['sharpe_ratio'].values,
            
            # Drawdown
            'V1 Max DD%': v1_df['max_drawdown_pct'].values,
            'V2 Max DD%': v2_df['max_drawdown_pct'].values,
            
            # Win Rate
            'V1 Win%': v1_df['win_rate'].values,
            'V2 Win%': v2_df['win_rate'].values,
            
            # Loss Rate
            'V1 Loss%': v1_df['loss_rate'].values,
            'V2 Loss%': v2_df['loss_rate'].values,
            
            # Calmar
            'V1 Calmar': v1_df['calmar_ratio'].values,
            'V2 Calmar': v2_df['calmar_ratio'].values,
        })
        
        comparison_path = output_dir / 'comparison_table.csv'
        comparison.to_csv(comparison_path, index=False)
        print(f"✓ Saved comparison table: {comparison_path}")
        
        # Display comparison table in terminal
        print(f"\n{'='*120}")
        print("STRATEGY COMPARISON TABLE")
        print(f"{'='*120}")
        print(comparison.to_string(index=False))
        print(f"{'='*120}\n")
        
        # Create plots
        create_comparison_plots(metrics_df, output_dir)
    
    # Create cumulative P&L plots
    if all_results:
        print(f"\nGenerating cumulative P&L plots...")
        plot_cumulative_pnl_by_strategy(all_results, output_dir)
        plot_pnl_by_security(all_results, output_dir)
    
    # Find best configurations
    print(f"\n{'='*80}")
    print("BEST CONFIGURATIONS")
    print(f"{'='*80}\n")
    
    for strategy in args.strategies:
        strat_df = metrics_df[metrics_df['strategy'] == strategy]
        
        best_pnl = strat_df.loc[strat_df['total_pnl'].idxmax()]
        best_sharpe = strat_df.loc[strat_df['sharpe_ratio'].idxmax()]
        
        print(f"{strategy.upper()} Best by P&L:")
        print(f"  Interval: {best_pnl['interval_sec']:.0f}s ({best_pnl['interval_min']:.1f}m)")
        print(f"  P&L: {best_pnl['total_pnl']:,.2f} AED")
        print(f"  Sharpe: {best_pnl['sharpe_ratio']:.3f}")
        print(f"  Max DD: {best_pnl['max_drawdown_pct']:.2f}%")
        print(f"  Win Rate: {best_pnl['win_rate']:.1f}%\n")
        
        print(f"{strategy.upper()} Best by Sharpe:")
        print(f"  Interval: {best_sharpe['interval_sec']:.0f}s ({best_sharpe['interval_min']:.1f}m)")
        print(f"  P&L: {best_sharpe['total_pnl']:,.2f} AED")
        print(f"  Sharpe: {best_sharpe['sharpe_ratio']:.3f}")
        print(f"  Max DD: {best_sharpe['max_drawdown_pct']:.2f}%")
        print(f"  Win Rate: {best_sharpe['win_rate']:.1f}%\n")
    
    print(f"{'='*80}")
    print("SWEEP COMPLETE!")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
