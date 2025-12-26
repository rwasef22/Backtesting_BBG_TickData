"""
Find the first non-trading day for ADNOCGAS quickly.
"""
from datetime import date
import openpyxl

print("Scanning ADNOCGAS dates...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

# Get all unique dates
dates_set = set()
for row in sheet.iter_rows(min_row=4, values_only=True):
    timestamp_val = row[0]
    if hasattr(timestamp_val, 'date'):
        dates_set.add(timestamp_val.date())
        if len(dates_set) >= 50:  # Just get first 50 dates
            break

all_dates = sorted(dates_set)
print(f"\nFirst 20 market dates in ADNOCGAS data:")
for i, d in enumerate(all_dates[:20], 1):
    print(f"{i:2}. {d.strftime('%Y-%m-%d (%A)')}")

print(f"\n\nWe'll analyze: {all_dates[0].strftime('%Y-%m-%d')}")
print(f"(First market date - should have trades if logic is correct)")
