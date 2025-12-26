"""Test if the Excel file can be read and has data."""

import pandas as pd
from src.data_loader import stream_sheets

file_path = 'data/raw/TickData.xlsx'

print("Testing Excel file reading...")
print(f"File: {file_path}\n")

count = 0
for sheet_name, chunk in stream_sheets(file_path, chunk_size=10000, max_sheets=1):
    count += 1
    print(f"Chunk {count}: {len(chunk)} rows from {sheet_name}")
    if count == 1:
        print(f"\nFirst few rows:")
        print(chunk.head())
        print(f"\nColumns: {list(chunk.columns)}")
    if count >= 3:
        break

print(f"\n{file_path} can be read successfully!")
