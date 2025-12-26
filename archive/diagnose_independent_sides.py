"""
Check when AT LEAST ONE SIDE has sufficient liquidity (not requiring both).
This matches the actual handler logic which checks bid/ask independently.
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

# Track refill opportunities
last_bid_refill = None
last_ask_refill = None
refill_checks_tradable = []
refill_checks_skip = []

for i, event in enumerate(events):
    timestamp = event['timestamp']
    
    # Check if in skip window
    in_opening_auction = strategy.is_in_opening_auction(timestamp)
    in_silent_period = strategy.is_in_silent_period(timestamp)
    in_closing_auction = strategy.is_in_closing_auction(timestamp)
    is_eod_close = strategy.is_eod_close_time(timestamp)
    in_skip_window = in_opening_auction or in_silent_period or in_closing_auction or is_eod_close
    
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
        
        # Calculate liquidity per side
        bid_liq = 0
        ask_liq = 0
        bid_pass = False
        ask_pass = False
        
        if best_bid and should_refill_bid:
            bid_price, bid_qty = best_bid
            quote_bid_price = bid_price
            bid_ahead = orderbook.bids.get(quote_bid_price, 0)
            bid_liq = quote_bid_price * bid_ahead
            bid_pass = bid_liq >= threshold
            last_bid_refill = timestamp
        
        if best_ask and should_refill_ask:
            ask_price, ask_qty = best_ask
            quote_ask_price = ask_price
            ask_ahead = orderbook.asks.get(quote_ask_price, 0)
            ask_liq = quote_ask_price * ask_ahead
            ask_pass = ask_liq >= threshold
            last_ask_refill = timestamp
        
        # CAN QUOTE if AT LEAST ONE SIDE passes (not both required)
        can_quote_bid = bid_pass and best_bid is not None
        can_quote_ask = ask_pass and best_ask is not None
        can_quote_either = can_quote_bid or can_quote_ask
        
        record = {
            'timestamp': timestamp,
            'time': timestamp.time(),
            'event_num': i,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'bid_liq': bid_liq,
            'ask_liq': ask_liq,
            'bid_pass': bid_pass,
            'ask_pass': ask_pass,
            'can_quote_bid': can_quote_bid,
            'can_quote_ask': can_quote_ask,
            'can_quote_either': can_quote_either,
            'in_skip_window': in_skip_window,
            'window_type': 'opening' if in_opening_auction else ('silent' if in_silent_period else ('closing' if in_closing_auction else ('eod' if is_eod_close else 'none')))
        }
        
        if in_skip_window:
            refill_checks_skip.append(record)
        else:
            refill_checks_tradable.append(record)

print(f"Total refill checks: {len(refill_checks_tradable) + len(refill_checks_skip)}")
print(f"  During TRADABLE windows: {len(refill_checks_tradable)}")
print(f"  During SKIP windows: {len(refill_checks_skip)}")
print("="*100)

# Show periods when AT LEAST ONE side passes (independent checking)
print("\n✓ TIMES WHEN CAN QUOTE (AT LEAST ONE SIDE, OUTSIDE SKIP WINDOWS):")
print("-"*100)
passing_tradable = [r for r in refill_checks_tradable if r['can_quote_either']]
if passing_tradable:
    print(f"Found {len(passing_tradable)} tradable opportunities:")
    for r in passing_tradable:
        bid_status = "BID ✓" if r['can_quote_bid'] else "bid ✗"
        ask_status = "ASK ✓" if r['can_quote_ask'] else "ask ✗"
        print(f"{r['time']} | Event #{r['event_num']:>5} | {bid_status} (${r['bid_liq']:>10,.0f}) | {ask_status} (${r['ask_liq']:>10,.0f})")
else:
    print("❌ NO TRADABLE OPPORTUNITIES - Neither side ever passes threshold outside skip windows!")

print("\n" + "="*100)
print("\n✓ TIMES WHEN CAN QUOTE (AT LEAST ONE SIDE, BUT IN SKIP WINDOWS):")
print("-"*100)
passing_skip = [r for r in refill_checks_skip if r['can_quote_either']]
if passing_skip:
    print(f"Found {len(passing_skip)} opportunities BLOCKED by skip windows:")
    for r in passing_skip:
        bid_status = "BID ✓" if r['can_quote_bid'] else "bid ✗"
        ask_status = "ASK ✓" if r['can_quote_ask'] else "ask ✗"
        print(f"{r['time']} | Event #{r['event_num']:>5} | {bid_status} (${r['bid_liq']:>10,.0f}) | {ask_status} (${r['ask_liq']:>10,.0f}) | Window: {r['window_type']}")
else:
    print("None")

print("\n" + "="*100)
print("\nSUMMARY (INDEPENDENT SIDE CHECKING):")
print(f"Tradable refill checks: {len(refill_checks_tradable)}")
print(f"  Can quote at least one side: {len(passing_tradable)}")
print(f"  Cannot quote either side: {len(refill_checks_tradable) - len(passing_tradable)}")
print(f"\nSkip window refill checks: {len(refill_checks_skip)}")
print(f"  Can quote at least one side (but blocked): {len(passing_skip)}")
print(f"  Cannot quote either side: {len(refill_checks_skip) - len(passing_skip)}")
print("="*100)

if len(passing_tradable) == 0 and len(passing_skip) > 0:
    print("\n⚠️  DIAGNOSIS: Liquidity only passes threshold during SKIP WINDOWS!")
    print(f"   On {TARGET_DATE}, ADNOCGAS only has sufficient liquidity during skip windows")
    print("   which are excluded from trading by the strategy configuration.")
elif len(passing_tradable) == 0 and len(passing_skip) == 0:
    print("\n⚠️  DIAGNOSIS: Liquidity NEVER passes threshold throughout the day!")
    print(f"   The 13,000 AED threshold is too high for this day's orderbook depth on BOTH sides.")
elif len(passing_tradable) > 0:
    print(f"\n✓ GOOD: Found {len(passing_tradable)} opportunities to quote during tradable windows")
    print("   Strategy SHOULD be able to trade on this day with independent side checking.")
