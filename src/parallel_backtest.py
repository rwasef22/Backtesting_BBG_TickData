"""Parallel backtest execution engine.

This module provides parallelized backtest execution using ProcessPoolExecutor
for per-security parallelization.
"""

import time
from pathlib import Path
from typing import Dict, Optional, Callable, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import pandas as pd


def get_handler_for_worker(strategy_name: str):
    """Get handler factory function for a strategy.
    
    This is called inside worker processes to import the handler.
    
    Args:
        strategy_name: Strategy name (e.g., 'v1_baseline')
    
    Returns:
        Handler factory function
    """
    import sys
    import os
    
    # Ensure project root in path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Handler name mapping
    handler_map = {
        'v1_baseline': 'create_v1_handler',
        'v2_price_follow_qty_cooldown': 'create_v2_price_follow_qty_cooldown_handler',
        'v2_1_stop_loss': 'create_v2_1_stop_loss_handler',
        'v3_liquidity_monitor': 'create_v3_handler',
    }
    
    handler_function = handler_map.get(strategy_name, f'create_{strategy_name}_handler')
    handler_module = f'src.strategies.{strategy_name}.handler'
    
    # Import the module
    module = __import__(handler_module, fromlist=[''])
    return getattr(module, handler_function)


def process_single_security_parquet(
    security_file: str,
    parquet_dir: str,
    handler_module: str,
    handler_function: str,
    config: dict,
    chunk_size: int = 100000
) -> tuple:
    """Process a single security from Parquet file in isolation.
    
    Args:
        security_file: Parquet filename (e.g., 'adnocgas.parquet')
        parquet_dir: Directory containing Parquet files
        handler_module: Module path for handler
        handler_function: Handler factory function name
        config: Configuration dict
        chunk_size: Rows per chunk
    
    Returns:
        Tuple of (security_name, results_dict, timing_info)
    """
    import sys
    import os
    import pandas as pd
    from pathlib import Path as PathLib
    
    # Ensure src is in path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    start_time = time.time()
    
    try:
        # Extract security name from filename
        security = PathLib(security_file).stem.upper()
        print(f"[Worker] Processing {security}...", flush=True)
        
        # Dynamically import handler factory
        print(f"[Worker] Importing handler...", flush=True)
        handler_module_obj = __import__(handler_module, fromlist=[''])
        handler_factory = getattr(handler_module_obj, handler_function)
        
        # Create handler in this process
        print(f"[Worker] Creating handler...", flush=True)
        handler = handler_factory(config)
        print(f"[Worker] Handler created", flush=True)
        
        # Read Parquet file
        print(f"[Worker] Reading Parquet file: {security_file}...", flush=True)
        parquet_file_path = PathLib(parquet_dir) / security_file
        df = pd.read_parquet(parquet_file_path)
        print(f"[Worker] Read {len(df):,} rows", flush=True)
        
        # Initialize results for this security
        from src.orderbook import OrderBook
        from src.data_loader import preprocess_chunk_df
        orderbook = OrderBook()
        state = {}  # Empty state - let handler initialize all fields
        
        # Process in chunks
        total_rows = len(df)
        chunk_num = 0
        for start_idx in range(0, total_rows, chunk_size):
            chunk_num += 1
            end_idx = min(start_idx + chunk_size, total_rows)
            chunk = df.iloc[start_idx:end_idx].copy()
            
            # Use preprocess_chunk_df to handle timestamp normalization
            chunk = preprocess_chunk_df(chunk)
            
            # Call handler - it updates state with trades, pnl, position
            state = handler(security, chunk, orderbook, state)
            if state is None:
                state = {'error': 'Handler returned None'}
                break
            
            state['rows'] = state.get('rows', 0) + len(chunk)
            print(f"[Worker] Chunk {chunk_num}: {len(state.get('trades', []))} trades", flush=True)
        
        # Extract results from state (handler populates these)
        results = {
            'trades': state.get('trades', []),
            'pnl': state.get('pnl', 0.0),
            'position': state.get('position', 0),
            'entry_price': state.get('entry_price', 0),
            'rows': state.get('rows', 0),
            'market_dates': state.get('market_dates', set()),
            'strategy_dates': state.get('strategy_dates', set())
        }
        
        elapsed = time.time() - start_time
        
        timing_info = {
            'elapsed': elapsed,
            'rows': results.get('rows', 0),
            'trades': len(results.get('trades', []))
        }
        
        print(f"[Worker] {security} complete: {timing_info['trades']} trades in {elapsed:.1f}s", flush=True)
        return (security, results, timing_info)
        
    except Exception as e:
        import traceback
        error_info = {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'elapsed': time.time() - start_time
        }
        security = PathLib(security_file).stem.upper()
        print(f"[Worker] ERROR {security}: {e}", flush=True)
        return (security, {'error': str(e)}, error_info)


def run_parallel_backtest_parquet(
    parquet_dir: str,
    handler_module: str,
    handler_function: str,
    config: dict,
    max_workers: Optional[int] = None,
    max_files: Optional[int] = None,
    chunk_size: int = 100000,
    output_dir: Optional[str] = 'output',
    write_csv: bool = True
) -> Dict:
    """Run backtest with per-security parallelization using Parquet files.
    
    Args:
        parquet_dir: Directory containing Parquet files
        handler_module: Module path for handler
        handler_function: Handler factory function name
        config: Configuration dictionary
        max_workers: Number of parallel workers (default: CPU count)
        max_files: Limit to first N securities (for testing)
        chunk_size: Rows per processing chunk
        output_dir: Output directory for results
        write_csv: Whether to write CSV output files
    
    Returns:
        Dictionary mapping security names to results
    """
    if max_workers is None:
        max_workers = cpu_count()
    
    print("="*80)
    print("PARALLEL BACKTEST (PARQUET)")
    print("="*80)
    print(f"Data source: {parquet_dir}")
    print(f"Workers: {max_workers}")
    print(f"Chunk size: {chunk_size:,} rows")
    if max_files:
        print(f"Max securities: {max_files}")
    print("="*80)
    print()
    
    # Find all Parquet files
    parquet_path = Path(parquet_dir)
    parquet_files = sorted(parquet_path.glob("*.parquet"))
    
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in {parquet_dir}")
    
    # Limit files if requested
    if max_files:
        parquet_files = parquet_files[:max_files]
    
    print(f"Found {len(parquet_files)} securities to process")
    
    # Process in parallel
    results = {}
    timings = {}
    completed_count = 0
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(
                process_single_security_parquet,
                parquet_file.name,
                parquet_dir,
                handler_module,
                handler_function,
                config,
                chunk_size
            ): parquet_file
            for parquet_file in parquet_files
        }
        
        print(f"Submitted {len(future_to_file)} tasks to process pool")
        print()
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            parquet_file = future_to_file[future]
            completed_count += 1
            
            try:
                security, result, timing_info = future.result()
                results[security] = result
                timings[security] = timing_info
                
                trades_count = len(result.get('trades', []))
                rows_count = result.get('rows', 0)
                elapsed = timing_info.get('elapsed', 0)
                
                if 'error' in result:
                    print(f"[{completed_count}/{len(parquet_files)}] [X] {security}: ERROR - {result['error']}")
                else:
                    print(f"[{completed_count}/{len(parquet_files)}] [OK] {security}: {trades_count:,} trades, {rows_count:,} rows in {elapsed:.1f}s")
            except Exception as e:
                print(f"[{completed_count}/{len(parquet_files)}] [X] {security}: EXCEPTION - {e}")
                results[parquet_file.stem.upper()] = {'error': str(e)}
    
    total_time = time.time() - start_time
    
    # Summary
    print()
    print("="*80)
    print("PARALLEL BACKTEST COMPLETE")
    print("="*80)
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Securities processed: {len(results)}")
    
    successful = [s for s, r in results.items() if 'error' not in r]
    failed = [s for s, r in results.items() if 'error' in r]
    
    print(f"  [OK] Successful: {len(successful)}")
    if failed:
        print(f"  [X] Failed: {len(failed)}: {failed}")
    
    total_trades = sum(len(results[s].get('trades', [])) for s in successful)
    total_rows = sum(results[s].get('rows', 0) for s in successful)
    
    print(f"\nTotal trades: {total_trades:,}")
    print(f"Total rows processed: {total_rows:,}")
    print(f"Throughput: {int(total_rows / total_time):,} rows/second")
    print("="*80)
    
    # Write results
    if write_csv and output_dir:
        write_results(results, output_dir)
    
    return results


def write_results(results: Dict, output_dir: str):
    """Write aggregated results to disk.
    
    Args:
        results: Results dict from parallel backtest
        output_dir: Output directory path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting results to {output_dir}...")
    
    # Write per-security trade files
    trades_written = 0
    for security, data in results.items():
        if 'error' in data:
            continue
            
        trades = data.get('trades', [])
        if trades:
            df = pd.DataFrame(trades)
            
            # Sort by timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Round numeric columns
            if 'realized_pnl' in df.columns:
                df['realized_pnl'] = df['realized_pnl'].round(0).astype(int)
            if 'pnl' in df.columns:
                df['pnl'] = df['pnl'].round(0).astype(int)
            if 'position' in df.columns:
                df['position'] = df['position'].round(0).astype(int)
            
            csv_path = output_path / f"{security.lower()}_trades_timeseries.csv"
            df.to_csv(csv_path, index=False)
            trades_written += 1
    
    print(f"  [OK] Wrote {trades_written} trade timeseries files")
    
    # Write summary
    summary_rows = []
    for security, data in results.items():
        if 'error' in data:
            summary_rows.append({
                'security': security,
                'trades': 0,
                'realized_pnl': 0,
                'position': 0,
                'market_dates': 0,
                'strategy_dates': 0,
                'error': data['error']
            })
        else:
            trades = data.get('trades', [])
            final_pnl = data.get('pnl', 0)
            final_position = data.get('position', 0)
            
            # Calculate from trades if pnl not in state
            if trades and 'realized_pnl' in trades[-1]:
                final_pnl = trades[-1]['realized_pnl']
            
            market_dates = data.get('market_dates', set())
            strategy_dates = data.get('strategy_dates', set())
            
            summary_rows.append({
                'security': security,
                'trades': len(trades),
                'realized_pnl': final_pnl,
                'position': final_position,
                'market_dates': len(market_dates) if isinstance(market_dates, set) else market_dates,
                'strategy_dates': len(strategy_dates) if isinstance(strategy_dates, set) else strategy_dates,
                'error': ''
            })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_path / 'backtest_summary.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"  [OK] Wrote summary: {summary_path}")


def run_parallel_backtest(
    file_path: str,
    handler_module: str,
    handler_function: str,
    config: dict,
    max_workers: Optional[int] = None,
    max_sheets: Optional[int] = None,
    chunk_size: int = 100000,
    header_row: int = 3,
    only_trades: bool = False,
    output_dir: Optional[str] = 'output',
    write_csv: bool = True
) -> Dict:
    """Run backtest with per-security parallelization using Excel file.
    
    This is the Excel-based version of parallel backtest.
    For better performance, use run_parallel_backtest_parquet with Parquet files.
    
    Args:
        file_path: Path to Excel file
        handler_module: Module path for handler
        handler_function: Handler factory function name  
        config: Configuration dictionary
        max_workers: Number of parallel workers (default: CPU count)
        max_sheets: Limit to first N securities (for testing)
        chunk_size: Rows per processing chunk
        header_row: Excel header row (1-indexed)
        only_trades: Filter to trade events only
        output_dir: Output directory for results
        write_csv: Whether to write CSV output files
    
    Returns:
        Dictionary mapping security names to results
    """
    print("="*80)
    print("PARALLEL BACKTEST (EXCEL)")
    print("="*80)
    print(f"NOTE: For faster performance, convert to Parquet format:")
    print(f"  python scripts/convert_excel_to_parquet.py")
    print("="*80)
    
    # For now, fall back to sequential processing with Excel
    # Full parallel Excel support can be added later if needed
    from src.market_making_backtest import MarketMakingBacktest
    
    # Import handler
    handler_module_obj = __import__(handler_module, fromlist=[''])
    handler_factory = getattr(handler_module_obj, handler_function)
    handler = handler_factory(config)
    
    # Run sequential backtest
    backtest = MarketMakingBacktest()
    results = backtest.run_streaming(
        file_path=file_path,
        handler=handler,
        max_sheets=max_sheets,
        chunk_size=chunk_size,
        write_csv=write_csv,
        output_dir=output_dir
    )
    
    return results

