"""Quick test of parallel backtest functionality."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def main():
    """Main test function."""
    print("="*80)
    print("QUICK PARALLEL BACKTEST TEST")
    print("="*80)

    # Test 1: Import test
    print("\n[1/5] Testing imports...")
    try:
        from src.config_loader import load_strategy_config
        from src.parallel_backtest import run_parallel_backtest
        from src.market_making_backtest import MarketMakingBacktest
        print("  [OK] All imports successful")
    except Exception as e:
        print(f"  [ERROR] Import failed: {e}")
        sys.exit(1)

    # Test 2: Config load
    print("\n[2/5] Loading config...")
    try:
        config = load_strategy_config('configs/v1_baseline_config.json')
        print(f"  [OK] Loaded config for {len(config)} securities")
    except Exception as e:
        print(f"  [ERROR] Config load failed: {e}")
        sys.exit(1)

    # Test 3: Data file check
    print("\n[3/5] Checking data file...")
    data_path = 'data/raw/TickData.xlsx'
    if os.path.exists(data_path):
        size_mb = os.path.getsize(data_path) / 1024 / 1024
        print(f"  [OK] Data file exists ({size_mb:.1f} MB)")
    else:
        print(f"  [ERROR] Data file not found: {data_path}")
        sys.exit(1)

    # Test 4: Create handler
    print("\n[4/5] Creating handler...")
    try:
        from src.strategies.v1_baseline.handler import create_v1_handler
        handler = create_v1_handler(config)
        print("  [OK] Handler created successfully")
    except Exception as e:
        print(f"  [ERROR] Handler creation failed: {e}")
        sys.exit(1)

    # Test 5: Quick parallel test
    print("\n[5/5] Running quick parallel test (1 security)...")
    try:
        results = run_parallel_backtest(
            file_path='data/raw/TickData.xlsx',
            handler_module='src.strategies.v1_baseline.handler',
            handler_function='create_v1_handler',
            config=config,
            max_sheets=1,
            max_workers=2,
            chunk_size=100000
        )
        
        if results:
            security = list(results.keys())[0]
            result = results[security]
            trades = result.get('trades', [])
            pnl = result.get('pnl', 0.0)
            print(f"  [OK] Completed: {len(trades)} trades, P&L: {pnl:.2f} AED")
        else:
            print("  [ERROR] No results returned")
            sys.exit(1)
            
    except Exception as e:
        print(f"  [ERROR] Parallel test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)


if __name__ == '__main__':
    main()
