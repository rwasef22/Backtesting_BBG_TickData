"""
Trace the complete day for ADNOCGAS on 2025-04-16 showing:
- Orderbook state evolution
- When refill checks happen
- Liquidity calculations at each refill opportunity
- Why quotes are/aren't generated
"""
from datetime import date, datetime
import sys
sys.path.insert(0, 'c:/Ray/VS Code/tick-backtest-project')

from src.config_loader import load_strategy_config
from src.market_making_strategy import MarketMakingStrategy
from src.orderbook import OrderBook
import openpyxl

TARGET_DATE = date(2025, 4, 16)

# Load config
config = load_strategy_config('configs/mm_config.json')
strategy = MarketMakingStrategy(config)
orderbook = OrderBook()

# Load ADNOCGAS data
print(f"Loading ADNOCGAS data for {TARGET_DATE}...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

# Parse and filter to target date
events = []
for row in sheet.iter_rows(min_row=4, values_only=True):
    timestamp_val = row[0]
    if not isinstance(timestamp_val, datetime):
        continue
    
    if timestamp_val.date() != TARGET_DATE:
        continue
    
    event_type = str(row[1]).lower() if row[1] else None
    price = float(row[2]) if row[2] is not None else None
    quantity = float(row[3]) if row[3] is not None else None
    
    if event_type in ['bid', 'ask', 'trade'] and price and quantity:
        events.append({
            'timestamp': timestamp_val,
            'type': event_type,
            'price': price,
            'quantity': quantity
        })

print(f"Found {len(events)} events for {TARGET_DATE}")
print("="*100)

cfg = strategy.get_config('ADNOCGAS')
threshold = cfg.get('min_local_currency_before_quote', 13000)
refill_interval = cfg['refill_interval_sec']
quote_size = cfg['quote_size_bid']  # Use quote_size_bid

print(f"Config: quote_size={quote_size}, min_currency={threshold}, refill_interval={refill_interval}s")
print("="*100)

# Track refill opportunities
last_bid_refill = None
last_ask_refill = None
refill_checks = []

for i, event in enumerate(events):
    timestamp = event['timestamp']
    
    # Update orderbook
    if event['type'] == 'bid':
        orderbook.set_bid(event['price'], event['quantity'])
    elif event['type'] == 'ask':
        orderbook.set_ask(event['price'], event['quantity'])
    elif event['type'] == 'trade':
        orderbook.last_trade = event['price']
    
    # Check if we should refill bid
    should_refill_bid = False
    if last_bid_refill is None:
        should_refill_bid = True
    else:
        elapsed = (timestamp - last_bid_refill).total_seconds()
        if elapsed >= refill_interval:
            should_refill_bid = True
    
    # Check if we should refill ask
    should_refill_ask = False
    if last_ask_refill is None:
        should_refill_ask = True
    else:
        elapsed = (timestamp - last_ask_refill).total_seconds()
        if elapsed >= refill_interval:
            should_refill_ask = True
    
    # If either side needs refill, check liquidity
    if should_refill_bid or should_refill_ask:
        best_bid = orderbook.get_best_bid()
        best_ask = orderbook.get_best_ask()
        
        # Calculate liquidity
        bid_liq = 0
        ask_liq = 0
        bid_pass = False
        ask_pass = False
        
        if best_bid and should_refill_bid:
            bid_price, bid_qty = best_bid
            # Get quantity ahead at quote price (one tick inside best)
            quote_bid_price = bid_price  # Simplified: quote at best
            bid_ahead = orderbook.bids.get(quote_bid_price, 0)
            bid_liq = quote_bid_price * bid_ahead
            bid_pass = bid_liq >= threshold
            last_bid_refill = timestamp
        
        if best_ask and should_refill_ask:
            ask_price, ask_qty = best_ask
            # Get quantity ahead at quote price (one tick inside best)
            quote_ask_price = ask_price  # Simplified: quote at best
            ask_ahead = orderbook.asks.get(quote_ask_price, 0)
            ask_liq = quote_ask_price * ask_ahead
            ask_pass = ask_liq >= threshold
            last_ask_refill = timestamp
        
        refill_checks.append({
            'timestamp': timestamp,
            'time': timestamp.time(),
            'event_num': i,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'bid_liq': bid_liq,
            'ask_liq': ask_liq,
            'bid_pass': bid_pass,
            'ask_pass': ask_pass,
            'can_quote': bid_pass and ask_pass and best_bid and best_ask
        })

print(f"\nTotal refill checks throughout the day: {len(refill_checks)}")
print("="*100)

# Show periods when both sides pass liquidity check
print("\nTIMES WHEN BOTH BID AND ASK LIQUIDITY PASS THRESHOLD:")
print("-"*100)
passing_periods = [r for r in refill_checks if r['can_quote']]
if passing_periods:
    for r in passing_periods:
        print(f"{r['time']} | Event #{r['event_num']:>5} | Bid: ${r['bid_liq']:>10,.0f} ✓ | Ask: ${r['ask_liq']:>10,.0f} ✓ | CAN QUOTE")
else:
    print("NO PERIODS where both bid AND ask liquidity pass threshold!")

print("\n" + "="*100)
print("\nTIMES WHEN AT LEAST ONE SIDE FAILS:")
print("-"*100)
failing_periods = [r for r in refill_checks if not r['can_quote']]
print(f"Total failing periods: {len(failing_periods)}")

# Show first 20 failing periods
for r in failing_periods[:20]:
    bid_status = "✓ PASS" if r['bid_pass'] else "✗ FAIL"
    ask_status = "✓ PASS" if r['ask_pass'] else "✗ FAIL"
    print(f"{r['time']} | Event #{r['event_num']:>5} | Bid: ${r['bid_liq']:>10,.0f} {bid_status} | Ask: ${r['ask_liq']:>10,.0f} {ask_status}")

if len(failing_periods) > 20:
    print(f"... and {len(failing_periods) - 20} more failing periods")

print("\n" + "="*100)
print("\nSUMMARY:")
print(f"Total refill opportunities: {len(refill_checks)}")
print(f"Opportunities where CAN quote (both sides pass): {len(passing_periods)}")
print(f"Opportunities where CANNOT quote (one or both fail): {len(failing_periods)}")
print(f"Percentage of time can quote: {100*len(passing_periods)/len(refill_checks):.1f}%")
print("="*100)

# Show orderbook stats
print("\nORDERBOOK STATISTICS:")
bid_sizes = []
ask_sizes = []
for r in refill_checks:
    if r['best_bid']:
        bid_sizes.append(r['bid_liq'])
    if r['best_ask']:
        ask_sizes.append(r['ask_liq'])

if bid_sizes:
    print(f"Bid liquidity: Min=${min(bid_sizes):,.0f}, Max=${max(bid_sizes):,.0f}, Avg=${sum(bid_sizes)/len(bid_sizes):,.0f}")
if ask_sizes:
    print(f"Ask liquidity: Min=${min(ask_sizes):,.0f}, Max=${max(ask_sizes):,.0f}, Avg=${sum(ask_sizes)/len(ask_sizes):,.0f}")
print(f"Threshold required: ${threshold:,}")
