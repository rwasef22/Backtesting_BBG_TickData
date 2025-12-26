"""Check if ADNOCGAS has ask data on non-trading days."""
import openpyxl
from datetime import date
from collections import defaultdict

wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

non_trading_days = [
    date(2025, 4, 16),
    date(2025, 4, 17),
    date(2025, 4, 22),
    date(2025, 4, 23)
]

trading_days = [
    date(2025, 4, 14),
    date(2025, 4, 21),
    date(2025, 4, 28)
]

# Count event types by date
event_counts = defaultdict(lambda: {'bid': 0, 'ask': 0, 'trade': 0})

for row in sheet.iter_rows(min_row=4, values_only=True):
    timestamp = row[0]
    if not hasattr(timestamp, 'date'):
        continue
    
    event_type = str(row[1]).lower() if row[1] else None
    if event_type in ['bid', 'ask', 'trade']:
        event_counts[timestamp.date()][event_type] += 1

print("="*80)
print("EVENT TYPE COUNTS BY DATE")
print("="*80)

print("\nNON-TRADING DAYS:")
print("-"*80)
for dt in non_trading_days:
    counts = event_counts[dt]
    total = counts['bid'] + counts['ask'] + counts['trade']
    print(f"{dt}: Total={total:>5} | Bid={counts['bid']:>4} | Ask={counts['ask']:>4} | Trade={counts['trade']:>4}")

print("\nTRADING DAYS:")
print("-"*80)
for dt in trading_days:
    counts = event_counts[dt]
    total = counts['bid'] + counts['ask'] + counts['trade']
    print(f"{dt}: Total={total:>5} | Bid={counts['bid']:>4} | Ask={counts['ask']:>4} | Trade={counts['trade']:>4}")

print("\n" + "="*80)
print("If non-trading days have ASK events, the issue is NOT missing data.")
print("If non-trading days have NO asks, that explains why the strategy can't quote.")
print("="*80)
