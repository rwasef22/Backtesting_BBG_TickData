"""Generic strategy runner script for any market-making strategy variation.

This script provides a unified interface to run any strategy variation
by specifying the strategy name. Results are automatically organized
into strategy-specific directories.

Usage:
    python scripts/run_strategy.py --strategy v1_baseline
    python scripts/run_strategy.py --strategy v2_aggressive_refill --max-sheets 5
    python scripts/run_strategy.py --strategy v1_baseline --output-dir custom_output
"""
import argparse
import sys
import os
import time
from datetime import datetime
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.parquet_utils import ensure_parquet_data


def import_strategy_handler(strategy_name: str):
    """Dynamically import handler for given strategy.
    
    Args:
        strategy_name: Strategy identifier (e.g., 'v1_baseline')
        
    Returns:
        Handler factory function
    """
    try:
        # Import the handler module
        module_path = f"src.strategies.{strategy_name}.handler"
        handler_module = __import__(module_path, fromlist=[''])
        
        # Map strategy names to handler function names
        handler_map = {
            'v1_baseline': 'create_v1_handler',
            'v2_price_follow_qty_cooldown': 'create_v2_price_follow_qty_cooldown_handler',
            'v2_1_stop_loss': 'create_v2_1_stop_loss_handler',
            'v3_liquidity_monitor': 'create_v3_liquidity_monitor_handler'
        }
        
        # Get handler function name
        handler_name = handler_map.get(strategy_name, 'create_handler')
        
        return getattr(handler_module, handler_name)
    except (ImportError, AttributeError) as e:
        print(f"Error importing strategy '{strategy_name}': {e}")
        print(f"Make sure the strategy exists at: src/strategies/{strategy_name}/handler.py")
        sys.exit(1)


def save_results(results: dict, strategy_name: str, output_dir: str):
    """Save backtest results to strategy-specific directories.
    
    Args:
        results: Results dictionary from backtest
        strategy_name: Strategy identifier
        output_dir: Base output directory
    """
    # Create strategy-specific output directory
    strategy_output = os.path.join(output_dir, strategy_name)
    os.makedirs(strategy_output, exist_ok=True)
    
    # Save per-security trade timeseries
    for security, data in results.items():
        if 'trades' in data and len(data['trades']) > 0:
            trades_df = pd.DataFrame(data['trades'])
            csv_path = os.path.join(strategy_output, f"{security}_trades_timeseries.csv")
            trades_df.to_csv(csv_path, index=False)
            print(f"Saved: {csv_path}")
    
    # Create summary
    summary_rows = []
    for security, data in results.items():
        trades = data.get('trades', [])
        if len(trades) > 0:
            summary_rows.append({
                'security': security,
                'trades': len(trades),
                'final_position': data.get('position', 0),
                'realized_pnl': data.get('pnl', 0.0),
                'rows_processed': data.get('rows', 0),
                'market_dates': len(data.get('market_dates', set())),
                'strategy_dates': len(data.get('strategy_dates', set()))
            })
    
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_path = os.path.join(strategy_output, "backtest_summary.csv")
        summary_df.to_csv(summary_path, index=False)
        print(f"Saved: {summary_path}")
        
        # Print summary to console
        print("\n" + "="*80)
        print(f"BACKTEST SUMMARY - {strategy_name.upper()}")
        print("="*80)
        print(summary_df.to_string(index=False))
        print("="*80)
        
        # Aggregate stats
        total_trades = summary_df['trades'].sum()
        total_pnl = summary_df['realized_pnl'].sum()
        print(f"\nTotal Trades: {total_trades:,}")
        print(f"Total Realized P&L: {total_pnl:,.2f} AED")


def main():
    parser = argparse.ArgumentParser(
        description="Run market-making backtest with any strategy variation"
    )
    parser.add_argument(
        '--strategy',
        type=str,
        required=True,
        help='Strategy name (e.g., v1_baseline, v2_aggressive_refill)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='configs/mm_config.json',
        help='Path to config file (default: configs/mm_config.json)'
    )
    parser.add_argument(
        '--data',
        type=str,
        default='data/raw/TickData.xlsx',
        help='Path to input Excel file (default: data/raw/TickData.xlsx)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Base output directory (default: output)'
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
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"MARKET-MAKING BACKTEST - {args.strategy.upper()}")
    print(f"{'='*80}")
    print(f"Strategy: {args.strategy}")
    print(f"Config: {args.config}")
    print(f"Data: {args.data}")
    print(f"Output: {args.output_dir}/{args.strategy}")
    print(f"Max Sheets: {args.max_sheets or 'All'}")
    print(f"Chunk Size: {args.chunk_size:,}")
    print(f"{'='*80}\n")
    
    # Ensure Parquet data exists (auto-convert if needed)
    print("Checking data format...")
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
    
    # Load configuration
    print("Loading configuration...")
    config = load_strategy_config(args.config)
    print(f"Loaded config for {len(config)} securities\n")
    
    # Import strategy handler
    print(f"Importing strategy handler: {args.strategy}...")
    handler_factory = import_strategy_handler(args.strategy)
    handler = handler_factory(config=config)
    print(f"Strategy handler loaded successfully\n")
    
    # Run backtest
    print("Starting backtest...")
    start_time = time.time()
    
    backtest = MarketMakingBacktest()
    if use_parquet:
        # Use Parquet streaming through parquet_loader
        from src.parquet_loader import stream_parquet_files
        
        results = backtest.run_streaming_from_generator(
            data_generator=stream_parquet_files(
                parquet_dir=data_path,
                chunk_size=args.chunk_size,
                max_files=args.max_sheets
            ),
            handler=handler
        )
    else:
        results = backtest.run_streaming(
            file_path=data_path,
            handler=handler,
            max_sheets=args.max_sheets,
            chunk_size=args.chunk_size
        )
    
    elapsed = time.time() - start_time
    print(f"\nBacktest completed in {elapsed:.1f} seconds")
    
    # Save results
    print("\nSaving results...")
    save_results(results, args.strategy, args.output_dir)
    
    print(f"\n{'='*80}")
    print("DONE!")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
