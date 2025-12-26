"""Test just ADNOCGAS to see if refill time fix worked."""
import sys
sys.path.insert(0, 'src')

from market_making_backtest import MarketMakingBacktest
from mm_handler import create_mm_handler
from config_loader import load_strategy_config

config = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=config)

backtest = MarketMakingBacktest()

# Run with max_sheets parameter to only process first few sheets
# ADNOCGAS is the 4th sheet, so process first 4 sheets
print("Running backtest for ADNOCGAS only (processing first 4 sheets)...")
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=4,  # Only process up to ADNOCGAS
    only_trades=False,
    write_csv=False
)

adnocgas = results.get('ADNOCGAS', {})
market_days = len(adnocgas.get('market_dates', set()))
trading_days = len(adnocgas.get('strategy_dates', set()))

print(f"\n{'='*70}")
print(f"ADNOCGAS RESULT AFTER FIX:")
print(f"  Market days: {market_days}")
print(f"  Trading days: {trading_days}")
print(f"  Coverage: {trading_days/market_days*100:.1f}%" if market_days > 0 else "  Coverage: N/A")
print(f"  Total trades: {len(adnocgas.get('trades', []))}")
print(f"{'='*70}")
