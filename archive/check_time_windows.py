"""Check timestamp distribution in data to see if time windows are blocking everything"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import stream_sheets
import pandas as pd

print("Checking timestamp distribution in first security...")

file_path = 'data/raw/TickData.xlsx'
row_count = 0
time_buckets = {
    'before_930': 0,
    'opening_930_1000': 0,
    'silent_1000_1005': 0,
    'active_1005_1445': 0,
    'closing_1445_1500': 0,
    'after_1500': 0
}

for sheet_name, chunk_df in stream_sheets(file_path, header_row=3, chunk_size=100000):
    print(f"\nProcessing {sheet_name}...")
    print(f"Columns: {chunk_df.columns.tolist()}")
    
    # Check column names
    if 'Dates' in chunk_df.columns:
        timestamps = pd.to_datetime(chunk_df['Dates'])
    elif 'timestamp' in chunk_df.columns:
        timestamps = chunk_df['timestamp']
    else:
        print(f"Cannot find timestamp column!")
        break
    
    times = pd.to_datetime(timestamps).dt.time
    
    for t in times:
        row_count += 1
        
        if t < pd.Timestamp('09:30:00').time():
            time_buckets['before_930'] += 1
        elif t < pd.Timestamp('10:00:00').time():
            time_buckets['opening_930_1000'] += 1
        elif t < pd.Timestamp('10:05:00').time():
            time_buckets['silent_1000_1005'] += 1
        elif t < pd.Timestamp('14:45:00').time():
            time_buckets['active_1005_1445'] += 1
        elif t <= pd.Timestamp('15:00:00').time():
            time_buckets['closing_1445_1500'] += 1
        else:
            time_buckets['after_1500'] += 1
    
    if row_count >= 100000:
        break

print(f"\n{'='*80}")
print(f"TIMESTAMP DISTRIBUTION (first {row_count:,} rows)")
print(f"{'='*80}")

for bucket, count in time_buckets.items():
    pct = (count / row_count * 100) if row_count > 0 else 0
    print(f"{bucket:25s}: {count:8,} ({pct:5.2f}%)")

active_pct = (time_buckets['active_1005_1445'] / row_count * 100) if row_count > 0 else 0
print(f"\n{'='*80}")
print(f"ACTIVE TRADING WINDOW (10:05 - 14:45): {time_buckets['active_1005_1445']:,} rows ({active_pct:.2f}%)")
print(f"{'='*80}")

if active_pct < 10:
    print("\nWARNING: Less than 10% of data falls in active trading window!")
    print("This explains why no trades are generated.")
