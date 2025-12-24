"""Run the market-making backtest with strategy on sample data."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import matplotlib.pyplot as plt
from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config


def run_mm_backtest(excel_file: str = 'TickData_Sample.xlsx', max_sheets: int = None, config_file: str = None, generate_plots: bool = True):
    """Run market-making strategy on backtest data.
    
    Args:
        excel_file: Path to Excel file (relative to project root)
        max_sheets: Max sheets to process (None = all)
        config_file: Path to JSON config file
        generate_plots: Whether to generate plots after backtest
    
    Returns: dict of results per security
    """
    # Load market-making config from file if provided
    mm_config = load_strategy_config(config_file) if config_file else {}
    
    # Create handler
    mm_handler = create_mm_handler(config=mm_config)
    
    # Run backtest
    backtest = MarketMakingBacktest()
    print(f"\n{'='*70}")
    print(f"MARKET-MAKING BACKTEST")
    print(f"{'='*70}")
    print(f"Excel file: {excel_file}")
    print(f"Max sheets: {max_sheets if max_sheets else 'All'}")
    print(f"Config file: {config_file if config_file else 'None (using defaults)'}")
    print(f"{'='*70}\n")
    
    results = backtest.run_streaming(
        file_path=excel_file,
        handler=mm_handler,
        max_sheets=max_sheets,
        only_trades=False,  # Read all updates (bid/ask/trade)
    )
    
    # Print results
    print(f"\n{'='*70}")
    print(f"BACKTEST RESULTS")
    print(f"{'='*70}\n")
    
    for security in sorted(results.keys()):
        data = results[security]
        print(f"\n{security}:")
        print(f"  Rows processed: {data['rows']:,}")
        print(f"  Bids: {data['bid_count']:,} | Asks: {data['ask_count']:,} | Trades: {data['trade_count']:,}")
        print(f"  Last price: ${data.get('last_price', 0):.3f}")
        print(f"  Position: {data.get('position', 0):,}")
        print(f"  Total P&L: ${data.get('pnl', 0):.2f}")
        
        # Display trading day statistics
        market_dates = data.get('market_dates', set())
        strategy_dates = data.get('strategy_dates', set())
        num_market_days = len(market_dates)
        num_strategy_days = len(strategy_dates)
        missed_days = sorted(market_dates - strategy_dates)
        
        print(f"\n  Trading Statistics:")
        print(f"    Market trading days: {num_market_days}")
        print(f"    Strategy traded days: {num_strategy_days}")
        if missed_days:
            print(f"    Days with NO strategy trades: {len(missed_days)}")
            print(f"    Missed dates: {', '.join(str(d) for d in missed_days[:10])}")
            if len(missed_days) > 10:
                print(f"      ... and {len(missed_days) - 10} more dates")
        
        trades = data.get('trades', [])
        if trades:
            print(f"\n  Sample trades (first 5 of {len(trades)}):")
            for i, trade in enumerate(trades[:5], 1):  # Show first 5 trades
                fill_qty = trade.get('fill_qty', 0)
                fill_price = trade.get('fill_price', 0)
                pnl = trade.get('pnl', 0)
                side = trade.get('side', 'unknown')
                print(f"    {i}. {side.upper():>4} {fill_qty:>8,} @ ${fill_price:>7.3f} | P&L: ${pnl:>10.2f}")
            if len(trades) > 5:
                print(f"    ... and {len(trades) - 5} more trades")
    
    print(f"\n{'='*70}\n")
    
    # Print overall summary statistics
    total_market_days = 0
    total_strategy_days = 0
    total_missed_days = 0
    
    for security in sorted(results.keys()):
        data = results[security]
        market_dates = data.get('market_dates', set())
        strategy_dates = data.get('strategy_dates', set())
        total_market_days += len(market_dates)
        total_strategy_days += len(strategy_dates)
        total_missed_days += len(market_dates - strategy_dates)
    
    if total_market_days > 0:
        coverage_pct = (total_strategy_days / total_market_days) * 100
        print("OVERALL TRADING STATISTICS:")
        print(f"  Total market trading days (all securities): {total_market_days}")
        print(f"  Total strategy trading days: {total_strategy_days}")
        print(f"  Total days with NO strategy trades: {total_missed_days}")
        print(f"  Coverage: {coverage_pct:.1f}%")
        print(f"\n{'='*70}\n")
    
    # Generate plots for each security with trades
    if generate_plots:
        output_dir = Path('output')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for security in sorted(results.keys()):
            data = results[security]
            trades = data.get('trades', [])
            
            if not trades:
                continue
                
            # Read the CSV that was just written by the backtest
            csv_path = output_dir / f"{security.lower()}_trades_timeseries.csv"
            if not csv_path.exists():
                print(f"Warning: CSV not found for {security} at {csv_path}")
                continue
                
            try:
                # Load the CSV data
                trade_df = pd.read_csv(csv_path)
                trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])
                
                # Check if required columns exist
                if 'position' not in trade_df.columns or 'pnl' not in trade_df.columns:
                    print(f"Warning: Required columns (position/pnl) not found in CSV for {security}")
                    continue
                
                # Extract configuration parameters for this security
                sec_config = mm_config.get(security, {})
                base_quote_size = sec_config.get('quote_size', 50000)
                quote_size_bid = sec_config.get('quote_size_bid', base_quote_size)
                quote_size_ask = sec_config.get('quote_size_ask', base_quote_size)
                min_qty_front = sec_config.get('min_local_currency_before_quote', 25000)
                refill_period = sec_config.get('refill_interval_sec', 60)
                max_position = sec_config.get('max_position', 2000000)
                
                # Format quote size display
                if quote_size_bid == quote_size_ask:
                    quote_size_str = f"{quote_size_bid:,}"
                else:
                    quote_size_str = f"{quote_size_bid:,} / {quote_size_ask:,} (bid/ask)"
                
                # Create parameter text for legend
                param_text = (
                    f"Quote Size: {quote_size_str}\n"
                    f"Min Qty in Front: {min_qty_front:,}\n"
                    f"Refill Period: {refill_period}s\n"
                    f"Max Position: {max_position:,}"
                )
                
                # Create plots
                fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
                
                # Plot inventory
                axes[0].plot(trade_df['timestamp'], trade_df['position'], color='tab:blue', linewidth=1.5, label='Position')
                axes[0].set_title(f'{security} - Inventory vs Time')
                axes[0].set_ylabel('Position (shares)')
                axes[0].grid(True, linestyle='--', alpha=0.3)
                axes[0].axhline(y=0, color='red', linestyle='--', alpha=0.5)
                
                # Add parameter text box to the inventory plot
                axes[0].text(0.02, 0.98, param_text, transform=axes[0].transAxes,
                           fontsize=9, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
                
                # Plot P&L
                axes[1].plot(trade_df['timestamp'], trade_df['pnl'], color='tab:green', linewidth=1.5, label='P&L')
                axes[1].set_title(f'{security} - P&L vs Time (realized)')
                axes[1].set_ylabel('P&L (local currency)')
                axes[1].set_xlabel('Time')
                axes[1].grid(True, linestyle='--', alpha=0.3)
                axes[1].axhline(y=0, color='red', linestyle='--', alpha=0.5)
                
                fig.autofmt_xdate()
                plt.tight_layout()
                
                # Save plot
                plot_path = output_dir / f"{security.lower()}_inventory_pnl.png"
                plt.savefig(plot_path, dpi=144)
                plt.close(fig)
                
                print(f"Generated plot: {plot_path}")
                
            except Exception as e:
                print(f"Error generating plot for {security}: {e}")
    
    return results


if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser(description='Run market-making backtest (sample).')
    p.add_argument('--excel-file', '-f', default='data/raw/TickData_Sample.xlsx', help='Path to Excel file')
    p.add_argument('--max-sheets', '-m', default=None, type=int, help='Max number of sheets to process')
    p.add_argument('--config-file', '-c', default=None, help='Path to JSON config file with per-security params')
    p.add_argument('--no-plots', action='store_true', help='Disable plot generation')
    args = p.parse_args()

    results = run_mm_backtest(excel_file=args.excel_file, max_sheets=args.max_sheets, config_file=args.config_file, generate_plots=not args.no_plots)
