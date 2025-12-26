"""Check what event types exist in ADNOCGAS data."""
import openpyxl
from collections import Counter

print("Loading TickData.xlsx...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

event_types = Counter()
row_count = 0

for row in sheet.iter_rows(min_row=2, values_only=True):
    row_count += 1
    event_type = row[1]
    if event_type:
        event_types[event_type] += 1

wb.close()

print(f"\nTotal rows: {row_count:,}")
print(f"\nEvent type breakdown:")
for event_type, count in event_types.most_common():
    print(f"  {event_type}: {count:,} ({count/row_count*100:.1f}%)")
