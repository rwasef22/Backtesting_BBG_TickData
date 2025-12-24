#!/usr/bin/env python
import openpyxl
from datetime import datetime

wb = openpyxl.load_workbook('data/raw/TickData.xlsx', data_only=True)
ws = wb['EMAAR UH Equity']

dates = []
for row in ws.iter_rows(min_row=2, max_row=None, values_only=True):
    if row[0] is None:
        break
    try:
        ts = row[0]
        if isinstance(ts, datetime):
            dates.append(ts.date())
    except:
        pass

if dates:
    dates_set = sorted(set(dates))
    print(f'Total unique trading dates: {len(dates_set)}')
    print(f'Date range: {dates_set[0]} to {dates_set[-1]}')
    print()
    print(f'First 10 dates: {dates_set[:10]}')
    print(f'Last 10 dates: {dates_set[-10:]}')
    
    print()
    print('Gaps > 7 days:')
    for i in range(len(dates_set) - 1):
        gap_days = (dates_set[i+1] - dates_set[i]).days
        if gap_days > 7:
            print(f'  {dates_set[i]} -> {dates_set[i+1]}: {gap_days} days')
