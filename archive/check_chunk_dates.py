"""Check which dates are in which chunks"""
import openpyxl
from datetime import datetime
from collections import defaultdict

wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

chunk_dates = defaultdict(set)
row_count = 0
current_chunk = 1

for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            row_count += 1
            chunk_dates[current_chunk].add(timestamp.date())
            
            if row_count % 100000 == 0:
                current_chunk += 1
        except:
            pass

for chunk_num in sorted(chunk_dates.keys()):
    dates = sorted(chunk_dates[chunk_num])
    print(f"Chunk {chunk_num}: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    
    # Check if May 9 is in this chunk
    target = datetime(2025, 5, 9).date()
    if target in dates:
        print(f"  *** May 9th is in this chunk! ***")
