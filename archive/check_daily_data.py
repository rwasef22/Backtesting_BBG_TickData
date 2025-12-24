#!/usr/bin/env python
"""Check daily row counts to see if any dates have zero data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

import pandas as pd
from src.data_loader import stream_sheets, preprocess_chunk_df
from collections import defaultdict

print("Checking daily row counts...\n")

daily_counts = defaultdict(lambda: {'total': 0, 'bids': 0, 'asks': 0, 'trades': 0})

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    chunk = preprocess_chunk_df(chunk)
    chunk['date'] = pd.to_datetime(chunk['timestamp']).dt.date
    
    for date_val in chunk['date'].unique():
        day_data = chunk[chunk['date'] == date_val]
        daily_counts[date_val]['total'] += len(day_data)
        daily_counts[date_val]['bids'] += len(day_data[day_data['type'] == 'bid'])
        daily_counts[date_val]['asks'] += len(day_data[day_data['type'] == 'ask'])
        daily_counts[date_val]['trades'] += len(day_data[day_data['type'] == 'trade'])

# Sort by date
sorted_dates = sorted(daily_counts.keys())

print(f"Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
print(f"Total dates with data: {len(sorted_dates)}\n")

# Find gaps
print("Checking for date gaps:")
from datetime import timedelta
for i in range(len(sorted_dates) - 1):
    current = sorted_dates[i]
    next_date = sorted_dates[i + 1]
    gap_days = (next_date - current).days
    if gap_days > 7:
        print(f"  GAP: {current} -> {next_date} ({gap_days} days)")

# Show a sample of days with very low activity
print("\nDates with < 100 total rows:")
low_activity = [(d, daily_counts[d]) for d in sorted_dates if daily_counts[d]['total'] < 100]
for d, counts in low_activity[:20]:
    print(f"  {d}: {counts['total']} rows (bids={counts['bids']}, asks={counts['asks']}, trades={counts['trades']})")

if not low_activity:
    print("  None found—all dates have >= 100 rows")
