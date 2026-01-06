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


def generate_all_plots(
    parquet_dir: str,
    trades_dir: str,
    output_dir: str,
    securities: list = None
):
    """
    Generate plots for all securities.
    
    Args:
        parquet_dir: Directory with parquet files
        trades_dir: Directory with strategy trade CSVs
        output_dir: Output directory for plots
        securities: List of securities to plot (None = all)
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
    
    args = parser.parse_args()
    
    # Resolve paths
    if not os.path.isabs(args.parquet_dir):
        args.parquet_dir = os.path.join(PROJECT_ROOT, args.parquet_dir)
    if not os.path.isabs(args.trades_dir):
        args.trades_dir = os.path.join(PROJECT_ROOT, args.trades_dir)
    if not os.path.isabs(args.output_dir):
        args.output_dir = os.path.join(PROJECT_ROOT, args.output_dir)
    
    securities = [args.security] if args.security else None
    
    generate_all_plots(
        parquet_dir=args.parquet_dir,
        trades_dir=args.trades_dir,
        output_dir=args.output_dir,
        securities=securities
    )


if __name__ == '__main__':
    main()
