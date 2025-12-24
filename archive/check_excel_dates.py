import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
import pandas as pd

dates = set()
count = 0

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1):
    # Preprocess to get standard columns
    chunk = preprocess_chunk_df(chunk)
    chunk['timestamp'] = pd.to_datetime(chunk['timestamp'])
    chunk_dates = chunk['timestamp'].dt.date.unique()
    dates.update(chunk_dates)
    count += len(chunk)

sorted_dates = sorted(dates)
print(f'Processed {count} rows')
print(f'Total unique dates: {len(sorted_dates)}')
print(f'Date range: {sorted_dates[0]} to {sorted_dates[-1]}')
print('\nAll dates:')
for d in sorted_dates:
    print(d)
