import sys
sys.path.insert(0, 'scripts')
from run_mm_backtest import run_mm_backtest

result = run_mm_backtest(excel_file='data/raw/TickData.xlsx', config_file='configs/mm_config.json', generate_plots=False)
adnocgas = result.get('ADNOCGAS', {})
market_days = len(adnocgas.get('market_dates', set()))
trading_days = len(adnocgas.get('strategy_dates', set()))
print(f"\n\n{'='*70}")
print(f"ADNOCGAS RESULT AFTER REFILL TIME FIX:")
print(f"Market days: {market_days}")
print(f"Trading days: {trading_days}")
print(f"Coverage: {trading_days/market_days*100:.1f}%")
print(f"{'='*70}")
