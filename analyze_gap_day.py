"""Analyze why 2025-04-21 doesn't trade for ADNOCGAS."""
from datetime import date, datetime, time
import sys
sys.path.insert(0, 'c:/Ray/VS Code/tick-backtest-project')

from src.config_loader import load_strategy_config
from src.market_making_strategy import MarketMakingStrategy
from src.orderbook import OrderBook

TARGET_DATE = date(2025, 4, 21)

# Load config
config = load_strategy_config('configs/mm_config.json')
security = 'ADNOCGAS'
cfg = config[security]
threshold = cfg.get('min_local_currency_before_quote', 13000)

print(f"Analyzing {security} on {TARGET_DATE}")
print(f"Threshold: ${threshold:,} AED")
print("="*80)

# Load data
import openpyxl
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True, data_only=True)
sheet = wb['ADNOCGAS UH Equity']

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

print(f"Total events on {TARGET_DATE}: {len(events)}")

# Build orderbook and check liquidity
strategy = MarketMakingStrategy(config)
orderbook = OrderBook()

sample_count = 0
can_quote_count = 0
skip_count = 0

for event in events:
    timestamp = event['timestamp']
    event_type = event['type']
    price = event['price']
    quantity = event['quantity']
    
    # Update orderbook
    if event_type == 'bid':
        orderbook.set_bid(price, quantity)
    elif event_type == 'ask':
        orderbook.set_ask(price, quantity)
    elif event_type == 'trade':
        orderbook.last_trade = price
    
    # Sample every 100 events
    if sample_count % 100 == 0:
        best_bid = orderbook.get_best_bid()
        best_ask = orderbook.get_best_ask()
        
        # Check skip windows
        in_skip = (strategy.is_in_silent_period(timestamp) or 
                  strategy.is_in_closing_auction(timestamp) or
                  strategy.is_eod_close_time(timestamp))
        
        # Calculate liquidity
        bid_liq = (best_bid[0] * best_bid[1]) if best_bid else 0
        ask_liq = (best_ask[0] * best_ask[1]) if best_ask else 0
        
        bid_pass = bid_liq >= threshold
        ask_pass = ask_liq >= threshold
        can_quote = (bid_pass or ask_pass) and not in_skip
        
        if can_quote:
            can_quote_count += 1
        if in_skip:
            skip_count += 1
            
        # Print first few samples
        if sample_count < 1000:
            status = "SKIP" if in_skip else ("CAN QUOTE" if can_quote else "NO QUOTE")
            bid_str = f"{best_bid[0]:.2f}@{best_bid[1]:.0f}" if best_bid else "None"
            ask_str = f"{best_ask[0]:.2f}@{best_ask[1]:.0f}" if best_ask else "None"
            print(f"{timestamp.time()} | Bid: {bid_str:<15} (${bid_liq:,.0f}) | " 
                  f"Ask: {ask_str:<15} (${ask_liq:,.0f}) | {status}")
    
    sample_count += 1

print("\n" + "="*80)
print(f"SUMMARY:")
print(f"Total samples: {sample_count}")
print(f"Skip window samples: {skip_count}")
print(f"Can quote samples: {can_quote_count}")
print(f"Cannot quote samples: {sample_count - skip_count - can_quote_count}")
print("="*80)

if can_quote_count == 0:
    print("\n*** NO OPPORTUNITIES TO QUOTE during tradable windows ***")
    print("This day should NOT trade.")
else:
    print(f"\n*** {can_quote_count} OPPORTUNITIES TO QUOTE ***")
    print("This day SHOULD trade!")
