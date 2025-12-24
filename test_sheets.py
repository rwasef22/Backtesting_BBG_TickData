#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from src.data_loader import stream_sheets

print("Testing stream_sheets with max_sheets=None...", flush=True)

sheet_count = 0
row_count = 0

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=None, only_trades=False):
    sheet_count += 1
    row_count += len(chunk)
    print(f"  Sheet {sheet_count}: {sheet_name}, rows in chunk: {len(chunk)}", flush=True)
    if sheet_count >= 5:  # Limit to first 5 sheets for testing
        break

print(f"\nProcessed {sheet_count} sheets, {row_count:,} total rows", flush=True)
