"""Direct orderbook state diagnostic for ADNOCGAS - focus on bid/ask availability."""
import openpyxl
from collections import defaultdict
from datetime import datetime, time

print("Loading TickData.xlsx...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

# Track orderbook state per day
daily_state = defaultdict(lambda: {
    'total_rows': 0,
    'valid_window_rows': 0,  # Outside silent/auction periods
    'bid_updates': 0,
    'ask_updates': 0,
    'trade_updates': 0,
    'moments_with_bid': 0,
    'moments_with_ask': 0,
    'moments_with_both': 0,
    'best_bid_samples': [],
    'best_ask_samples': []
})

# Current orderbook state
current_bids = {}
current_asks = {}
last_trade = None

# Time window functions
def is_in_opening_auction(ts):
    return time(9, 30) <= ts.time() < time(10, 0)

def is_in_silent_period(ts):
    return time(10, 0) <= ts.time() < time(10, 5)

def is_in_closing_auction(ts):
    return time(14, 45) <= ts.time() < time(15, 0)

def is_valid_trading_window(ts):
    return not (is_in_opening_auction(ts) or is_in_silent_period(ts) or is_in_closing_auction(ts))

print("Processing ADNOCGAS rows...")
row_count = 0
last_date = None

for row in sheet.iter_rows(min_row=2, values_only=True):
    row_count += 1
    if row_count % 100000 == 0:
        print(f"  Processed {row_count:,} rows...")
    
    timestamp = row[0]
    event_type = row[1]
    price = row[2]
    volume = row[3]
    
    if not isinstance(timestamp, datetime):
        continue
    
    current_date = timestamp.date()
    
    # Clear orderbook on new trading day
    if last_date is not None and last_date != current_date:
        current_bids.clear()
        current_asks.clear()
        last_trade = None
    last_date = current_date
    
    daily_state[current_date]['total_rows'] += 1
    
    # Check if in valid trading window
    if is_valid_trading_window(timestamp):
        daily_state[current_date]['valid_window_rows'] += 1
        
        # Apply orderbook update
        if event_type == 'bid':
            daily_state[current_date]['bid_updates'] += 1
            if price is not None and volume is not None:
                if volume > 0:
                    current_bids[price] = volume
                elif price in current_bids:
                    del current_bids[price]
        
        elif event_type == 'ask':
            daily_state[current_date]['ask_updates'] += 1
            if price is not None and volume is not None:
                if volume > 0:
                    current_asks[price] = volume
                elif price in current_asks:
                    del current_asks[price]
        
        elif event_type == 'trade':
            daily_state[current_date]['trade_updates'] += 1
            last_trade = (price, volume)
        
        # Check orderbook state AFTER update
        best_bid = max(current_bids.keys()) if current_bids else None
        best_ask = min(current_asks.keys()) if current_asks else None
        
        if best_bid is not None:
            daily_state[current_date]['moments_with_bid'] += 1
        if best_ask is not None:
            daily_state[current_date]['moments_with_ask'] += 1
        if best_bid is not None and best_ask is not None:
            daily_state[current_date]['moments_with_both'] += 1
            
            # Sample first few
            if len(daily_state[current_date]['best_bid_samples']) < 3:
                bid_qty = current_bids[best_bid]
                ask_qty = current_asks[best_ask]
                daily_state[current_date]['best_bid_samples'].append((best_bid, bid_qty, best_bid * bid_qty))
                daily_state[current_date]['best_ask_samples'].append((best_ask, ask_qty, best_ask * ask_qty))

wb.close()

# Load trading days from previous backtest
print("\nIdentifying trading vs non-trading days...")
# We know from previous runs: 76 trading days, 60 non-trading days
# Let's identify which dates had actual strategy trades

# For now, analyze all days
all_dates = sorted(daily_state.keys())
print(f"\nTotal dates with data: {len(all_dates)}")

# Analyze days with low orderbook availability
print(f"\n{'='*100}")
print("ORDERBOOK STATE ANALYSIS - Days with poor bid/ask availability")
print(f"{'='*100}\n")
print(f"{'Date':<12} {'TotalRows':<10} {'ValidRows':<10} {'BidUpd':<8} {'AskUpd':<8} "
      f"{'MomBid':<8} {'MomAsk':<8} {'MomBoth':<9} {'BothPct':<8}")
print("="*100)

# Identify days with poor orderbook state
poor_orderbook_days = []
for date in all_dates:
    state = daily_state[date]
    valid_rows = state['valid_window_rows']
    
    if valid_rows > 0:
        both_pct = (state['moments_with_both'] / valid_rows) * 100
        
        # Flag days with less than 50% both-side availability
        if both_pct < 50:
            poor_orderbook_days.append(date)
            print(f"{date} {state['total_rows']:>9} {valid_rows:>9} "
                  f"{state['bid_updates']:>7} {state['ask_updates']:>7} "
                  f"{state['moments_with_bid']:>7} {state['moments_with_ask']:>7} "
                  f"{state['moments_with_both']:>8} {both_pct:>7.1f}%")

print(f"\nDays with <50% both-side orderbook availability: {len(poor_orderbook_days)}")

# Show sample values for a few poor days
print(f"\n{'='*100}")
print("SAMPLE ORDERBOOK VALUES (First 3 valid moments)")
print(f"{'='*100}\n")

for date in poor_orderbook_days[:5]:
    state = daily_state[date]
    print(f"\n{date}:")
    if state['best_bid_samples']:
        print("  Bid samples:")
        for bid_price, bid_qty, bid_value in state['best_bid_samples']:
            print(f"    Price: {bid_price:.2f}, Qty: {bid_qty:,}, Value: ${bid_value:,.2f}")
        print("  Ask samples:")
        for ask_price, ask_qty, ask_value in state['best_ask_samples']:
            print(f"    Price: {ask_price:.2f}, Qty: {ask_qty:,}, Value: ${ask_value:,.2f}")
    else:
        print("  No bid/ask samples captured (orderbook may be empty)")

# Summary
print(f"\n{'='*100}")
print("SUMMARY")
print(f"{'='*100}")
print(f"Total trading days in data: {len(all_dates)}")
print(f"Days with poor orderbook (<50% both-side availability): {len(poor_orderbook_days)}")
print(f"\nThis diagnostic shows orderbook state throughout each day.")
print(f"If 60 days have very poor orderbook availability, that's the root cause.")
