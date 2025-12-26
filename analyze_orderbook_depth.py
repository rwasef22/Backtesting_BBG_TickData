"""
Detailed analysis of 2025-04-16 orderbook state every minute to verify liquidity.
"""
from datetime import date, datetime, time
import sys
sys.path.insert(0, 'c:/Ray/VS Code/tick-backtest-project')

from src.config_loader import load_strategy_config
from src.market_making_strategy import MarketMakingStrategy
from src.orderbook import OrderBook
import openpyxl

TARGET_DATE = date(2025, 4, 21)

# Load config
config = load_strategy_config('configs/mm_config.json')
security = 'ADNOCGAS'
cfg = config[security]
threshold = cfg.get('min_local_currency_before_quote', 13000)

print(f"Detailed orderbook analysis for {security} on {TARGET_DATE}")
print("="*120)
print(f"Threshold: ${threshold:,} AED")
print("="*120)

# Load data
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

print(f"\nTotal events: {len(events)}")
print("="*120)

# Build orderbook and sample every minute
strategy = MarketMakingStrategy(config)
orderbook = OrderBook()

# Sample times (every hour + key times)
sample_times = [
    time(9, 30),
    time(10, 0),
    time(10, 30),
    time(11, 0),
    time(11, 30),
    time(12, 0),
    time(12, 30),
    time(13, 0),
    time(13, 30),
    time(14, 0),
    time(14, 30),
    time(14, 45),  # Closing auction starts
]

samples = []
last_sample_time = None

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
    
    # Check if we should sample at this time
    current_time = timestamp.time()
    for sample_time in sample_times:
        if current_time >= sample_time and (last_sample_time is None or sample_time > last_sample_time):
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            # Calculate liquidity AT the best prices
            bid_liq = 0
            ask_liq = 0
            bid_pass = False
            ask_pass = False
            
            if best_bid:
                bid_price, bid_qty = best_bid
                # Check qty at THIS price level
                qty_at_price = orderbook.bids.get(bid_price, 0)
                bid_liq = bid_price * qty_at_price
                bid_pass = bid_liq >= threshold
            
            if best_ask:
                ask_price, ask_qty = best_ask
                # Check qty at THIS price level
                qty_at_price = orderbook.asks.get(ask_price, 0)
                ask_liq = ask_price * qty_at_price
                ask_pass = ask_liq >= threshold
            
            # Check skip windows
            in_silent = strategy.is_in_silent_period(timestamp)
            in_closing = strategy.is_in_closing_auction(timestamp)
            is_eod = strategy.is_eod_close_time(timestamp)
            in_skip = in_silent or in_closing or is_eod
            
            samples.append({
                'time': sample_time,
                'timestamp': timestamp,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'bid_liq': bid_liq,
                'ask_liq': ask_liq,
                'bid_pass': bid_pass,
                'ask_pass': ask_pass,
                'can_quote': (bid_pass or ask_pass) and not in_skip,
                'in_skip': in_skip,
                'total_bid_levels': len(orderbook.bids),
                'total_ask_levels': len(orderbook.asks)
            })
            
            last_sample_time = sample_time
            break

print("\nORDERBOOK STATE THROUGHOUT THE DAY:")
print("-"*120)
print(f"{'Time':<8} {'BestBid':<18} {'BestAsk':<18} {'BidLiq':<13} {'AskLiq':<13} {'BidLvl':<8} {'AskLvl':<8} {'CanQuote':<10} {'Skip'}")
print("-"*120)

for s in samples:
    bid_str = f"{s['best_bid'][0]:.2f}@{s['best_bid'][1]:.0f}" if s['best_bid'] else "None"
    ask_str = f"{s['best_ask'][0]:.2f}@{s['best_ask'][1]:.0f}" if s['best_ask'] else "None"
    bid_status = "PASS" if s['bid_pass'] else "FAIL"
    ask_status = "PASS" if s['ask_pass'] else "FAIL"
    can_quote = "YES" if s['can_quote'] else "NO"
    skip_str = "SKIP" if s['in_skip'] else ""
    bid_lvl = s['total_bid_levels']
    ask_lvl = s['total_ask_levels']
    
    print(f"{str(s['time']):<8} {bid_str:<18} {ask_str:<18} ${s['bid_liq']:<12,.0f}{bid_status:<5} ${s['ask_liq']:<12,.0f}{ask_status:<5} {bid_lvl:<8} {ask_lvl:<8} {can_quote:<10} {skip_str}")

print("\n" + "="*120)
print("\nSUMMARY:")
tradable_samples = [s for s in samples if not s['in_skip']]
can_quote_samples = [s for s in tradable_samples if s['can_quote']]
print(f"Tradable time samples: {len(tradable_samples)}")
print(f"Can quote (at least one side passes): {len(can_quote_samples)}")
print(f"Cannot quote: {len(tradable_samples) - len(can_quote_samples)}")

if len(can_quote_samples) > 0:
    print(f"\n✓ There ARE {len(can_quote_samples)} times when liquidity is sufficient!")
else:
    print(f"\n✗ No times when liquidity is sufficient during tradable windows")

# Show total orderbook depth (all levels combined)
print("\n" + "="*120)
print("\nTOTAL ORDERBOOK DEPTH CHECK (all price levels combined):")
print("-"*120)

for s in samples[:6]:  # First 6 samples
    total_bid_value = sum(p * q for p, q in orderbook.bids.items()) if hasattr(orderbook, 'bids') else 0
    total_ask_value = sum(p * q for p, q in orderbook.asks.items()) if hasattr(orderbook, 'asks') else 0
    print(f"{str(s['time']):<8} Total bid depth: ${total_bid_value:,.0f} | Total ask depth: ${total_ask_value:,.0f}")

print("\n" + "="*120)
print("\nKEY INSIGHT:")
print("If liquidity at BEST BID/ASK price is low but total depth is high,")
print("the issue is that the strategy quotes AT the best price where liquidity is thin,")
print("rather than a few ticks away where there's more depth.")
