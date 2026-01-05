"""Parallel strategy runner for market-making strategies.

This script runs strategies using parallel processing, where each security
is processed in a separate process. This provides significant speedup on
multi-core systems (3-8x faster depending on CPU cores).

Usage:
    # Run V1 baseline in parallel with 4 workers
    python scripts/run_parallel_backtest.py --strategy v1_baseline --workers 4
    
    # Quick test with 5 securities
    python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 5 --workers 2
    
    # Compare timing against sequential version
    python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark

For comparison with sequential version, use:
    python scripts/run_strategy.py --strategy v1_baseline
"""
import argparse
import sys
import os
import time
from pathlib import Path
from multiprocessing import cpu_count

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parallel_backtest import run_parallel_backtest
from src.config_loader import load_strategy_config
from src.parquet_utils import ensure_parquet_data


def get_handler_info(strategy_name: str) -> tuple:
    """Get handler module and function name for a strategy.
    
    Args:
        strategy_name: Strategy identifier (e.g., 'v1_baseline')
        
    Returns:
        Tuple of (module_path, function_name)
    """
    # Map strategy names to handler module paths
    module_path = f"src.strategies.{strategy_name}.handler"
    
    # Map strategy names to handler function names
    # Different strategies use different naming conventions
    handler_map = {
        'v1_baseline': 'create_v1_handler',
        'v2_price_follow_qty_cooldown': 'create_v2_price_follow_qty_cooldown_handler',
        'v2_1_stop_loss': 'create_v2_1_stop_loss_handler',
        'v3_liquidity_monitor': 'create_v3_liquidity_monitor_handler'
    }
    
    # Try mapped name first, fallback to generic
    function_name = handler_map.get(strategy_name, 'create_handler')
    
    return module_path, function_name


def run_benchmark_comparison(args):
    """Run both sequential and parallel versions for timing comparison."""
    from src.market_making_backtest import MarketMakingBacktest
    
    print("="*80)
    print("BENCHMARK: Sequential vs Parallel Comparison")
    print("="*80)
    
    # Load config
    if args.config:
        config = load_strategy_config(args.config)
    else:
        config_path = f"configs/{args.strategy}_config.json"
        config = load_strategy_config(config_path)
    
    # Get handler info
    handler_module, handler_function = get_handler_info(args.strategy)
    
    # Sequential version
    print("\n1. SEQUENTIAL VERSION")
    print("-"*80)
    
    try:
        # Import handler dynamically
        handler_module_obj = __import__(handler_module, fromlist=[''])
        handler_factory = getattr(handler_module_obj, handler_function)
        handler = handler_factory(config)
        
        backtest = MarketMakingBacktest(config=config)
        
        start_seq = time.time()
        results_seq = backtest.run_streaming(
            file_path=args.data,
            handler=handler,
            max_sheets=args.max_sheets,
            chunk_size=args.chunk_size,
            header_row=3,
            write_csv=False
        )
        time_seq = time.time() - start_seq
        
        trades_seq = sum(len(r.get('trades', [])) for r in results_seq.values())
        
        print(f"\nSequential results:")
        print(f"  Time: {time_seq:.1f}s ({time_seq/60:.1f} minutes)")
        print(f"  Securities: {len(results_seq)}")
        print(f"  Total trades: {trades_seq:,}")
        
    except Exception as e:
        print(f"ERROR: Sequential version failed: {e}")
        import traceback
        traceback.print_exc()
        time_seq = None
        trades_seq = None
    
    # Parallel version
    print("\n2. PARALLEL VERSION")
    print("-"*80)
    
    start_par = time.time()
    results_par = run_parallel_backtest(
        file_path=args.data,
        handler_module=handler_module,
        handler_function=handler_function,
        config=config,
        max_workers=args.workers,
        max_sheets=args.max_sheets,
        chunk_size=args.chunk_size,
        header_row=3,
        write_csv=False
    )
    time_par = time.time() - start_par
    
    trades_par = sum(len(r.get('trades', [])) for r in results_par.values() if 'error' not in r)
    
    # Comparison
    print("\n" + "="*80)
    print("BENCHMARK RESULTS")
    print("="*80)
    print(f"Sequential: {time_seq:.1f}s ({time_seq/60:.1f} min)" if time_seq else "Sequential: FAILED")
    print(f"Parallel:   {time_par:.1f}s ({time_par/60:.1f} min)")
    
    if time_seq:
        speedup = time_seq / time_par
        print(f"\nSpeedup:    {speedup:.2f}x")
        print(f"Time saved: {time_seq - time_par:.1f}s ({(time_seq - time_par)/60:.1f} min)")
        
        # Verify results match
        if trades_seq == trades_par:
            print(f"\n✓ Results verified: Both versions produced {trades_seq:,} trades")
        else:
            print(f"\n⚠ Warning: Trade count mismatch!")
            print(f"  Sequential: {trades_seq:,} trades")
            print(f"  Parallel:   {trades_par:,} trades")
    
    print("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Run market-making strategy backtest with parallel processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic parallel run with auto-detected CPU count
  python scripts/run_parallel_backtest.py --strategy v1_baseline
  
  # Use 4 workers for testing
  python scripts/run_parallel_backtest.py --strategy v1_baseline --workers 4
  
  # Quick test with limited securities
  python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 5 --workers 2
  
  # Benchmark comparison (sequential vs parallel)
  python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark
  
  # Custom config and output directory
  python scripts/run_parallel_backtest.py --strategy v2_price_follow_qty_cooldown \\
      --config configs/v2_price_follow_qty_cooldown_config.json \\
      --output-dir output/v2_parallel
        """
    )
    
    parser.add_argument('--strategy', '-s', required=True,
                       help='Strategy name (e.g., v1_baseline, v2_price_follow_qty_cooldown)')
    parser.add_argument('--config', '-c',
                       help='Path to config JSON (default: configs/{strategy}_config.json)')
    parser.add_argument('--data', '-d', default='data/raw/TickData.xlsx',
                       help='Path to tick data Excel file')
    parser.add_argument('--output-dir', '-o',
                       help='Output directory (default: output/{strategy}_parallel)')
    parser.add_argument('--workers', '-w', type=int, default=None,
                       help=f'Number of parallel workers (default: {cpu_count()} - CPU count)')
    parser.add_argument('--max-sheets', type=int, default=None,
                       help='Limit to first N securities (for testing)')
    parser.add_argument('--chunk-size', type=int, default=100000,
                       help='Rows per processing chunk (default: 100000)')
    parser.add_argument('--benchmark', '-b', action='store_true',
                       help='Run benchmark comparison vs sequential version')
    parser.add_argument('--only-trades', action='store_true',
                       help='Filter to trade events only (faster but may affect some strategies)')
    
    args = parser.parse_args()
    
    # Run benchmark if requested
    if args.benchmark:
        run_benchmark_comparison(args)
        return
    
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
    
    # Load configuration
    if args.config:
        config = load_strategy_config(args.config)
    else:
        config_path = f"configs/{args.strategy}_config.json"
        if not os.path.exists(config_path):
            print(f"ERROR: Config file not found: {config_path}")
            print(f"Specify config with --config or create {config_path}")
            sys.exit(1)
        config = load_strategy_config(config_path)
    
    print(f"Loaded config: {len(config)} securities")
    
    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"output/{args.strategy}_parallel"
    
    # Get handler info
    handler_module, handler_function = get_handler_info(args.strategy)
    
    # Verify handler exists
    try:
        handler_module_obj = __import__(handler_module, fromlist=[''])
        if not hasattr(handler_module_obj, handler_function):
            # Try generic name
            handler_function = 'create_handler'
            if not hasattr(handler_module_obj, handler_function):
                print(f"ERROR: Handler function not found in {handler_module}")
                print(f"Expected: {handler_function} or create_handler")
                sys.exit(1)
    except ImportError as e:
        print(f"ERROR: Cannot import handler module: {handler_module}")
        print(f"Make sure strategy exists at: src/strategies/{args.strategy}/handler.py")
        print(f"Error: {e}")
        sys.exit(1)
    
    # Run parallel backtest
    if use_parquet:
        from src.parallel_backtest import run_parallel_backtest_parquet
        results = run_parallel_backtest_parquet(
            parquet_dir=data_path,
            handler_module=handler_module,
            handler_function=handler_function,
            config=config,
            max_workers=args.workers,
            max_files=args.max_sheets,
            chunk_size=args.chunk_size,
            output_dir=output_dir,
            write_csv=True
        )
    else:
        results = run_parallel_backtest(
            file_path=data_path,
            handler_module=handler_module,
            handler_function=handler_function,
            config=config,
            max_workers=args.workers,
            max_sheets=args.max_sheets,
            chunk_size=args.chunk_size,
            header_row=3,
            only_trades=args.only_trades,
            output_dir=output_dir,
            write_csv=True
        )
    
    # Print final summary
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    
    successful = [s for s, r in results.items() if 'error' not in r]
    failed = [s for s, r in results.items() if 'error' in r]
    
    print(f"Strategy: {args.strategy}")
    print(f"Output directory: {output_dir}")
    print(f"Securities processed: {len(successful)}/{len(results)}")
    
    if failed:
        print(f"\nFailed securities: {', '.join(failed)}")
    
    # Per-security summary
    print("\nPer-security results:")
    for security in sorted(successful):
        data = results[security]
        trades = len(data.get('trades', []))
        pnl = data.get('pnl', 0)
        position = data.get('position', 0)
        market_days = len(data.get('market_dates', set()))
        strategy_days = len(data.get('strategy_dates', set()))
        
        print(f"  {security:12s}: {trades:6,} trades, P&L: {pnl:12,.0f}, "
              f"Days: {strategy_days}/{market_days}, Position: {position:8,.0f}")
    
    # Aggregate totals
    total_trades = sum(len(results[s].get('trades', [])) for s in successful)
    total_pnl = sum(results[s].get('pnl', 0) for s in successful)
    
    print(f"\n{'TOTAL':12s}: {total_trades:6,} trades, P&L: {total_pnl:12,.0f}")
    print("="*80)
    
    print(f"\n[OK] Results saved to: {output_dir}/")
    print(f"  - backtest_summary.csv")
    print(f"  - {{security}}_trades_timeseries.csv (per security)")


if __name__ == '__main__':
    main()
