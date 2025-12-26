#!/usr/bin/env python
import openpyxl
from datetime import datetime

# Load the workbook
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', data_only=True)
ws = wb['EMAAR UH Equity']

# Collect all dates
dates = []
row_count = 0
for row in ws.iter_rows(min_row=2, max_row=None, values_only=True):
    row_count += 1
    if row[0] is None:
        break
    try:
        ts = row[0]
        if isinstance(ts, datetime):
            dates.append(ts.date())
    except Exception as e:
        pass

if dates:
    dates_set = sorted(set(dates))
    print(f'Total rows in EMAAR sheet: {row_count}')
    print(f'Total unique trading dates: {len(dates_set)}')
    print(f'Date range: {dates_set[0]} to {dates_set[-1]}')
    print()
    print(f'First 15 dates:')
    for d in dates_set[:15]:
        print(f'  {d}')
    print()
    print(f'Last 15 dates:')
    for d in dates_set[-15:]:
        print(f'  {d}')
    
    print()
    print('Date gaps > 10 days:')
    gap_found = False
    for i in range(len(dates_set) - 1):
        gap_days = (dates_set[i+1] - dates_set[i]).days
        if gap_days > 10:
            gap_found = True
            print(f'  {dates_set[i]} -> {dates_set[i+1]}: {gap_days} days')
    if not gap_found:
        print('  None found')
else:
    print('No dates found')
