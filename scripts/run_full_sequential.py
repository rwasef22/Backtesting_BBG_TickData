"""Run full SEQUENTIAL backtest with all securities."""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.strategies.v1_baseline.handler import create_v1_handler
from src.parquet_utils import ensure_parquet_data

print("="*80)
print("FULL SEQUENTIAL BACKTEST - ALL SECURITIES")
print("="*80)

# Ensure Parquet data exists (auto-convert if needed)
try:
    parquet_dir = ensure_parquet_data(
        excel_path='data/raw/TickData.xlsx',
        parquet_dir='data/parquet'
    )
    use_parquet = True
    data_path = parquet_dir
    print(f"Using Parquet format: {parquet_dir}\n")
except Exception as e:
    print(f"Parquet setup failed: {e}")
    print("Falling back to Excel format...\n")
    use_parquet = False
    data_path = 'data/raw/TickData.xlsx'

# Load config
config = load_strategy_config('configs/v1_baseline_config.json')
print(f"Loaded config for {len(config)} securities\n")

# Create handler
handler = create_v1_handler(config)

# Run full backtest
backtest = MarketMakingBacktest()

start_time = time.time()

if use_parquet:
    results = backtest.run_parquet_streaming(
        parquet_dir=data_path,
        handler=handler,
        chunk_size=100000,
        write_csv=True,
        output_dir='output'
    )
else:
    results = backtest.run_streaming(
        file_path=data_path,
        handler=handler,
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
    if result:
        trades = len(result.get('trades', []))
        pnl = result.get('pnl', 0.0)
        total_trades += trades
        total_pnl += pnl
        print(f"  {security}: {trades:,} trades, P&L: {pnl:,.2f} AED")

print("-"*80)
print(f"TOTAL: {total_trades:,} trades, P&L: {total_pnl:,.2f} AED")
print("="*80)
