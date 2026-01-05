"""
Plot comprehensive analysis for V3 test results.
Similar to comprehensive_sweep plots but for single strategy run.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))


class AdvancedMetricsCalculator:
    """Calculate advanced investment metrics from trade history."""
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = (excess_returns.mean() / returns.std()) * np.sqrt(252)
        return sharpe
    
    @staticmethod
    def calculate_max_drawdown(cumulative_pnl: pd.Series) -> tuple:
        """Calculate maximum drawdown and recovery info."""
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
        """Calculate Calmar ratio (annualized return / max drawdown)."""
        if len(returns) == 0:
            return 0.0
        
        annual_return = returns.mean() * 252
        _, max_dd_pct, _ = AdvancedMetricsCalculator.calculate_max_drawdown(cumulative_pnl)
        
        if abs(max_dd_pct) < 0.001:  # Avoid division by zero
            return 0.0
        
        return (annual_return / abs(max_dd_pct)) * 100
    
    @staticmethod
    def calculate_win_rate(trades: list) -> dict:
        """Calculate win rate and related statistics."""
        if not trades:
            return {
                'win_rate': 0.0,
                'loss_rate': 0.0,
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


def plot_v3_analysis(trades_csv_path: str, output_dir: str = None):
    """Generate comprehensive analysis plots for V3 test results.
    
    Args:
        trades_csv_path: Path to the trades timeseries CSV
        output_dir: Output directory for plots (default: same as CSV location)
    """
    # Load data
    trades_df = pd.read_csv(trades_csv_path)
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df = trades_df.sort_values('timestamp')
    
    # Set output directory
    if output_dir is None:
        output_dir = Path(trades_csv_path).parent
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Analyzing V3 test results from: {trades_csv_path}")
    print(f"Output directory: {output_dir}")
    print(f"\nData loaded: {len(trades_df)} trades")
    
    # Calculate metrics
    calc = AdvancedMetricsCalculator()
    
    # Basic metrics
    total_trades = len(trades_df)
    final_pnl = trades_df['pnl'].iloc[-1]
    total_realized_pnl = trades_df['realized_pnl'].sum()
    
    # Daily aggregation
    daily = trades_df.groupby(trades_df['timestamp'].dt.date).agg({
        'realized_pnl': 'sum',
        'pnl': 'last'
    })
    daily['returns'] = daily['realized_pnl']
    
    # Advanced metrics
    sharpe = calc.calculate_sharpe_ratio(daily['returns'])
    max_dd, max_dd_pct, dd_duration = calc.calculate_max_drawdown(daily['pnl'])
    calmar = calc.calculate_calmar_ratio(daily['returns'], daily['pnl'])
    
    # Win/Loss statistics
    trades_list = trades_df[trades_df['realized_pnl'] != 0].to_dict('records')
    win_stats = calc.calculate_win_rate(trades_list)
    
    # Trading days
    trading_days = len(daily)
    trades_per_day = total_trades / trading_days if trading_days > 0 else 0
    
    # Print summary
    print(f"\n{'='*80}")
    print("V3 LIQUIDITY MONITOR STRATEGY - TEST RESULTS")
    print(f"{'='*80}")
    print(f"Total Trades:       {total_trades:,}")
    print(f"Final P&L:          {final_pnl:,.2f} AED")
    print(f"Total Realized PnL: {total_realized_pnl:,.2f} AED")
    print(f"Trading Days:       {trading_days}")
    print(f"Trades per Day:     {trades_per_day:.2f}")
    print(f"\nRisk Metrics:")
    print(f"Sharpe Ratio:       {sharpe:.3f}")
    print(f"Max Drawdown:       {max_dd:,.2f} AED ({max_dd_pct:.2f}%)")
    print(f"DD Duration:        {dd_duration:.0f} days")
    print(f"Calmar Ratio:       {calmar:.3f}")
    print(f"\nWin/Loss Statistics:")
    print(f"Win Rate:           {win_stats['win_rate']:.1f}%")
    print(f"Loss Rate:          {win_stats['loss_rate']:.1f}%")
    print(f"Avg Win:            {win_stats['avg_win']:,.2f} AED")
    print(f"Avg Loss:           {win_stats['avg_loss']:,.2f} AED")
    print(f"Profit Factor:      {win_stats['profit_factor']:.2f}")
    print(f"Total Wins:         {win_stats['total_wins']}")
    print(f"Total Losses:       {win_stats['total_losses']}")
    print(f"{'='*80}\n")
    
    # Create comprehensive plots
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)
    
    # 1. Cumulative P&L Over Time
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(trades_df['timestamp'], trades_df['pnl'], 
             linewidth=2.5, color='darkblue', alpha=0.8, label='Cumulative P&L')
    ax1.fill_between(trades_df['timestamp'], 0, trades_df['pnl'], 
                     alpha=0.2, color='darkblue')
    ax1.set_xlabel('Date', fontweight='bold', fontsize=12)
    ax1.set_ylabel('Cumulative P&L (AED)', fontweight='bold', fontsize=12)
    ax1.set_title('V3 Liquidity Monitor: Cumulative P&L Over Time', 
                 fontweight='bold', fontsize=14)
    ax1.grid(alpha=0.3)
    ax1.axhline(0, color='black', linestyle='--', linewidth=1)
    ax1.legend(fontsize=11)
    
    # Add annotations for max and min
    max_pnl = trades_df['pnl'].max()
    max_pnl_date = trades_df.loc[trades_df['pnl'].idxmax(), 'timestamp']
    min_pnl = trades_df['pnl'].min()
    min_pnl_date = trades_df.loc[trades_df['pnl'].idxmin(), 'timestamp']
    
    ax1.annotate(f'Max: {max_pnl:,.0f}', 
                xy=(max_pnl_date, max_pnl), 
                xytext=(10, 10), textcoords='offset points',
                fontsize=10, color='green', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))
    
    ax1.annotate(f'Min: {min_pnl:,.0f}', 
                xy=(min_pnl_date, min_pnl), 
                xytext=(10, -20), textcoords='offset points',
                fontsize=10, color='red', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7))
    
    # 2. Trade P&L Distribution
    ax2 = fig.add_subplot(gs[1, 0])
    realized_pnl = trades_df[trades_df['realized_pnl'] != 0]['realized_pnl']
    ax2.hist(realized_pnl, bins=30, color='steelblue', alpha=0.7, edgecolor='black')
    ax2.axvline(realized_pnl.mean(), color='red', linestyle='--', linewidth=2, 
               label=f'Mean: {realized_pnl.mean():.2f}')
    ax2.axvline(0, color='black', linestyle='-', linewidth=1)
    ax2.set_xlabel('Realized P&L (AED)', fontweight='bold')
    ax2.set_ylabel('Frequency', fontweight='bold')
    ax2.set_title('Trade P&L Distribution', fontweight='bold', fontsize=12)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    # 3. Position Over Time
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(trades_df['timestamp'], trades_df['position'], 
            linewidth=1.5, color='purple', alpha=0.8)
    ax3.fill_between(trades_df['timestamp'], 0, trades_df['position'], 
                     alpha=0.3, color='purple')
    ax3.set_xlabel('Date', fontweight='bold')
    ax3.set_ylabel('Position (shares)', fontweight='bold')
    ax3.set_title('Position Over Time', fontweight='bold', fontsize=12)
    ax3.axhline(0, color='black', linestyle='--', linewidth=1)
    ax3.grid(alpha=0.3)
    
    # 4. Buy vs Sell Distribution
    ax4 = fig.add_subplot(gs[1, 2])
    buy_trades = trades_df[trades_df['side'] == 'buy'].shape[0]
    sell_trades = trades_df[trades_df['side'] == 'sell'].shape[0]
    ax4.bar(['Buy', 'Sell'], [buy_trades, sell_trades], 
           color=['green', 'red'], alpha=0.7, edgecolor='black', width=0.5)
    ax4.set_ylabel('Number of Trades', fontweight='bold')
    ax4.set_title('Buy vs Sell Trades', fontweight='bold', fontsize=12)
    ax4.grid(axis='y', alpha=0.3)
    for i, v in enumerate([buy_trades, sell_trades]):
        ax4.text(i, v + 2, str(v), ha='center', va='bottom', fontweight='bold', fontsize=11)
    
    # 5. Daily P&L
    ax5 = fig.add_subplot(gs[2, 0])
    daily_pnl = trades_df.groupby(trades_df['timestamp'].dt.date)['realized_pnl'].sum()
    colors = ['green' if x >= 0 else 'red' for x in daily_pnl.values]
    ax5.bar(range(len(daily_pnl)), daily_pnl.values, color=colors, alpha=0.7, edgecolor='black')
    ax5.set_xlabel('Trading Day', fontweight='bold')
    ax5.set_ylabel('Daily P&L (AED)', fontweight='bold')
    ax5.set_title('Daily P&L', fontweight='bold', fontsize=12)
    ax5.axhline(0, color='black', linestyle='-', linewidth=1)
    ax5.grid(axis='y', alpha=0.3)
    
    # 6. Win/Loss Pie Chart
    ax6 = fig.add_subplot(gs[2, 1])
    wins = win_stats['total_wins']
    losses = win_stats['total_losses']
    if wins + losses > 0:
        ax6.pie([wins, losses], labels=['Wins', 'Losses'], 
               colors=['green', 'red'], autopct='%1.1f%%', 
               startangle=90, textprops={'fontweight': 'bold', 'fontsize': 11},
               wedgeprops={'edgecolor': 'black', 'linewidth': 1.5})
        ax6.set_title(f'Win/Loss Ratio\n(Win Rate: {win_stats["win_rate"]:.1f}%)', 
                     fontweight='bold', fontsize=12)
    
    # 7. Cumulative Trades Count
    ax7 = fig.add_subplot(gs[2, 2])
    ax7.plot(trades_df['timestamp'], range(1, len(trades_df) + 1), 
            linewidth=2, color='darkgreen', alpha=0.8)
    ax7.set_xlabel('Date', fontweight='bold')
    ax7.set_ylabel('Cumulative Trade Count', fontweight='bold')
    ax7.set_title('Trade Execution Timeline', fontweight='bold', fontsize=12)
    ax7.grid(alpha=0.3)
    
    # 8. Rolling Sharpe (if enough data)
    ax8 = fig.add_subplot(gs[3, 0])
    if len(daily) >= 20:
        rolling_returns = daily['returns'].rolling(window=10, min_periods=5)
        rolling_sharpe = rolling_returns.mean() / rolling_returns.std() * np.sqrt(252)
        ax8.plot(range(len(rolling_sharpe)), rolling_sharpe.values, 
                linewidth=2, color='darkblue', alpha=0.8)
        ax8.axhline(0, color='black', linestyle='--', linewidth=1)
        ax8.set_xlabel('Trading Day', fontweight='bold')
        ax8.set_ylabel('Rolling Sharpe (10-day)', fontweight='bold')
        ax8.set_title('Rolling Sharpe Ratio', fontweight='bold', fontsize=12)
        ax8.grid(alpha=0.3)
    else:
        ax8.text(0.5, 0.5, 'Insufficient data\nfor rolling Sharpe', 
                ha='center', va='center', fontsize=12, transform=ax8.transAxes)
        ax8.set_title('Rolling Sharpe Ratio', fontweight='bold', fontsize=12)
    
    # 9. Drawdown Over Time
    ax9 = fig.add_subplot(gs[3, 1])
    cumulative_pnl = daily['pnl'].values
    running_max = np.maximum.accumulate(cumulative_pnl)
    drawdown = cumulative_pnl - running_max
    drawdown_pct = (drawdown / running_max) * 100
    drawdown_pct = np.where(running_max == 0, 0, drawdown_pct)
    
    ax9.fill_between(range(len(drawdown_pct)), drawdown_pct, 0, 
                     color='red', alpha=0.4, label='Drawdown')
    ax9.plot(range(len(drawdown_pct)), drawdown_pct, 
            linewidth=2, color='darkred', alpha=0.8)
    ax9.set_xlabel('Trading Day', fontweight='bold')
    ax9.set_ylabel('Drawdown (%)', fontweight='bold')
    ax9.set_title(f'Drawdown Over Time (Max: {max_dd_pct:.2f}%)', 
                 fontweight='bold', fontsize=12)
    ax9.legend()
    ax9.grid(alpha=0.3)
    
    # 10. Metrics Summary Box
    ax10 = fig.add_subplot(gs[3, 2])
    ax10.axis('off')
    
    summary_text = f"""
    PERFORMANCE SUMMARY
    {'='*40}
    
    Total Trades:        {total_trades:,}
    Final P&L:           {final_pnl:,.2f} AED
    
    Sharpe Ratio:        {sharpe:.3f}
    Max Drawdown:        {max_dd_pct:.2f}%
    Calmar Ratio:        {calmar:.3f}
    
    Win Rate:            {win_stats['win_rate']:.1f}%
    Profit Factor:       {win_stats['profit_factor']:.2f}
    
    Avg Win:             {win_stats['avg_win']:,.2f} AED
    Avg Loss:            {win_stats['avg_loss']:,.2f} AED
    
    Trades/Day:          {trades_per_day:.2f}
    Trading Days:        {trading_days}
    """
    
    ax10.text(0.1, 0.5, summary_text, fontsize=10, verticalalignment='center',
             fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    # Main title
    fig.suptitle('V3 Liquidity Monitor Strategy - Comprehensive Analysis', 
                fontsize=16, fontweight='bold', y=0.995)
    
    # Save plot
    plot_path = output_dir / 'v3_comprehensive_analysis.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved comprehensive analysis plot: {plot_path}")
    plt.close()
    
    # Create separate cumulative P&L plot (larger, clearer)
    fig2, ax = plt.subplots(figsize=(16, 8))
    ax.plot(trades_df['timestamp'], trades_df['pnl'], 
           linewidth=3, color='darkblue', alpha=0.8, label='Cumulative P&L')
    ax.fill_between(trades_df['timestamp'], 0, trades_df['pnl'], 
                   alpha=0.2, color='darkblue')
    
    # Add trade markers
    buy_df = trades_df[trades_df['side'] == 'buy']
    sell_df = trades_df[trades_df['side'] == 'sell']
    ax.scatter(buy_df['timestamp'], buy_df['pnl'], 
              color='green', marker='^', s=50, alpha=0.6, label='Buy', zorder=5)
    ax.scatter(sell_df['timestamp'], sell_df['pnl'], 
              color='red', marker='v', s=50, alpha=0.6, label='Sell', zorder=5)
    
    ax.set_xlabel('Date', fontweight='bold', fontsize=14)
    ax.set_ylabel('Cumulative P&L (AED)', fontweight='bold', fontsize=14)
    ax.set_title('V3 Liquidity Monitor: Cumulative P&L with Trade Markers', 
                fontweight='bold', fontsize=16)
    ax.grid(alpha=0.3, linestyle='--')
    ax.axhline(0, color='black', linestyle='--', linewidth=1.5)
    ax.legend(fontsize=12, loc='best')
    
    # Add annotations
    ax.annotate(f'Final P&L: {final_pnl:,.2f} AED', 
               xy=(trades_df['timestamp'].iloc[-1], final_pnl), 
               xytext=(-80, 20), textcoords='offset points',
               fontsize=12, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.7', facecolor='yellow', alpha=0.8),
               arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', lw=2))
    
    plt.tight_layout()
    pnl_plot_path = output_dir / 'v3_cumulative_pnl_detailed.png'
    plt.savefig(pnl_plot_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved detailed cumulative P&L plot: {pnl_plot_path}")
    plt.close()
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE!")
    print(f"All plots saved to: {output_dir}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Plot V3 test analysis')
    parser.add_argument('--trades-csv', type=str, 
                       default='output/v3_test/emaar_trades_timeseries.csv',
                       help='Path to trades timeseries CSV')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='Output directory for plots (default: same as CSV location)')
    
    args = parser.parse_args()
    
    plot_v3_analysis(args.trades_csv, args.output_dir)
