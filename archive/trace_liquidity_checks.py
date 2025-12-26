"""
Detailed trace showing EVERY liquidity check throughout 2025-04-16,
not just at refill intervals. This will show what the handler actually sees.
"""
from datetime import date, datetime
import sys
sys.path.insert(0, 'c:/Ray/VS Code/tick-backtest-project')

from src.config_loader import load_strategy_config
from src.market_making_strategy import MarketMakingStrategy
from src.orderbook import OrderBook
import openpyxl

TARGET_DATE = date(2025, 4, 21)  # A TRADING day

# Load config
config = load_strategy_config('configs/mm_config.json')
security = 'ADNOCGAS'
cfg = config[security]

print(f"Tracing liquidity checks for {security} on {TARGET_DATE}")
print("="*120)
print(f"Config: quote_size={cfg['quote_size']}, threshold={cfg.get('min_local_currency_before_quote', 13000)}, refill={cfg['refill_interval_sec']}s")
print("="*120)

# Load data for target date
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

# Run the actual handler and capture liquidity checks
strategy = MarketMakingStrategy(config)
strategy.position[security] = 0  # Initialize position
orderbook = OrderBook()

# Track when liquidity checks happen
liquidity_checks = []
refill_attempts = []

# Process events one by one
for i, event in enumerate(events):
    timestamp = event['timestamp']
    event_type = event['type']
    price = event['price']
    quantity = event['quantity']
    
    # Check skip windows
    in_silent = strategy.is_in_silent_period(timestamp)
    in_closing = strategy.is_in_closing_auction(timestamp)
    is_eod = strategy.is_eod_close_time(timestamp)
    in_skip = in_silent or in_closing or is_eod
    
    if in_skip:
        continue
    
    # Update orderbook
    if event_type == 'bid':
        orderbook.set_bid(price, quantity)
    elif event_type == 'ask':
        orderbook.set_ask(price, quantity)
    elif event_type == 'trade':
        orderbook.last_trade = price
    
    # Check if we would try to refill
    should_refill_bid = strategy.should_refill_side(security, timestamp, 'bid')
    should_refill_ask = strategy.should_refill_side(security, timestamp, 'ask')
    
    if should_refill_bid or should_refill_ask:
        best_bid = orderbook.get_best_bid()
        best_ask = orderbook.get_best_ask()
        
        quotes = strategy.generate_quotes(security, best_bid, best_ask)
        
        if quotes:
            threshold = cfg.get('min_local_currency_before_quote', 13000)
            
            # BID SIDE
            if best_bid and should_refill_bid:
                bid_price = quotes['bid_price']
                bid_size = quotes['bid_size']
                bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price else 0
                bid_local = (bid_price * bid_ahead) if bid_price else 0
                bid_pass = bid_local >= threshold and bid_size > 0
                
                refill_attempts.append({
                    'timestamp': timestamp,
                    'side': 'bid',
                    'best': best_bid,
                    'quote_price': bid_price,
                    'quote_size': bid_size,
                    'qty_ahead': bid_ahead,
                    'liquidity': bid_local,
                    'threshold': threshold,
                    'passes': bid_pass
                })
                
                strategy.set_refill_time(security, 'bid', timestamp)
            
            # ASK SIDE
            if best_ask and should_refill_ask:
                ask_price = quotes['ask_price']
                ask_size = quotes['ask_size']
                ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price else 0
                ask_local = (ask_price * ask_ahead) if ask_price else 0
                ask_pass = ask_local >= threshold and ask_size > 0
                
                refill_attempts.append({
                    'timestamp': timestamp,
                    'side': 'ask',
                    'best': best_ask,
                    'quote_price': ask_price,
                    'quote_size': ask_size,
                    'qty_ahead': ask_ahead,
                    'liquidity': ask_local,
                    'threshold': threshold,
                    'passes': ask_pass
                })
                
                strategy.set_refill_time(security, 'ask', timestamp)

print(f"\nTotal refill attempts: {len(refill_attempts)}")
print("="*120)

# Show sample of refill attempts
print("\nFIRST 20 REFILL ATTEMPTS:")
print("-"*120)
print(f"{'Time':<12} {'Side':<4} {'Best':<15} {'QuotePrice':<10} {'QtyAhead':<10} {'Liquidity':<12} {'Threshold':<10} {'Pass'}")
print("-"*120)

for r in refill_attempts[:20]:
    best_str = f"{r['best'][0]:.2f}@{r['best'][1]:.0f}"
    status = "✓" if r['passes'] else "✗"
    print(f"{str(r['timestamp'].time()):<12} {r['side']:<4} {best_str:<15} {r['quote_price']:<10.2f} {r['qty_ahead']:<10.0f} ${r['liquidity']:<11,.0f} ${r['threshold']:<9,} {status}")

print("\n" + "="*120)
print("\nKEY INSIGHT:")
passing = [r for r in refill_attempts if r['passes']]
print(f"Refill attempts that PASS liquidity check: {len(passing)}/{len(refill_attempts)}")
print(f"Refill attempts that FAIL: {len(refill_attempts) - len(passing)}/{len(refill_attempts)}")

# Show why they're failing
bid_attempts = [r for r in refill_attempts if r['side'] == 'bid']
ask_attempts = [r for r in refill_attempts if r['side'] == 'ask']
print(f"\nBid refill attempts: {len(bid_attempts)}, passing: {len([r for r in bid_attempts if r['passes']])}")
print(f"Ask refill attempts: {len(ask_attempts)}, passing: {len([r for r in ask_attempts if r['passes']])}")

# Show zero qty_ahead cases
zero_ahead = [r for r in refill_attempts if r['qty_ahead'] == 0]
print(f"\nCases where qty_ahead = 0: {len(zero_ahead)}/{len(refill_attempts)}")
if zero_ahead:
    print("\nSample cases with ZERO qty_ahead:")
    for r in zero_ahead[:5]:
        print(f"  {r['timestamp'].time()} {r['side']}: best={r['best']}, quote_price={r['quote_price']:.2f}, qty_ahead=0")
