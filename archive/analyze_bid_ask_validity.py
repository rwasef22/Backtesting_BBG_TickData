"""Count how many bid/ask have valid (non-zero) prices."""
import openpyxl

print("Loading TickData.xlsx...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

# Skip to data (row 4)
total_bids = 0
total_asks = 0
total_trades = 0
valid_bids = 0  # price > 0 and volume > 0
valid_asks = 0
zero_price_bids = 0
zero_volume_bids = 0
zero_price_asks = 0
zero_volume_asks = 0

for row in sheet.iter_rows(min_row=4, values_only=True):
    timestamp = row[0]
    event_type = row[1]
    price = row[2]
    volume = row[3]
    
    if event_type == 'BID':
        total_bids += 1
        if price is None or price == 0:
            zero_price_bids += 1
        if volume is None or volume == 0:
            zero_volume_bids += 1
        if price and price > 0 and volume and volume > 0:
            valid_bids += 1
    
    elif event_type == 'ASK':
        total_asks += 1
        if price is None or price == 0:
            zero_price_asks += 1
        if volume is None or volume == 0:
            zero_volume_asks += 1
        if price and price > 0 and volume and volume > 0:
            valid_asks += 1
    
    elif event_type == 'TRADE':
        total_trades += 1

wb.close()

print(f"\n{'='*70}")
print("ADNOCGAS Event Analysis")
print(f"{'='*70}")
print(f"\nBIDs:")
print(f"  Total: {total_bids:,}")
print(f"  Valid (price>0 AND volume>0): {valid_bids:,} ({valid_bids/total_bids*100:.1f}%)")
print(f"  Zero/None price: {zero_price_bids:,} ({zero_price_bids/total_bids*100:.1f}%)")
print(f"  Zero/None volume: {zero_volume_bids:,} ({zero_volume_bids/total_bids*100:.1f}%)")

print(f"\nASKs:")
print(f"  Total: {total_asks:,}")
print(f"  Valid (price>0 AND volume>0): {valid_asks:,} ({valid_asks/total_asks*100:.1f}%)")
print(f"  Zero/None price: {zero_price_asks:,} ({zero_price_asks/total_asks*100:.1f}%)")
print(f"  Zero/None volume: {zero_volume_asks:,} ({zero_volume_asks/total_asks*100:.1f}%)")

print(f"\nTRADEs: {total_trades:,}")

print(f"\n{'='*70}")
print(f"CONCLUSION:")
if valid_bids < total_bids * 0.5 or valid_asks < total_asks * 0.5:
    print("Many bid/ask events have zero/invalid prices or volumes!")
    print("This causes orderbook to be empty most of the time.")
else:
    print("Bid/ask events look valid. Issue must be elsewhere.")
