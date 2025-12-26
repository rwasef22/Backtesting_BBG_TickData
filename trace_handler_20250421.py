"""
Trace handler execution for 2025-04-21 to find why no trades occur.
"""
from datetime import date, datetime
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

print(f"Tracing handler logic for {security} on {TARGET_DATE}")
print(f"Threshold: ${threshold:,} AED")
print("="*80)

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
        events.append({'timestamp': timestamp_val, 'type': event_type, 'price': price, 'quantity': quantity})

print(f"Total events: {len(events)}")

# Initialize strategy and orderbook
strategy = MarketMakingStrategy(config)
strategy.initialize_security(security)
orderbook = OrderBook()

quote_attempts = 0
successful_quotes = 0
trades_processed = 0
refill_checks = 0

print("\nFirst 20 quote attempts:")
print("-"*80)

for i, event in enumerate(events):
    timestamp = event['timestamp']
    event_type = event['type']
    price = event['price']
    quantity = event['quantity']
    
    # Check if in skip window
    is_opening = strategy.is_in_opening_auction(timestamp)
    is_closing = strategy.is_in_closing_auction(timestamp)
    is_silent = strategy.is_in_silent_period(timestamp)
    is_eod = strategy.is_eod_close_time(timestamp)
    
    in_skip = is_opening or is_closing or is_silent or is_eod
    
    # Apply update to orderbook (outside skip windows)
    if not in_skip or event_type == 'trade':
        orderbook.apply_update({'timestamp': timestamp, 'type': event_type, 'price': price, 'volume': quantity})
    
    # Get best bid/ask
    best_bid = orderbook.get_best_bid()
    best_ask = orderbook.get_best_ask()
    
    # Try to generate quotes
    quotes = strategy.generate_quotes(security, best_bid, best_ask)
    
    if quotes and not in_skip:
        # Check if should refill bid
        should_refill_bid = strategy.should_refill_side(security, timestamp, 'bid') if best_bid else False
        should_refill_ask = strategy.should_refill_side(security, timestamp, 'ask') if best_ask else False
        
        if should_refill_bid or should_refill_ask:
            refill_checks += 1
            
            if quote_attempts < 20:
                bid_price = quotes.get('bid_price')
                ask_price = quotes.get('ask_price')
                bid_size = quotes.get('bid_size')
                ask_size = quotes.get('ask_size')
                
                bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price else 0
                ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price else 0
                bid_liq = bid_price * bid_ahead if bid_price else 0
                ask_liq = ask_price * ask_ahead if ask_price else 0
                
                bid_ok = bid_liq >= threshold and bid_size > 0 if should_refill_bid else False
                ask_ok = ask_liq >= threshold and ask_size > 0 if should_refill_ask else False
                
                status = []
                if should_refill_bid:
                    status.append(f"Bid: {bid_price:.2f} liq=${bid_liq:,.0f} {'✓' if bid_ok else '✗'}")
                if should_refill_ask:
                    status.append(f"Ask: {ask_price:.2f} liq=${ask_liq:,.0f} {'✓' if ask_ok else '✗'}")
                
                print(f"{timestamp.time()} | Refill check #{refill_checks} | {' | '.join(status)}")
                
                if bid_ok or ask_ok:
                    successful_quotes += 1
            
            quote_attempts += 1
    
    # Check for trade fills
    if event_type == 'trade' and not is_opening:
        trades_processed += 1

print("\n" + "="*80)
print(f"SUMMARY:")
print(f"Total events: {len(events)}")
print(f"Refill checks: {refill_checks}")
print(f"Quote attempts: {quote_attempts}")
print(f"Successful quotes (passed liquidity): {successful_quotes}")
print(f"Trades processed: {trades_processed}")
print(f"Strategy trades recorded: {len(strategy.trades.get(security, []))}")
print("="*80)

if successful_quotes > 0 and len(strategy.trades.get(security, [])) == 0:
    print("\n*** BUG FOUND: Quotes pass liquidity but no fills recorded! ***")
    print("Issue is likely in:")
    print("  1. should_refill_side() returning False when it should return True")
    print("  2. process_trade() not matching our quotes")
    print("  3. Quote tracking in active_orders not being set properly")
