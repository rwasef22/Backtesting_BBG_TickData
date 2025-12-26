"""Debug why the sweep is getting 0 trades."""

import json
import pandas as pd
from src.mm_handler import create_mm_handler
from src.market_making_backtest import MarketMakingBacktest

# Load config
with open('configs/v1_baseline_config.json', 'r') as f:
    config = json.load(f)

# Create handler with 180s interval (baseline)
handler = create_mm_handler(config=config)

# Create backtest
backtest = MarketMakingBacktest()

# Run on a single security (ADNOCGAS - high liquidity)
file_path = 'data/raw/TickData.xlsx'
results = backtest.run_streaming(
    file_path=file_path,
    handler=handler,
    max_sheets=1,  # Just EMAAR first
    chunk_size=50000
)

print("\n" + "="*80)
print("RESULTS")
print("="*80)
print(f"Results keys: {results.keys()}")
for security, sec_results in results.items():
    print(f"\n{security}:")
    print(f"  Type: {type(sec_results)}")
    if isinstance(sec_results, dict):
        for key, value in sec_results.items():
            if isinstance(value, (int, float, str)):
                print(f"  {key}: {value}")
            elif isinstance(value, pd.DataFrame):
                print(f"  {key}: DataFrame with {len(value)} rows")
            else:
                print(f"  {key}: {type(value)}")
