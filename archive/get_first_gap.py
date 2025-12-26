"""Quick check of first non-trading day."""
import sys
sys.path.insert(0,'src')
from market_making_backtest import MarketMakingBacktest
from mm_handler import create_mm_handler
from config_loader import load_strategy_config

config = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config)
backtest = MarketMakingBacktest()

print("Running backtest...")
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=4,
    only_trades=False,
    write_csv=False
)

adnocgas = results.get('ADNOCGAS', {})
trading_dates = sorted(adnocgas.get('strategy_dates', set()))
all_dates = sorted(adnocgas.get('market_dates', set()))
non_trading = [d for d in all_dates if d not in trading_dates]

print(f"\n{'='*80}")
print(f"ADNOCGAS Results:")
print(f"  Trading days: {len(trading_dates)}/{len(all_dates)}")
print(f"  Non-trading days: {len(non_trading)}")
print(f"\nFirst 5 trading dates:")
for d in trading_dates[:5]:
    print(f"  - {d}")
print(f"\nFirst 5 NON-trading dates:")
for d in non_trading[:5]:
    print(f"  - {d}")
print(f"\nFIRST GAP DAY TO ANALYZE: {non_trading[0]}")
print(f"{'='*80}")
