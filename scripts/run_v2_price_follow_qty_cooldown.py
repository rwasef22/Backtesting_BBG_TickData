"""
Run backtest with v2_price_follow_qty_cooldown strategy.

This strategy continuously updates quote prices to follow the market,
but limits quantity refills after executions via cooldown periods.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_strategy_config
from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v2_price_follow_qty_cooldown import create_v2_price_follow_qty_cooldown_handler
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime


def run_v2_price_follow_qty_cooldown_backtest(
    data_file: str,
    config_file: str,
    output_dir: str = 'output/v2_price_follow_qty_cooldown',
    max_sheets: int = None
):
    """
    Run backtest with v2_price_follow_qty_cooldown strategy.
    
    Args:
        data_file: Path to Excel data file
        config_file: Path to strategy config JSON
        output_dir: Directory for output files
        max_sheets: Maximum number of securities to process
    """
    print("=" * 80)
    print("V2 PRICE FOLLOW WITH QUANTITY COOLDOWN STRATEGY BACKTEST")
    print("=" * 80)
    print(f"\nStrategy: v2_price_follow_qty_cooldown")
    print(f"Data file: {data_file}")
    print(f"Config file: {config_file}")
    print(f"Output directory: {output_dir}")
    print("\nStrategy Characteristics:")
    print("  - Quote prices: CONTINUOUS UPDATES (follow market)")
    print("  - Quantity refill: COOLDOWN after fills")
    print("  - Queue position: RESET on price changes")
    print("  - Cooldown trigger: ANY fill (partial or full)")
    print()
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load configuration
    print("Loading configuration...")
    config = load_strategy_config(config_file)
    print(f"Loaded config for {len(config)} securities")
    
    # Create handler
    print("Creating v2_price_follow_qty_cooldown handler...")
    handler = create_v2_price_follow_qty_cooldown_handler(config)
    
    # Run backtest
    print("\nRunning backtest...")
    print("-" * 80)
    backtest = MarketMakingBacktest()
    
    results = backtest.run_streaming(
        file_path=data_file,
        handler=handler,
        only_trades=False,
        max_sheets=max_sheets
    )
    
    print("-" * 80)
    print(f"\nBacktest complete! Processed {len(results)} securities")
    
    # Save results
    print("\nSaving results...")
    
    # Summary results
    summary_data = []
    for security, data in results.items():
        trades = data.get('trades', [])
        if trades:
            trade_df = pd.DataFrame(trades)
            
            summary_data.append({
                'security': security,
                'total_trades': len(trades),
                'total_pnl': data.get('pnl', 0),
                'final_position': data.get('position', 0),
                'avg_pnl_per_trade': data.get('pnl', 0) / len(trades) if trades else 0,
                'total_buy_qty': trade_df[trade_df['side'] == 'buy']['fill_qty'].sum(),
                'total_sell_qty': trade_df[trade_df['side'] == 'sell']['fill_qty'].sum(),
            })
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        summary_file = output_path / 'backtest_summary.csv'
        summary_df.to_csv(summary_file, index=False)
        print(f"Saved summary to {summary_file}")
        
        # Display summary
        print("\n" + "=" * 80)
        print("BACKTEST SUMMARY")
        print("=" * 80)
        print(summary_df.to_string(index=False))
        print("=" * 80)
    
    # Save per-security results
    for security, data in results.items():
        trades = data.get('trades', [])
        if trades:
            trade_df = pd.DataFrame(trades)
            
            # Save timeseries
            csv_file = output_path / f'{security}_trades_timeseries.csv'
            trade_df.to_csv(csv_file, index=False)
            print(f"Saved {security} timeseries to {csv_file}")
            
            # Generate plots
            plot_file = output_path / f'{security}_inventory_pnl.png'
            plot_strategy_results(trade_df, security, plot_file)
            print(f"Saved {security} plot to {plot_file}")
    
    # Save run log
    log_file = output_path / 'run_log.txt'
    with open(log_file, 'w') as f:
        f.write(f"V2 Price Follow with Quantity Cooldown Strategy Backtest\n")
        f.write(f"Run time: {datetime.now()}\n")
        f.write(f"Data file: {data_file}\n")
        f.write(f"Config file: {config_file}\n")
        f.write(f"\nStrategy: v2_price_follow_qty_cooldown\n")
        f.write(f"Version: 2.0\n")
        f.write(f"\nCharacteristics:\n")
        f.write(f"  - Price updates: Continuous (follow market)\n")
        f.write(f"  - Quantity refills: Cooldown after fills\n")
        f.write(f"  - Queue position: Reset on price changes\n")
        f.write(f"  - Cooldown trigger: Any fill\n")
        f.write(f"\nSecurities processed: {len(results)}\n")
        f.write(f"Total trades: {sum(len(d.get('trades', [])) for d in results.values())}\n")
    
    print(f"\nSaved run log to {log_file}")
    print(f"\nAll results saved to: {output_dir}/")
    
    return results


def plot_strategy_results(trade_df, security, output_file):
    """
    Generate plots for strategy results.
    
    Args:
        trade_df: DataFrame with trade data
        security: Security name
        output_file: Path to save plot
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Plot 1: Inventory over time
    ax1.plot(trade_df['timestamp'], trade_df['position'], linewidth=1.5, color='blue')
    ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Inventory (shares)')
    ax1.set_title(f'{security} - Inventory Over Time (v2_price_follow_qty_cooldown)')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Cumulative P&L over time
    ax2.plot(trade_df['timestamp'], trade_df['pnl'], linewidth=1.5, color='green')
    ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Cumulative P&L')
    ax2.set_title(f'{security} - Cumulative P&L (v2_price_follow_qty_cooldown)')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()


if __name__ == '__main__':
    # Default paths
    data_file = 'data/raw/TickData.xlsx'
    config_file = 'configs/mm_config.json'
    output_dir = 'output/v2_price_follow_qty_cooldown'
    
    # Run backtest
    results = run_v2_price_follow_qty_cooldown_backtest(
        data_file=data_file,
        config_file=config_file,
        output_dir=output_dir,
        max_sheets=None  # Process all securities
    )
    
    print("\n✓ Backtest complete!")
