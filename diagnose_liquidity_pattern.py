"""
Diagnose liquidity patterns on non-trading vs trading days for ADNOCGAS.
"""
from datetime import date, datetime, time
import openpyxl

# Load ADNOCGAS data
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']
rows = list(sheet.iter_rows(min_row=4, values_only=True))

# Parse all ADNOCGAS data
all_data = []
for row in rows:
    timestamp_val = row[0]
    if isinstance(timestamp_val, datetime):
        timestamp = timestamp_val
    else:
        continue
    
    event_type = row[1]
    price = float(row[2]) if row[2] is not None else None
    quantity = float(row[3]) if row[3] is not None else None
    
    if price is not None and quantity is not None:
        all_data.append({
            'timestamp': timestamp,
            'date': timestamp.date(),
            'event_type': event_type,
            'price': price,
            'quantity': quantity
        })

# Group by date
from collections import defaultdict
by_date = defaultdict(list)
for d in all_data:
    by_date[d['date']].append(d)

print("="*80)
print("LIQUIDITY ANALYSIS: Non-trading vs Trading Days")
print("="*80)

# Non-trading days (from output)
non_trading_sample = [
    date(2025, 4, 16),
    date(2025, 4, 17),
    date(2025, 4, 22),
    date(2025, 4, 23)
]

# Trading days (need to identify from the data)
trading_sample = [
    date(2025, 4, 14),  # First day (should have trades)
    date(2025, 4, 15),  # Should have trades
    date(2025, 4, 21),  # Should have trades
]

MIN_CURRENCY = 13000

def analyze_liquidity(target_date, events):
    """Analyze liquidity throughout the day"""
    # Build orderbook state at different times
    times_to_check = [
        time(9, 30),   # Opening
        time(10, 5),   # After opening skip
        time(11, 0),   # Mid-morning
        time(12, 0),   # Noon
        time(13, 0),   # Afternoon
        time(14, 0),   # Pre-close
    ]
    
    bids = {}  # price -> quantity
    asks = {}
    
    liquidity_timeline = []
    
    for event in events:
        ts = event['timestamp']
        event_type = event['event_type'].lower()
        price = event['price']
        qty = event['quantity']
        
        # Update orderbook
        if event_type == 'bid':
            bids[price] = qty
        elif event_type == 'ask':
            asks[price] = qty
        
        # Check at specific times
        for check_time in times_to_check:
            if ts.time() >= check_time:
                # Calculate current liquidity
                if bids:
                    best_bid_price = max(bids.keys())
                    best_bid_qty = bids[best_bid_price]
                    bid_liquidity = best_bid_price * best_bid_qty
                else:
                    bid_liquidity = 0
                
                if asks:
                    best_ask_price = min(asks.keys())
                    best_ask_qty = asks[best_ask_price]
                    ask_liquidity = best_ask_price * best_ask_qty
                else:
                    ask_liquidity = 0
                
                liquidity_timeline.append({
                    'time': check_time,
                    'bid_liq': bid_liquidity,
                    'ask_liq': ask_liquidity,
                    'passes': bid_liquidity >= MIN_CURRENCY and ask_liquidity >= MIN_CURRENCY
                })
                
                times_to_check.remove(check_time)
                if not times_to_check:
                    break
        
        if not times_to_check:
            break
    
    return liquidity_timeline

print("\nNON-TRADING DAYS:")
print("-" * 80)
for dt in non_trading_sample:
    if dt in by_date:
        events = by_date[dt]
        print(f"\n{dt}: {len(events)} events")
        timeline = analyze_liquidity(dt, events)
        for entry in timeline:
            status = "✓ PASS" if entry['passes'] else "✗ FAIL"
            print(f"  {entry['time']}: Bid={entry['bid_liq']:>10,.0f} AED, Ask={entry['ask_liq']:>10,.0f} AED  {status}")

print("\n" + "="*80)
print("\nTRADING DAYS:")
print("-" * 80)
for dt in trading_sample:
    if dt in by_date:
        events = by_date[dt]
        print(f"\n{dt}: {len(events)} events")
        timeline = analyze_liquidity(dt, events)
        for entry in timeline:
            status = "✓ PASS" if entry['passes'] else "✗ FAIL"
            print(f"  {entry['time']}: Bid={entry['bid_liq']:>10,.0f} AED, Ask={entry['ask_liq']:>10,.0f} AED  {status}")

print("\n" + "="*80)
print("\nConclusion:")
print("If non-trading days consistently FAIL liquidity check and trading days PASS,")
print("the issue is that min_local_currency_before_quote=13,000 AED is too high")
print("for ADNOCGAS's typical orderbook depth on certain days.")
print("="*80)
