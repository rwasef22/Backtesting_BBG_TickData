"""
Find which days ADNOCGAS traded vs didn't trade to identify first gap day.
"""
from datetime import date
import sys
sys.path.insert(0, 'c:/Ray/VS Code/tick-backtest-project')

from src.config_loader import load_strategy_config
from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
import openpyxl

# Run backtest for ADNOCGAS only
config = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=config)
backtest = MarketMakingBacktest()

print("Running backtest for ADNOCGAS (first 4 sheets)...")
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=4,  # ADNOCGAS is 4th sheet
    only_trades=False,
    write_csv=False
)

# Extract trading dates
adnocgas_result = results.get('ADNOCGAS', {})
trading_dates = sorted(adnocgas_result.get('strategy_dates', set()))

print(f"\nADNOCGAS Trading Analysis:")
print(f"Total trading days: {len(trading_dates)}")
print(f"Market days: {len(adnocgas_result.get('market_dates', set()))}")
print(f"Coverage: {len(trading_dates)/len(adnocgas_result.get('market_dates', set()))*100:.1f}%")
print(f"\nTotal trades: {len(adnocgas_result.get('trades', []))}")

# Get all market dates from the Excel file
print("\n" + "="*80)
print("Loading all market dates from Excel...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

all_market_dates = set()
for row in sheet.iter_rows(min_row=4, values_only=True):
    timestamp_val = row[0]
    if hasattr(timestamp_val, 'date'):
        all_market_dates.add(timestamp_val.date())

all_market_dates = sorted(all_market_dates)
trading_dates_set = set(trading_dates)

gap_days = [d for d in all_market_dates if d not in trading_dates_set]

print(f"\nTotal market dates in file: {len(all_market_dates)}")
print(f"Gap days (no trades): {len(gap_days)}")

print("\n" + "="*80)
print(f"FIRST 10 GAP DAYS (days with no trades):")
print("-"*80)
for i, gap_date in enumerate(gap_days[:10], 1):
    print(f"{i}. {gap_date.strftime('%Y-%m-%d (%A)')}")

if gap_days:
    print("\n" + "="*80)
    print(f"FIRST GAP DAY: {gap_days[0].strftime('%Y-%m-%d')}")
    print("="*80)

