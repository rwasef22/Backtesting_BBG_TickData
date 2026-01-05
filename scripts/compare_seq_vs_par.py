"""Direct comparison of sequential vs parallel backtest results.

Runs both versions on same securities and compares trade counts and P&L.
"""
import sys
import os
import time
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config_loader import load_strategy_config
from src.market_making_backtest import MarketMakingBacktest
from src.parallel_backtest import run_parallel_backtest


def main():
    # Config
    config_path = 'configs/v1_baseline_config.json'
    data_path = 'data/raw/TickData.xlsx'
    max_sheets = 2  # Test with 2 securities
    
    print("="*80)
    print("SEQUENTIAL VS PARALLEL COMPARISON")
    print("="*80)
    print(f"Testing with {max_sheets} securities")
    print()
    
    # Load config
    config = load_strategy_config(config_path)
    
    # === SEQUENTIAL RUN ===
    print("="*80)
    print("RUNNING SEQUENTIAL VERSION")
    print("="*80)
    
    from src.strategies.v1_baseline.handler import create_v1_handler
    handler = create_v1_handler(config)
    
    backtest = MarketMakingBacktest()
    
    start = time.time()
    results_seq = backtest.run_streaming(
        file_path=data_path,
        handler=handler,
        chunk_size=100000,
        max_sheets=max_sheets,
        write_csv=False  # Don't write files
    )
    seq_time = time.time() - start
    
    print(f"\n[OK] Sequential completed in {seq_time:.1f}s")
    
    # === PARALLEL RUN ===
    print("\n" + "="*80)
    print("RUNNING PARALLEL VERSION")
    print("="*80)
    
    start = time.time()
    results_par = run_parallel_backtest(
        file_path=data_path,
        handler_module='src.strategies.v1_baseline.handler',
        handler_function='create_v1_handler',
        config=config,
        max_sheets=max_sheets,
        max_workers=2,
        chunk_size=100000,
        write_csv=False  # Don't write files
    )
    par_time = time.time() - start
    
    print(f"\n[OK] Parallel completed in {par_time:.1f}s")
    
    # === COMPARISON ===
    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)
    
    # Get securities (sorted for consistent order)
    securities = sorted(set(results_seq.keys()) | set(results_par.keys()))
    
    print(f"\nSecurities: {len(securities)}")
    print(f"Sequential time: {seq_time:.1f}s")
    print(f"Parallel time: {par_time:.1f}s")
    print(f"Speedup: {seq_time/par_time:.2f}x")
    
    print("\n" + "-"*80)
    print(f"{'Security':<15} {'Seq Trades':<12} {'Par Trades':<12} {'Match':<8} {'Seq P&L':<15} {'Par P&L':<15} {'P&L Diff':<12}")
    print("-"*80)
    
    all_match = True
    total_seq_trades = 0
    total_par_trades = 0
    total_seq_pnl = 0.0
    total_par_pnl = 0.0
    
    for security in securities:
        seq_result = results_seq.get(security, {})
        par_result = results_par.get(security, {})
        
        seq_trades_list = seq_result.get('trades', [])
        par_trades_list = par_result.get('trades', [])
        
        seq_trades = len(seq_trades_list)
        par_trades = len(par_trades_list)
        
        seq_pnl = seq_result.get('pnl', 0.0)
        par_pnl = par_result.get('pnl', 0.0)
        
        total_seq_trades += seq_trades
        total_par_trades += par_trades
        total_seq_pnl += seq_pnl
        total_par_pnl += par_pnl
        
        trades_match = seq_trades == par_trades
        pnl_diff = abs(seq_pnl - par_pnl)
        pnl_match = pnl_diff < 0.01
        
        match = "[OK]" if (trades_match and pnl_match) else "[FAIL]"
        if not (trades_match and pnl_match):
            all_match = False
        
        print(f"{security:<15} {seq_trades:<12,} {par_trades:<12,} {match:<8} {seq_pnl:<15,.2f} {par_pnl:<15,.2f} {pnl_diff:<12,.2f}")
    
    print("-"*80)
    print(f"{'TOTAL':<15} {total_seq_trades:<12,} {total_par_trades:<12,} {'':8} {total_seq_pnl:<15,.2f} {total_par_pnl:<15,.2f} {abs(total_seq_pnl - total_par_pnl):<12,.2f}")
    print("-"*80)
    
    print("\n" + "="*80)
    if all_match:
        print("RESULT: [PASS] Sequential and parallel produce IDENTICAL results!")
    else:
        print("RESULT: [FAIL] Differences detected")
    print("="*80)
    
    return all_match


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
