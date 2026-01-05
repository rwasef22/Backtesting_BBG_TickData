"""Compare Excel vs Parquet data format performance and results.

Tests both data formats to ensure identical results and measure I/O speedup.
"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config_loader import load_strategy_config
from src.parallel_backtest import run_parallel_backtest
from run_parquet_backtest import run_parquet_backtest


def main():
    # Config
    config_path = 'configs/v1_baseline_config.json'
    excel_path = 'data/raw/TickData.xlsx'
    parquet_dir = 'data/parquet'
    max_sheets = 2  # Test with 2 securities
    
    print("="*80)
    print("EXCEL VS PARQUET COMPARISON")
    print("="*80)
    print(f"Testing with {max_sheets} securities")
    print()
    
    # Load config
    config = load_strategy_config(config_path)
    
    # === EXCEL RUN ===
    print("="*80)
    print("RUNNING WITH EXCEL FILES")
    print("="*80)
    
    start = time.time()
    results_excel = run_parallel_backtest(
        file_path=excel_path,
        handler_module='src.strategies.v1_baseline.handler',
        handler_function='create_v1_handler',
        config=config,
        max_sheets=max_sheets,
        max_workers=2,
        chunk_size=100000,
        write_csv=False
    )
    excel_time = time.time() - start
    
    print(f"\n[OK] Excel completed in {excel_time:.1f}s")
    
    # === PARQUET RUN ===
    print("\n" + "="*80)
    print("RUNNING WITH PARQUET FILES")
    print("="*80)
    
    start = time.time()
    results_parquet = run_parquet_backtest(
        strategy_name='v1_baseline',
        parquet_dir=parquet_dir,
        config_path=config_path,
        max_workers=2,
        max_sheets=max_sheets,
        chunk_size=100000,
        write_csv=False
    )
    parquet_time = time.time() - start
    
    print(f"\n[OK] Parquet completed in {parquet_time:.1f}s")
    
    # === COMPARISON ===
    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)
    
    # Get securities (sorted for consistent order)
    securities = sorted(set(results_excel.keys()) | set(results_parquet.keys()))
    
    print(f"\nSecurities: {len(securities)}")
    print(f"Excel time: {excel_time:.1f}s")
    print(f"Parquet time: {parquet_time:.1f}s")
    print(f"Speedup: {excel_time/parquet_time:.2f}x")
    
    print("\n" + "-"*80)
    print(f"{'Security':<15} {'Excel Trades':<12} {'Parq Trades':<12} {'Match':<8} {'Excel P&L':<15} {'Parq P&L':<15} {'Diff':<12}")
    print("-"*80)
    
    all_match = True
    total_excel_trades = 0
    total_parquet_trades = 0
    total_excel_pnl = 0.0
    total_parquet_pnl = 0.0
    
    for security in securities:
        excel_result = results_excel.get(security, {})
        parquet_result = results_parquet.get(security, {})
        
        excel_trades_list = excel_result.get('trades', [])
        parquet_trades_list = parquet_result.get('trades', [])
        
        excel_trades = len(excel_trades_list)
        parquet_trades = len(parquet_trades_list)
        
        excel_pnl = excel_result.get('pnl', 0.0)
        parquet_pnl = parquet_result.get('pnl', 0.0)
        
        total_excel_trades += excel_trades
        total_parquet_trades += parquet_trades
        total_excel_pnl += excel_pnl
        total_parquet_pnl += parquet_pnl
        
        trades_match = excel_trades == parquet_trades
        pnl_diff = abs(excel_pnl - parquet_pnl)
        pnl_match = pnl_diff < 0.01
        
        match = "[OK]" if (trades_match and pnl_match) else "[FAIL]"
        if not (trades_match and pnl_match):
            all_match = False
        
        print(f"{security:<15} {excel_trades:<12,} {parquet_trades:<12,} {match:<8} {excel_pnl:<15,.2f} {parquet_pnl:<15,.2f} {pnl_diff:<12,.2f}")
    
    print("-"*80)
    print(f"{'TOTAL':<15} {total_excel_trades:<12,} {total_parquet_trades:<12,} {'':8} {total_excel_pnl:<15,.2f} {total_parquet_pnl:<15,.2f} {abs(total_excel_pnl - total_parquet_pnl):<12,.2f}")
    print("-"*80)
    
    print("\n" + "="*80)
    if all_match:
        print("RESULT: [PASS] Excel and Parquet produce IDENTICAL results!")
        print(f"PERFORMANCE: Parquet is {excel_time/parquet_time:.2f}x faster for I/O")
    else:
        print("RESULT: [FAIL] Differences detected")
    print("="*80)
    
    return all_match


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
