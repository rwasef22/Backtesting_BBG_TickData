#!/usr/bin/env python
"""Quick analysis: check trade volume during gap period."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

import pandas as pd
from src.data_loader import stream_sheets, preprocess_chunk_df
from datetime import date

gap_start = date(2025, 4, 22)
gap_end = date(2025, 6, 19)

print(f"Analyzing trade data in gap: {gap_start} to {gap_end}\n")

total_rows = 0
total_trades = 0
trades_in_gap = 0

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    chunk = preprocess_chunk_df(chunk)
    
    total_rows += len(chunk)
    trades = chunk[chunk['type'] == 'trade'].copy()
    total_trades += len(trades)
    
    # Filter to gap period
    trades['ts_date'] = pd.to_datetime(trades['timestamp']).dt.date
    gap_trades = trades[trades['ts_date'].between(gap_start, gap_end)]
    trades_in_gap += len(gap_trades)

print(f"Total rows: {total_rows:,}")
print(f"Total trades: {total_trades:,}")
print(f"Trades in gap ({gap_start} to {gap_end}): {trades_in_gap:,}")

if trades_in_gap > 0:
    print(f"\n✓ {trades_in_gap:,} trades exist during gap—strategy should be quoting.")
else:
    print(f"\n⚠️  NO trades during gap—market is inactive or halted.")

with open('gap_analysis_result.txt', 'w') as f:
    f.write(f"Gap analysis: {gap_start} to {gap_end}\n")
    f.write(f"Total rows: {total_rows:,}\n")
    f.write(f"Total trades: {total_trades:,}\n")
    f.write(f"Trades in gap: {trades_in_gap:,}\n")
