"""Check if trading days are split across chunk boundaries for ADNOCGAS."""

from src.data_loader import stream_sheets, preprocess_chunk_df

file_path = 'data/raw/TickData.xlsx'
chunk_size = 100000

print("Analyzing ADNOCGAS chunk boundaries...")
print("=" * 80)

chunk_num = 0
for sheet_name, chunk in stream_sheets(file_path, header_row=3, chunk_size=chunk_size, max_sheets=4):
    if 'ADNOCGAS' not in sheet_name:
        continue
    
    chunk_num += 1
    df = preprocess_chunk_df(chunk)
    
    if len(df) == 0:
        continue
    
    dates = df['timestamp'].dt.date.unique()
    first_date = df['timestamp'].iloc[0].date()
    last_date = df['timestamp'].iloc[-1].date()
    
    print(f"\nChunk {chunk_num}: {len(df)} rows")
    print(f"  First timestamp: {df['timestamp'].iloc[0]}")
    print(f"  Last timestamp: {df['timestamp'].iloc[-1]}")
    print(f"  Unique dates: {len(dates)}")
    print(f"  Date range: {first_date} to {last_date}")
    
    # Check if chunk ends mid-day (next chunk will start with same date)
    if last_date in dates and len(dates) > 1:
        print(f"  ⚠️ WARNING: Chunk may end mid-day on {last_date}")

print("\n" + "=" * 80)
print("Analysis complete.")
