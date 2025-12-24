import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
import pandas as pd

total_rows = 0
chunk_count = 0
last_timestamp = None

print("Streaming EMAAR data...")
for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    chunk_count += 1
    rows_in_chunk = len(chunk)
    total_rows += rows_in_chunk
    
    chunk = preprocess_chunk_df(chunk)
    chunk['timestamp'] = pd.to_datetime(chunk['timestamp'])
    first_ts = chunk['timestamp'].iloc[0]
    last_ts = chunk['timestamp'].iloc[-1]
    last_timestamp = last_ts
    
    print(f"Chunk {chunk_count}: {rows_in_chunk} rows | {first_ts} to {last_ts}")

print(f"\nTotal chunks: {chunk_count}")
print(f"Total rows: {total_rows}")
print(f"Last timestamp: {last_timestamp}")
