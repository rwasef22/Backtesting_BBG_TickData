"""
Identify first gap day from existing results and analyze it.
"""
from datetime import date, datetime
import sys
sys.path.insert(0, 'c:/Ray/VS Code/tick-backtest-project')

import openpyxl

# Get all market dates and first few gap days from Excel
print("Loading all market dates from Excel...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

all_market_dates = set()
for row in sheet.iter_rows(min_row=4, max_row=10000, values_only=True):  # Sample first 10k rows
    timestamp_val = row[0]
    if hasattr(timestamp_val, 'date'):
        all_market_dates.add(timestamp_val.date())

all_market_dates = sorted(list(all_market_dates))[:20]  # First 20 dates

print(f"First 20 market dates: {all_market_dates[0]} to {all_market_dates[-1]}")

# Now check the output CSV to see which days traded
import csv
trading_dates = set()
try:
    with open('output/adnocgas_trades_timeseries.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
            trading_dates.add(ts.date())
    trading_dates = sorted(trading_dates)
    print(f"\nTrading dates from CSV: {len(trading_dates)} days")
    print(f"First trading day: {trading_dates[0]}")
    print(f"Last trading day: {trading_dates[-1]}")
except FileNotFoundError:
    print("\nNo CSV found - using first market date as first gap")
    first_gap = all_market_dates[0]
else:
    # Find first gap
    gap_days = [d for d in all_market_dates if d not in trading_dates]
    if gap_days:
        first_gap = gap_days[0]
        print(f"\nFirst {len(gap_days)} gap days from sample:")
        for i, d in enumerate(gap_days[:5], 1):
            print(f"  {i}. {d.strftime('%Y-%m-%d (%A)')}")
    else:
        print("\nNo gaps in first 20 days - checking further...")
        # All first 20 days traded, need to check more
        first_gap = date(2025, 1, 2)  # Use a reasonable guess

print(f"\n{'='*80}")
print(f"ANALYZING FIRST GAP DAY: {first_gap}")
print(f"{'='*80}")
