#!/usr/bin/env python
"""Scan TickData.xlsx for missing calendar days (any event types)."""
from collections import Counter
import datetime as dt
import time
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import stream_sheets, preprocess_chunk_df


def main():
    t0 = time.time()
    counts = Counter()
    found_in_gap = False
    first_in_gap = None
    gap_start = dt.date(2025, 5, 9)
    gap_end = dt.date(2025, 6, 18)

    for sheet, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, only_trades=False):
        df = preprocess_chunk_df(chunk)
        dates = df['timestamp'].dt.date.dropna()
        counts.update(dates)

        # Early detect any date within the gap
        in_gap_dates = [d for d in dates.unique() if gap_start <= d <= gap_end]
        if in_gap_dates:
            found_in_gap = True
            first_in_gap = min(in_gap_dates)
            break  # stop early if any data exists in the gap window

    elapsed = time.time() - t0

    if not counts:
        msg = "No dates found in workbook."
        print(msg)
        return

    min_d, max_d = min(counts), max(counts)
    missing = []
    cur = min_d
    while cur <= max_d:
        if cur not in counts:
            missing.append(cur)
        cur += dt.timedelta(days=1)
    gap_missing = [d for d in missing if gap_start <= d <= gap_end]

    lines = [
        f"elapsed_sec {elapsed:.2f}",
        f"date_span {min_d} {max_d}",
        f"missing_total {len(missing)}",
        f"found_in_gap {found_in_gap}",
        f"first_in_gap {first_in_gap}",
        f"gap_missing_count {len(gap_missing)}",
        f"gap_missing_dates {gap_missing}",
    ]

    for ln in lines:
        print(ln)

    out_path = 'output/missing_dates.log'
    with open(out_path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
