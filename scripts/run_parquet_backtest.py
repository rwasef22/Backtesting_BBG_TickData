"""Run backtest using Parquet files for 5-10x faster I/O.

This script uses per-security Parquet files instead of Excel,
providing significantly faster I/O performance when combined with parallel processing.

Performance:
- Excel Sequential: 8-10 minutes
- Excel Parallel: 2-3 minutes (4 cores)
- Parquet Parallel: 30-60 seconds (4 cores) ← 8-15x faster!

Prerequisites:
1. Install pyarrow: pip install pyarrow
2. Convert Excel to Parquet:
   python scripts/convert_excel_to_parquet.py

Usage:
    # Basic usage
    python scripts/run_parquet_backtest.py --strategy v1_baseline
    
    # Quick test
    python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5
    
    # Custom workers
    python scripts/run_parquet_backtest.py --strategy v1_baseline --workers 8
"""
import argparse
import sys
import os
import time
from pathlib import Path
from multiprocessing import cpu_count

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parquet_loader import list_available_securities, get_parquet_info
from src.parallel_backtest import write_results
from src.config_loader import load_strategy_config
from src.market_making_backtest import MarketMakingBacktest

# Try to import parallel processing
try:
    from concurrent.futures import ProcessPoolExecutor, as_completed
    _HAS_PARALLEL = True
except ImportError:
    _HAS_PARALLEL = False


def get_handler_info(strategy_name: str) -> tuple:
    """Get handler module and function name for a strategy."""
    module_path = f"src.strategies.{strategy_name}.handler"
    function_name = f"create_{strategy_name}_handler"
    return module_path, function_name


def process_parquet_security(
    security: str,
    parquet_dir: str,
    handler_module: str,
    handler_function: str,
    config: dict,
    chunk_size: int = 100000
) -> tuple:
    """Process a single security from Parquet file (runs in worker process)."""
    import sys
    import os
    
    # Ensure src is in path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    start_time = time.time()
    
    try:
        # Import Parquet loader and handler
        from src.parquet_loader import read_single_parquet
        
        # Dynamically import handler factory
        handler_module_obj = __import__(handler_module, fromlist=[''])
        handler_factory = getattr(handler_module_obj, handler_function)
        
        # Create handler in this process
        handler = handler_factory(config)
        
        # Read Parquet file
        df = read_single_parquet(parquet_dir, security)
        
        # Create backtest instance (process-local)
        from src.market_making_backtest import MarketMakingBacktest
        backtest = MarketMakingBacktest(config=config)
        
        # Format sheet name for compatibility
        sheet_name = f"{security} UH Equity"
        
        # Process in chunks
        total_rows = len(df)
        for start_idx in range(0, total_rows, chunk_size):
            end_idx = min(start_idx + chunk_size, total_rows)
            chunk = df.iloc[start_idx:end_idx].copy()
            
            state = backtest.handler_state.get(sheet_name, {})
            state = handler(sheet_name, chunk, backtest.orderbook, state) or state
            backtest.handler_state[sheet_name] = state
        
        elapsed = time.time() - start_time
        
        result = backtest.handler_state.get(sheet_name, {})
        trades = result.get('trades', [])
        
        timing_info = {
            'elapsed': elapsed,
            'rows': total_rows,
            'trades': len(trades)
        }
        
        return (security, result, timing_info)
        
    except Exception as e:
        import traceback
        error_info = {
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        elapsed = time.time() - start_time
        return (security, error_info, {'elapsed': elapsed, 'rows': 0, 'trades': 0})


def run_parquet_backtest(
    strategy_name: str,
    parquet_dir: str = 'data/parquet',
    config_path: str = None,
    max_workers: int = None,
    max_sheets: int = None,
    chunk_size: int = 100000,
    output_dir: str = None,
    write_csv: bool = True
):
    """Run parallel backtest using Parquet files.
    
    Args:
        strategy_name: Strategy identifier (e.g., 'v1_baseline')
        parquet_dir: Directory containing Parquet files
        config_path: Path to strategy config JSON
        max_workers: Number of parallel workers
        max_sheets: Limit to first N securities
        chunk_size: Rows per chunk
        output_dir: Output directory
        write_csv: Write CSV files
    """
    if max_workers is None:
        max_workers = cpu_count()
    
    if output_dir is None:
        output_dir = f'output/{strategy_name}'
    
    print("="*80)
    print(f"PARQUET PARALLEL BACKTEST - {strategy_name}")
    print("="*80)
    print(f"Workers:     {max_workers} (CPU count: {cpu_count()})")
    print(f"Parquet dir: {parquet_dir}")
    print(f"Output dir:  {output_dir}")
    print("="*80)
    
    start_time = time.time()
    
    # Check Parquet directory
    parquet_info = get_parquet_info(parquet_dir)
    if not parquet_info['exists']:
        print(f"\nERROR: Parquet directory not found: {parquet_dir}")
        print("Run conversion first: python scripts/convert_excel_to_parquet.py")
        return {}
    
    print(f"\nFound {parquet_info['num_files']} Parquet files")
    print(f"Total size: {parquet_info['total_size_mb']:.1f} MB")
    
    # Get securities
    securities = list_available_securities(parquet_dir)
    if max_sheets:
        securities = securities[:max_sheets]
    
    print(f"\nProcessing {len(securities)} securities:")
    print(f"  {', '.join(securities)}")
    print()
    
    # Load config
    if config_path is None:
        config_path = f'configs/{strategy_name}_config.json'
    
    config = load_strategy_config(config_path)
    print(f"Loaded config: {config_path}")
    print()
    
    # Get handler info
    handler_module, handler_function = get_handler_info(strategy_name)
    
    # Run parallel processing
    results = {}
    timings = {}
    completed_count = 0
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_security = {
            executor.submit(
                process_parquet_security,
                security,
                parquet_dir,
                handler_module,
                handler_function,
                config,
                chunk_size
            ): security
            for security in securities
        }
        
        print(f"Submitted {len(future_to_security)} tasks to process pool")
        print()
        
        # Collect results as they complete
        for future in as_completed(future_to_security):
            security = future_to_security[future]
            completed_count += 1
            
            try:
                sec_name, result, timing_info = future.result()
                results[sec_name] = result
                timings[sec_name] = timing_info
                
                trades_count = len(result.get('trades', []))
                rows_count = timing_info.get('rows', 0)
                elapsed = timing_info.get('elapsed', 0)
                
                if 'error' in result:
                    print(f"[{completed_count}/{len(securities)}] ✗ {sec_name}: ERROR - {result['error']}")
                else:
                    print(f"[{completed_count}/{len(securities)}] ✓ {sec_name}: {trades_count:,} trades, {rows_count:,} rows in {elapsed:.1f}s")
                
            except Exception as e:
                print(f"[{completed_count}/{len(securities)}] ✗ {security}: EXCEPTION - {e}")
                results[security] = {'error': str(e)}
    
    total_elapsed = time.time() - start_time
    
    # Print summary
    print()
    print("="*80)
    print("PARALLEL BACKTEST COMPLETE")
    print("="*80)
    print(f"Total time:   {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
    print(f"Securities:   {len(results)}")
    
    total_trades = sum(len(r.get('trades', [])) for r in results.values())
    total_rows = sum(timings.get(s, {}).get('rows', 0) for s in results.keys())
    
    print(f"Total trades: {total_trades:,}")
    print(f"Total rows:   {total_rows:,}")
    
    if total_elapsed > 0:
        print(f"Throughput:   {total_rows/total_elapsed:.0f} rows/sec")
    
    print("="*80)
    
    # Write results
    if write_csv:
        print(f"\nWriting results to {output_dir}/")
        write_results(results, output_dir)
        print(f"✓ Results written to {output_dir}/")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Run backtest using Parquet files for fast I/O',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python scripts/run_parquet_backtest.py --strategy v1_baseline
  
  # Quick test
  python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5
  
  # Custom workers
  python scripts/run_parquet_backtest.py --strategy v1_baseline --workers 8
  
Prerequisites:
  1. Install pyarrow: pip install pyarrow
  2. Convert Excel: python scripts/convert_excel_to_parquet.py
        """
    )
    
    parser.add_argument('--strategy', '-s', required=True,
                       help='Strategy name (e.g., v1_baseline)')
    parser.add_argument('--parquet-dir', default='data/parquet',
                       help='Parquet directory (default: data/parquet)')
    parser.add_argument('--config', '-c', default=None,
                       help='Config file (default: configs/{strategy}_config.json)')
    parser.add_argument('--workers', '-w', type=int, default=None,
                       help=f'Number of workers (default: {cpu_count()} = CPU count)')
    parser.add_argument('--max-sheets', type=int, default=None,
                       help='Limit to first N securities (for testing)')
    parser.add_argument('--chunk-size', type=int, default=100000,
                       help='Rows per chunk (default: 100000)')
    parser.add_argument('--output-dir', '-o', default=None,
                       help='Output directory (default: output/{strategy})')
    parser.add_argument('--no-csv', action='store_true',
                       help='Skip writing CSV files')
    
    args = parser.parse_args()
    
    # Check if Parquet directory exists
    if not Path(args.parquet_dir).exists():
        print(f"ERROR: Parquet directory not found: {args.parquet_dir}")
        print("\nRun conversion first:")
        print("  python scripts/convert_excel_to_parquet.py")
        sys.exit(1)
    
    # Check if pyarrow is installed
    try:
        import pyarrow.parquet
    except ImportError:
        print("ERROR: pyarrow not installed")
        print("Install with: pip install pyarrow")
        sys.exit(1)
    
    # Run backtest
    run_parquet_backtest(
        strategy_name=args.strategy,
        parquet_dir=args.parquet_dir,
        config_path=args.config,
        max_workers=args.workers,
        max_sheets=args.max_sheets,
        chunk_size=args.chunk_size,
        output_dir=args.output_dir,
        write_csv=not args.no_csv
    )


if __name__ == '__main__':
    main()
