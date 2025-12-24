"""Check which dates exist in Excel file and compare to strategy dates"""
import openpyxl
import pandas as pd
from datetime import datetime

print("Reading Excel file...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

# Get all dates in the Excel file
dates_in_excel = set()
row_count = 0
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:  # timestamp column
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            date_only = timestamp.date()
            dates_in_excel.add(date_only)
            row_count += 1
        except:
            pass

print(f"\nExcel file analysis:")
print(f"  Total rows processed: {row_count}")
print(f"  Unique dates: {len(dates_in_excel)}")

# Sort dates
excel_dates_sorted = sorted(dates_in_excel)
print(f"  Date range: {excel_dates_sorted[0]} to {excel_dates_sorted[-1]}")

# Get strategy dates from CSV
df = pd.read_csv('output/emaar_trades_timeseries.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['date'] = df['timestamp'].dt.date
strategy_dates = set(df['date'].unique())

print(f"\nStrategy dates: {len(strategy_dates)}")

# Find missing dates
missing_dates = sorted(dates_in_excel - strategy_dates)
print(f"\nMissing dates (first 30 of {len(missing_dates)}):")
for date in missing_dates[:30]:
    print(f"  {date}")

# Check for a gap
if len(missing_dates) > 0:
    print(f"\n Checking for consecutive missing dates...")
    consecutive_runs = []
    current_run = [missing_dates[0]]
    
    for i in range(1, len(missing_dates)):
        if (missing_dates[i] - missing_dates[i-1]).days <= 3:  # Allow weekends
            current_run.append(missing_dates[i])
        else:
            if len(current_run) > 5:
                consecutive_runs.append(current_run)
            current_run = [missing_dates[i]]
    
    if len(current_run) > 5:
        consecutive_runs.append(current_run)
    
    print(f"\nFound {len(consecutive_runs)} gaps of 5+ consecutive missing days:")
    for run in consecutive_runs:
        print(f"  Gap: {run[0]} to {run[-1]} ({len(run)} days)")
