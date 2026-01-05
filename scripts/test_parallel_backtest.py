"""Test script for parallel backtest implementation.

Run this to verify the parallel backtest works correctly with a small dataset.

Usage:
    python scripts/test_parallel_backtest.py
    python scripts/test_parallel_backtest.py --max-sheets 10
"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parallel_backtest import run_parallel_backtest
from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config


def test_parallel_vs_sequential(max_sheets=5):
    """Test parallel implementation against sequential baseline."""
    
    print("="*80)
    print("PARALLEL BACKTEST VALIDATION TEST")
    print("="*80)
    print(f"\nTesting with V1 baseline strategy on {max_sheets} securities")
    print()
    
    # Configuration
    strategy = 'v1_baseline'
    config_path = f'configs/{strategy}_config.json'
    data_path = 'data/raw/TickData.xlsx'
    workers = 2
    
    # Load config
    print(f"Loading config: {config_path}")
    try:
        config = load_strategy_config(config_path)
        print(f"  [OK] Loaded config for {len(config)} securities")
    except Exception as e:
        print(f"  [ERROR] Error loading config: {e}")
        return False
    
    # Test 1: Sequential baseline
    print("\n" + "-"*80)
    print("TEST 1: Sequential Version (Baseline)")
    print("-"*80)
    
    try:
        from src.strategies.v1_baseline.handler import create_v1_handler
        
        handler = create_v1_handler(config)
        backtest = MarketMakingBacktest(config=config)
        
        start = time.time()
        results_seq = backtest.run_streaming(
            file_path=data_path,
            handler=handler,
            max_sheets=max_sheets,
            write_csv=False
        )
        time_seq = time.time() - start
        
        trades_seq = sum(len(r.get('trades', [])) for r in results_seq.values())
        pnl_seq = sum(r.get('pnl', 0) for r in results_seq.values())
        
        print(f"\n[OK] Sequential test passed")
        print(f"  Time: {time_seq:.1f}s")
        print(f"  Securities: {len(results_seq)}")
        print(f"  Trades: {trades_seq:,}")
        print(f"  Total P&L: {pnl_seq:,.2f}")
        
    except Exception as e:
        print(f"\n[ERROR] Sequential test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Parallel version
    print("\n" + "-"*80)
    print("TEST 2: Parallel Version")
    print("-"*80)
    
    try:
        start = time.time()
        results_par = run_parallel_backtest(
            file_path=data_path,
            handler_module='src.strategies.v1_baseline.handler',
            handler_function='create_v1_handler',
            config=config,
            max_workers=workers,
            max_sheets=max_sheets,
            write_csv=False
        )
        time_par = time.time() - start
        
        trades_par = sum(len(r.get('trades', [])) for r in results_par.values() if 'error' not in r)
        pnl_par = sum(r.get('pnl', 0) for r in results_par.values() if 'error' not in r)
        
        print(f"\n[OK] Parallel test passed")
        print(f"  Time: {time_par:.1f}s")
        print(f"  Securities: {len(results_par)}")
        print(f"  Trades: {trades_par:,}")
        print(f"  Total P&L: {pnl_par:,.2f}")
        
    except Exception as e:
        print(f"\n[ERROR] Parallel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Compare results
    print("\n" + "-"*80)
    print("TEST 3: Results Comparison")
    print("-"*80)
    
    print(f"\nSequential:")
    print(f"  Time:   {time_seq:.1f}s")
    print(f"  Trades: {trades_seq:,}")
    print(f"  P&L:    {pnl_seq:,.2f}")
    
    print(f"\nParallel:")
    print(f"  Time:   {time_par:.1f}s")
    print(f"  Trades: {trades_par:,}")
    print(f"  P&L:    {pnl_par:,.2f}")
    
    speedup = time_seq / time_par if time_par > 0 else 0
    print(f"\nSpeedup: {speedup:.2f}x")
    print(f"Time saved: {time_seq - time_par:.1f}s")
    
    # Verify results match
    all_passed = True
    
    if trades_seq != trades_par:
        print(f"\n⚠ WARNING: Trade count mismatch!")
        print(f"  Sequential: {trades_seq:,}")
        print(f"  Parallel:   {trades_par:,}")
        print(f"  Difference: {abs(trades_seq - trades_par):,}")
        all_passed = False
    else:
        print(f"\n[OK] Trade counts match: {trades_seq:,}")
    
    pnl_diff = abs(pnl_seq - pnl_par)
    if pnl_diff > 1.0:  # 1 AED tolerance
        print(f"\n⚠ WARNING: P&L mismatch!")
        print(f"  Sequential: {pnl_seq:,.2f}")
        print(f"  Parallel:   {pnl_par:,.2f}")
        print(f"  Difference: {pnl_diff:,.2f} AED")
        all_passed = False
    else:
        print(f"[OK] P&L matches: {pnl_seq:,.2f} AED (diff: {pnl_diff:.2f})")
    
    print(f"[OK] Number of securities: {len(results_seq)} vs {len(results_par)}")
    
    # Per-security comparison
    print(f"\nPer-security summary:")
    for security in sorted(results_seq.keys()):
        seq_trades = len(results_seq[security].get('trades', []))
        par_trades = len(results_par.get(security, {}).get('trades', []))
        seq_pnl = results_seq[security].get('pnl', 0)
        par_pnl = results_par.get(security, {}).get('pnl', 0)
        
        match = "[OK]" if (seq_trades == par_trades and abs(seq_pnl - par_pnl) < 0.01) else "[FAIL]"
        print(f"  {match} {security}: {seq_trades} trades, P&L={seq_pnl:,.2f}")
    
    # Final verdict
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("="*80)
        print("\nParallel backtest produces identical results to sequential version!")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*80)
        print("\nParallel backtest results differ from sequential version.")
    
    if time_par < time_seq:
        print(f"\n📊 Performance: {speedup:.2f}x speedup ({time_seq - time_par:.1f}s saved)")
    
    return all_passed


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test parallel backtest implementation')
    parser.add_argument('--max-sheets', type=int, default=5,
                       help='Number of securities to test (default: 5)')
    
    args = parser.parse_args()
    
    success = test_parallel_vs_sequential(max_sheets=args.max_sheets)
    sys.exit(0 if success else 1)
