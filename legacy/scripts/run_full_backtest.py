"""Run full parallel backtest with all securities."""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parallel_backtest import run_parallel_backtest
from src.config_loader import load_strategy_config

print("="*80)
print("FULL PARALLEL BACKTEST - ALL SECURITIES")
print("="*80)

# Load config
config = load_strategy_config('configs/v1_baseline_config.json')
print(f"Loaded config for {len(config)} securities")

# Run full backtest
start_time = time.time()

results = run_parallel_backtest(
    file_path='data/raw/TickData.xlsx',
    handler_module='src.strategies.v1_baseline.handler',
    handler_function='create_v1_handler',
    config=config,
    max_workers=4,
    max_sheets=None,  # All securities
    chunk_size=100000,
    write_csv=True,
    output_dir='output'
)

elapsed = time.time() - start_time

# Summary
print("\n" + "="*80)
print("BACKTEST COMPLETE")
print("="*80)
print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
print(f"Securities processed: {len(results)}")

total_trades = 0
total_pnl = 0.0
for security, result in sorted(results.items()):
    if 'error' not in result:
        trades = len(result.get('trades', []))
        pnl = result.get('pnl', 0.0)
        total_trades += trades
        total_pnl += pnl
        print(f"  {security}: {trades:,} trades, P&L: {pnl:,.2f} AED")
    else:
        print(f"  {security}: ERROR - {result.get('error', 'Unknown')}")

print("-"*80)
print(f"TOTAL: {total_trades:,} trades, P&L: {total_pnl:,.2f} AED")
print("="*80)
