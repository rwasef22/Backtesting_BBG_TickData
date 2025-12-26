"""
Check how many market trading days ADNOCGAS has in the data.
"""
import openpyxl
from datetime import datetime, time

wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
ws = wb['ADNOCGAS UH Equity']

market_dates = set()
trade_dates = set()

print("Analyzing ADNOCGAS market days...")

for row in ws.iter_rows(min_row=4, values_only=True):
    if not row[0]:
        continue
    
    dt = row[0]
    if not isinstance(dt, datetime):
        continue
    
    date_str = dt.date().isoformat()
    
    # Track any market activity
    if row[1] in ['BID', 'ASK', 'TRADE']:
        market_dates.add(date_str)
    
    # Track actual trades
    if row[1] == 'TRADE':
        trade_dates.add(date_str)

print(f"\nTotal market days with data: {len(market_dates)}")
print(f"Days with actual trades: {len(trade_dates)}")

sorted_dates = sorted(market_dates)
print(f"\nFirst date: {sorted_dates[0]}")
print(f"Last date: {sorted_dates[-1]}")

print(f"\nFirst 10 market dates:")
for date in sorted_dates[:10]:
    has_trade = "✓" if date in trade_dates else "✗"
    print(f"  {date} {has_trade}")

wb.close()
