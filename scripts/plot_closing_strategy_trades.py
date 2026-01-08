#!/usr/bin/env python
"""
Plot closing strategy trades overlaid on raw market data.

For each security, generates a continuous chart showing:
- Line chart: All Trade events from raw data (price over time, 1-min aggregated)
- Bar chart: Volume aggregated per 30min (separate y-axis)
- Cumulative P&L line (third y-axis)
- Entry buy: upward green triangle
- Entry sell: downward red triangle
- Exit buy: green star
- Exit sell: red star
- Alternating day shading for visual separation
"""

import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def load_raw_trades(parquet_path: str) -> pd.DataFrame:
    """Load raw trade data from parquet file."""
    df = pd.read_parquet(parquet_path)
    # Filter to TRADE events only and trading hours (10:00-15:00)
    trades = df[df['type'] == 'TRADE'].copy()
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])
    trades = trades[(trades['timestamp'].dt.hour >= 10) & 
                    (trades['timestamp'].dt.hour < 15)]
    return trades


def load_strategy_trades(trades_csv_path: str) -> pd.DataFrame:
    """Load strategy trades from CSV."""
    df = pd.read_csv(trades_csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Calculate cumulative P&L
    df = df.sort_values('timestamp')
    df['cumulative_pnl'] = df['realized_pnl'].cumsum()
    return df


def map_to_seq_idx(ts, price_df):
    """Map a timestamp to sequential index in price dataframe."""
    idx = price_df['timestamp'].searchsorted(ts)
    if idx >= len(price_df):
        idx = len(price_df) - 1
    return price_df.iloc[idx]['seq_idx']


def plot_security_continuous(
    security: str,
    raw_trades: pd.DataFrame,
    strategy_trades: pd.DataFrame,
    output_dir: str
) -> str:
    """
    Plot all trading days for a security in a single continuous chart.
    
    Returns the path to the saved plot.
    """
    if len(raw_trades) == 0:
        return None
    
    # Filter strategy trades to trading hours
    strategy_trades_filtered = strategy_trades[
        (strategy_trades['timestamp'].dt.hour >= 10) & 
        (strategy_trades['timestamp'].dt.hour < 15)
    ].copy()
    
    # Aggregate price to 1-minute
    raw_trades_indexed = raw_trades.set_index('timestamp')
    price_1min = raw_trades_indexed['price'].resample('1min').ohlc().dropna()
    price_1min = price_1min.reset_index()
    
    if len(price_1min) == 0:
        return None
    
    # Aggregate volume into 30-minute bins
    volume_30min = raw_trades_indexed['volume'].resample('30min').sum().reset_index()
    volume_30min = volume_30min[volume_30min['volume'] > 0]
    
    # Create sequential index (removes gaps)
    price_1min['seq_idx'] = range(len(price_1min))
    price_1min['date'] = price_1min['timestamp'].dt.date
    
    # Map strategy trades to sequential index
    if len(strategy_trades_filtered) > 0:
        strategy_trades_filtered['seq_idx'] = strategy_trades_filtered['timestamp'].apply(
            lambda x: map_to_seq_idx(x, price_1min)
        )
    
    if len(volume_30min) > 0:
        volume_30min['seq_idx'] = volume_30min['timestamp'].apply(
            lambda x: map_to_seq_idx(x, price_1min)
        )
    
    # Create figure with 3 y-axes
    fig, ax1 = plt.subplots(figsize=(24, 8))
    ax2 = ax1.twinx()
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))  # Offset the third axis
    
    # Add alternating background shading for each day
    day_boundaries = price_1min.groupby('date')['seq_idx'].agg(['min', 'max'])
    for i, (date, row) in enumerate(day_boundaries.iterrows()):
        if i % 2 == 0:
            ax1.axvspan(row['min'], row['max'], alpha=0.1, color='lightblue', zorder=0)
        else:
            ax1.axvspan(row['min'], row['max'], alpha=0.1, color='lightyellow', zorder=0)
    
    # Plot volume bars using sequential index
    if len(volume_30min) > 0:
        bar_width = 30
        ax2.bar(volume_30min['seq_idx'], volume_30min['volume'] / 1e6,
                width=bar_width, alpha=0.3, color='steelblue', label='30min Volume (M)')
    ax2.set_ylabel('Volume (Millions)', color='steelblue', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='steelblue')
    
    # Plot price using sequential index
    ax1.plot(price_1min['seq_idx'], price_1min['close'], 
             linewidth=0.8, alpha=0.9, color='black', label='Trade Price (1min)')
    ax1.set_ylabel('Price (AED)', color='black', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='black')
    
    # Plot cumulative P&L on third axis
    if len(strategy_trades_filtered) > 0:
        ax3.plot(strategy_trades_filtered['seq_idx'], 
                 strategy_trades_filtered['cumulative_pnl'] / 1000,
                 linewidth=2, color='purple', alpha=0.8, label='Cumulative P&L (K)')
        ax3.set_ylabel('Cumulative P&L (K AED)', color='purple', fontsize=12)
        ax3.tick_params(axis='y', labelcolor='purple')
        ax3.axhline(y=0, color='purple', linestyle='--', alpha=0.3)
    
    # Strategy trades markers (only if we have seq_idx column)
    if len(strategy_trades_filtered) > 0 and 'seq_idx' in strategy_trades_filtered.columns:
        entry_buy = strategy_trades_filtered[
            (strategy_trades_filtered['trade_type'] == 'auction_entry') & 
            (strategy_trades_filtered['side'] == 'buy')
        ]
        entry_sell = strategy_trades_filtered[
            (strategy_trades_filtered['trade_type'] == 'auction_entry') & 
            (strategy_trades_filtered['side'] == 'sell')
        ]
        exit_buy = strategy_trades_filtered[
            (strategy_trades_filtered['trade_type'] != 'auction_entry') & 
            (strategy_trades_filtered['side'] == 'buy')
        ]
        exit_sell = strategy_trades_filtered[
            (strategy_trades_filtered['trade_type'] != 'auction_entry') & 
            (strategy_trades_filtered['side'] == 'sell')
        ]
        
        # Plot markers
        if len(entry_buy) > 0:
            ax1.scatter(entry_buy['seq_idx'], entry_buy['price'], 
                       marker='^', s=150, c='green', edgecolors='darkgreen',
                       linewidths=1.5, label='Entry Buy', zorder=5)
        if len(entry_sell) > 0:
            ax1.scatter(entry_sell['seq_idx'], entry_sell['price'], 
                       marker='v', s=150, c='red', edgecolors='darkred',
                       linewidths=1.5, label='Entry Sell', zorder=5)
        if len(exit_buy) > 0:
            ax1.scatter(exit_buy['seq_idx'], exit_buy['price'], 
                       marker='*', s=80, c='limegreen', edgecolors='green',
                       linewidths=0.5, label='Exit Buy', zorder=5, alpha=0.8)
        if len(exit_sell) > 0:
            ax1.scatter(exit_sell['seq_idx'], exit_sell['price'], 
                       marker='*', s=80, c='salmon', edgecolors='red',
                       linewidths=0.5, label='Exit Sell', zorder=5, alpha=0.8)
    
    # Create custom x-axis labels showing dates at day boundaries
    day_starts = price_1min.groupby(price_1min['timestamp'].dt.date).first()
    tick_positions = day_starts['seq_idx'].values[::5]  # Every 5 days
    tick_labels = [str(d) for d in day_starts.index[::5]]
    ax1.set_xticks(tick_positions)
    ax1.set_xticklabels(tick_labels, rotation=45, ha='right')
    
    # Calculate final P&L for title
    final_pnl = strategy_trades['cumulative_pnl'].iloc[-1] if len(strategy_trades) > 0 else 0
    plt.title(f'{security} - Closing Strategy (P&L: {final_pnl:,.0f} AED)', 
              fontsize=14, fontweight='bold')
    
    # Combine legends from all axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    ax1.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3, loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save
    output_path = os.path.join(output_dir, f'{security}_trades.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_path


def generate_summary_plot(trades_dir: str, output_dir: str, config: dict = None):
    """
    Generate a summary plot with:
    - Panel 1: Cumulative P&L over time (all securities combined)
    - Panel 2: P&L by security bar chart
    - Panel 3: Performance metrics table
    - Panel 4: Cumulative P&L by security
    - Panel 5: Configuration parameters table (per-security)
    - Panel 6: Global parameters table
    """
    # Load all trade files
    all_trades = []
    security_pnl = {}
    
    for f in os.listdir(trades_dir):
        if f.endswith('_trades.csv') and not f.startswith('backtest'):
            security = f.replace('_trades.csv', '')
            trades_path = os.path.join(trades_dir, f)
            
            try:
                df = pd.read_csv(trades_path)
                if len(df) == 0:
                    continue
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['security'] = security
                all_trades.append(df)
                
                # Calculate final P&L for this security
                security_pnl[security] = df['realized_pnl'].sum()
            except Exception as e:
                print(f"  ⚠ Error loading {f}: {e}")
                continue
    
    if not all_trades:
        print("  No trades to generate summary plot")
        return
    
    # Combine all trades
    combined = pd.concat(all_trades, ignore_index=True)
    combined = combined.sort_values('timestamp')
    combined['portfolio_cumulative_pnl'] = combined['realized_pnl'].cumsum()
    
    # Calculate performance metrics
    total_pnl = combined['realized_pnl'].sum()
    total_trades = len(combined)
    entry_trades = len(combined[combined['trade_type'].str.contains('ENTRY', na=False)])
    exit_trades = len(combined[combined['trade_type'].str.contains('EXIT', na=False)])
    
    # Win rate
    wins = len(combined[combined['realized_pnl'] > 0])
    losses = len(combined[combined['realized_pnl'] < 0])
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    
    # Calculate returns for Sharpe
    daily_pnl = combined.groupby(combined['timestamp'].dt.date)['realized_pnl'].sum()
    avg_daily_return = daily_pnl.mean()
    std_daily_return = daily_pnl.std()
    sharpe = (avg_daily_return / std_daily_return * np.sqrt(252)) if std_daily_return > 0 else 0
    
    # Drawdown
    running_max = combined['portfolio_cumulative_pnl'].cummax()
    drawdown = combined['portfolio_cumulative_pnl'] - running_max
    max_drawdown = drawdown.min()
    max_drawdown_pct = (max_drawdown / running_max.max() * 100) if running_max.max() > 0 else 0
    
    # Create figure - 3 rows x 2 cols for 6 panels
    fig = plt.figure(figsize=(18, 16))
    
    # Panel 1: Cumulative P&L over time
    ax1 = fig.add_subplot(3, 2, 1)
    ax1.plot(combined['timestamp'], combined['portfolio_cumulative_pnl'] / 1000, 
             color='blue', linewidth=1.5, alpha=0.8)
    ax1.fill_between(combined['timestamp'], 0, combined['portfolio_cumulative_pnl'] / 1000,
                     alpha=0.3, color='blue')
    ax1.set_title('Portfolio Cumulative P&L Over Time', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Cumulative P&L (K AED)')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # Panel 2: P&L by security bar chart
    ax2 = fig.add_subplot(3, 2, 2)
    securities = sorted(security_pnl.keys())
    pnl_values = [security_pnl[s] / 1000 for s in securities]
    colors = ['green' if p >= 0 else 'red' for p in pnl_values]
    bars = ax2.bar(securities, pnl_values, color=colors, alpha=0.7, edgecolor='black')
    ax2.set_title('P&L by Security', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Security')
    ax2.set_ylabel('P&L (K AED)')
    ax2.tick_params(axis='x', rotation=45)
    ax2.axhline(y=0, color='black', linewidth=0.5)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, val in zip(bars, pnl_values):
        height = bar.get_height()
        ax2.annotate(f'{val:.0f}K',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -10),
                    textcoords="offset points",
                    ha='center', va='bottom' if height >= 0 else 'top',
                    fontsize=8)
    
    # Panel 3: Performance metrics table
    ax3 = fig.add_subplot(3, 2, 3)
    ax3.axis('off')
    
    metrics_data = [
        ['Total P&L', f'{total_pnl:,.0f} AED'],
        ['Total Trades', f'{total_trades:,}'],
        ['Entry Trades', f'{entry_trades:,}'],
        ['Exit Trades', f'{exit_trades:,}'],
        ['Win Rate', f'{win_rate:.1f}%'],
        ['Sharpe Ratio', f'{sharpe:.2f}'],
        ['Max Drawdown', f'{max_drawdown:,.0f} AED'],
        ['Max Drawdown %', f'{max_drawdown_pct:.1f}%'],
        ['Trading Days', f'{len(daily_pnl)}'],
        ['Avg Daily P&L', f'{avg_daily_return:,.0f} AED'],
    ]
    
    table = ax3.table(
        cellText=metrics_data,
        colLabels=['Metric', 'Value'],
        loc='center',
        cellLoc='left',
        colWidths=[0.4, 0.4]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Style header row
    for i in range(2):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(color='white', fontweight='bold')
    
    # Alternate row colors
    for i in range(1, len(metrics_data) + 1):
        for j in range(2):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#E6F0FF')
    
    ax3.set_title('Performance Metrics', fontsize=12, fontweight='bold', pad=20)
    
    # Panel 4: P&L per security cumulative
    ax4 = fig.add_subplot(3, 2, 4)
    
    colors_map = plt.cm.tab20(np.linspace(0, 1, len(securities)))
    for i, (trades_df, sec) in enumerate(zip(all_trades, [df['security'].iloc[0] for df in all_trades])):
        trades_sorted = trades_df.sort_values('timestamp')
        trades_sorted['sec_cumulative_pnl'] = trades_sorted['realized_pnl'].cumsum()
        ax4.plot(trades_sorted['timestamp'], trades_sorted['sec_cumulative_pnl'] / 1000,
                label=sec, color=colors_map[i % len(colors_map)], alpha=0.7, linewidth=1)
    
    ax4.set_title('Cumulative P&L by Security', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Date')
    ax4.set_ylabel('Cumulative P&L (K AED)')
    ax4.legend(loc='upper left', ncol=4, fontsize=7)
    ax4.grid(True, alpha=0.3)
    ax4.tick_params(axis='x', rotation=45)
    
    # Panel 5: Global Parameters (if config provided)
    ax5 = fig.add_subplot(3, 2, 5)
    ax5.axis('off')
    
    if config and len(config) > 0:
        # Extract global parameters from first security config
        first_sec = list(config.keys())[0]
        first_config = config[first_sec]
        
        global_params = [
            ['VWAP Period (min)', str(first_config.get('vwap_preclose_period_min', 15))],
            ['Spread VWAP (%)', str(first_config.get('spread_vwap_pct', 0.5))],
            ['Stop Loss (%)', str(first_config.get('stop_loss_threshold_pct', 2.0))],
            ['SELL Filter Enabled', str(first_config.get('trend_filter_sell_enabled', True))],
            ['SELL Threshold (bps/hr)', str(first_config.get('trend_filter_sell_threshold_bps_hr', 10.0))],
            ['BUY Filter Enabled', str(first_config.get('trend_filter_buy_enabled', False))],
            ['BUY Threshold (bps/hr)', str(first_config.get('trend_filter_buy_threshold_bps_hr', 10.0))],
        ]
        
        table5 = ax5.table(
            cellText=global_params,
            colLabels=['Parameter', 'Value'],
            loc='center',
            cellLoc='left',
            colWidths=[0.5, 0.3]
        )
        table5.auto_set_font_size(False)
        table5.set_fontsize(11)
        table5.scale(1.2, 1.8)
        
        for i in range(2):
            table5[(0, i)].set_facecolor('#70AD47')
            table5[(0, i)].set_text_props(color='white', fontweight='bold')
        
        for i in range(1, len(global_params) + 1):
            for j in range(2):
                if i % 2 == 0:
                    table5[(i, j)].set_facecolor('#E2EFDA')
        
        ax5.set_title('Global Strategy Parameters', fontsize=12, fontweight='bold', pad=20)
    else:
        ax5.text(0.5, 0.5, 'No config file provided\nUse --config to include parameters', 
                ha='center', va='center', fontsize=12, color='gray')
        ax5.set_title('Global Strategy Parameters', fontsize=12, fontweight='bold', pad=20)
    
    # Panel 6: Per-Security Configuration (notional sizes)
    ax6 = fig.add_subplot(3, 2, 6)
    ax6.axis('off')
    
    if config and len(config) > 0:
        # Build per-security table with notional values
        sec_config_data = []
        for sec in sorted(config.keys()):
            sec_cfg = config[sec]
            notional = sec_cfg.get('order_notional', 250000)
            notional_str = f'{notional/1000:.0f}K' if notional >= 1000 else str(notional)
            sec_config_data.append([sec, notional_str])
        
        # Split into two columns for better display
        n_rows = (len(sec_config_data) + 1) // 2
        left_data = sec_config_data[:n_rows]
        right_data = sec_config_data[n_rows:] if len(sec_config_data) > n_rows else []
        
        # Pad right data if needed
        while len(right_data) < len(left_data):
            right_data.append(['', ''])
        
        # Combine into 4-column table
        combined_data = []
        for i in range(len(left_data)):
            row = [left_data[i][0], left_data[i][1]]
            if i < len(right_data):
                row.extend([right_data[i][0], right_data[i][1]])
            else:
                row.extend(['', ''])
            combined_data.append(row)
        
        table6 = ax6.table(
            cellText=combined_data,
            colLabels=['Security', 'Notional', 'Security', 'Notional'],
            loc='center',
            cellLoc='center',
            colWidths=[0.25, 0.2, 0.25, 0.2]
        )
        table6.auto_set_font_size(False)
        table6.set_fontsize(9)
        table6.scale(1.1, 1.5)
        
        for i in range(4):
            table6[(0, i)].set_facecolor('#ED7D31')
            table6[(0, i)].set_text_props(color='white', fontweight='bold')
        
        for i in range(1, len(combined_data) + 1):
            for j in range(4):
                if i % 2 == 0:
                    table6[(i, j)].set_facecolor('#FCE4D6')
        
        ax6.set_title('Per-Security Order Notional (AED)', fontsize=12, fontweight='bold', pad=20)
    else:
        ax6.text(0.5, 0.5, 'No config file provided\nUse --config to include parameters', 
                ha='center', va='center', fontsize=12, color='gray')
        ax6.set_title('Per-Security Order Notional', fontsize=12, fontweight='bold', pad=20)
    
    plt.suptitle('Closing Strategy - Performance Summary', fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    
    # Save
    summary_path = os.path.join(output_dir, 'performance_summary.png')
    plt.savefig(summary_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Saved: performance_summary.png")


def generate_all_plots(
    parquet_dir: str,
    trades_dir: str,
    output_dir: str,
    securities: list = None,
    config: dict = None
):
    """
    Generate plots for all securities.
    
    Args:
        parquet_dir: Directory with parquet files
        trades_dir: Directory with strategy trade CSVs
        output_dir: Output directory for plots
        securities: List of securities to plot (None = all)
        config: Strategy configuration dict for parameter display
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Get list of securities to plot
    if securities is None:
        securities = []
        for f in os.listdir(trades_dir):
            if f.endswith('_trades.csv'):
                securities.append(f.replace('_trades.csv', ''))
    
    print(f"Generating plots for {len(securities)} securities...")
    
    for security in securities:
        parquet_path = os.path.join(parquet_dir, f'{security}.parquet')
        trades_path = os.path.join(trades_dir, f'{security}_trades.csv')
        
        if not os.path.exists(parquet_path):
            print(f"  ⚠ {security}: No parquet file found")
            continue
        if not os.path.exists(trades_path):
            print(f"  ⚠ {security}: No trades file found")
            continue
        
        # Load data
        raw_trades = load_raw_trades(parquet_path)
        strategy_trades = load_strategy_trades(trades_path)
        
        # Generate plot
        output_path = plot_security_continuous(
            security, raw_trades, strategy_trades, output_dir
        )
        
        if output_path:
            final_pnl = strategy_trades['cumulative_pnl'].iloc[-1] if len(strategy_trades) > 0 else 0
            print(f"  ✓ {security}: P&L {final_pnl:,.0f} AED")
        else:
            print(f"  ⚠ {security}: No data to plot")
    
    # Generate summary plot
    generate_summary_plot(trades_dir, output_dir, config)
    
    print(f"\nPlots saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Plot closing strategy trades')
    parser.add_argument(
        '--security',
        help='Specific security to plot (default: all)'
    )
    parser.add_argument(
        '--parquet-dir',
        default='data/parquet',
        help='Directory with parquet files'
    )
    parser.add_argument(
        '--trades-dir',
        default='output/closing_strategy',
        help='Directory with strategy trade CSVs'
    )
    parser.add_argument(
        '--output-dir',
        default='output/closing_strategy/plots',
        help='Output directory for plots'
    )
    parser.add_argument(
        '--config',
        help='Path to config JSON file (for parameter display in summary plot)'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    if not os.path.isabs(args.parquet_dir):
        args.parquet_dir = os.path.join(PROJECT_ROOT, args.parquet_dir)
    if not os.path.isabs(args.trades_dir):
        args.trades_dir = os.path.join(PROJECT_ROOT, args.trades_dir)
    if not os.path.isabs(args.output_dir):
        args.output_dir = os.path.join(PROJECT_ROOT, args.output_dir)
    
    # Load config if provided
    config = None
    if args.config:
        config_path = args.config
        if not os.path.isabs(config_path):
            config_path = os.path.join(PROJECT_ROOT, config_path)
        
        import json
        with open(config_path) as f:
            config = json.load(f)
        print(f"Loaded config from {config_path}")
    
    securities = [args.security] if args.security else None
    
    generate_all_plots(
        parquet_dir=args.parquet_dir,
        trades_dir=args.trades_dir,
        output_dir=args.output_dir,
        securities=securities,
        config=config
    )


if __name__ == '__main__':
    main()
