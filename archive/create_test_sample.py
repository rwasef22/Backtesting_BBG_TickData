#!/usr/bin/env python
"""Create a smaller sample from TickData.xlsx for quick testing"""
import pandas as pd
import os

# Read first security from TickData.xlsx and take first 10k rows
excel_file = 'data/raw/TickData.xlsx'
xls = pd.ExcelFile(excel_file)

print(f"Available sheets: {xls.sheet_names[:5]}...")

# Read first sheet
sheet_name = xls.sheet_names[0]
print(f"Reading first 10k rows from {sheet_name}...", flush=True)

df = pd.read_excel(excel_file, sheet_name=sheet_name, header=2, nrows=10000)
print(f"  Loaded {len(df)} rows with columns: {list(df.columns)}")

# Save to a small test file
os.makedirs('data/test', exist_ok=True)
test_file = 'data/test/TickData_Small.xlsx'

with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=2)
    ws = writer.sheets[sheet_name]
    ws['A1'] = sheet_name
    ws['A2'] = 'Test data - first 10k rows'

print(f"Created {test_file}")
