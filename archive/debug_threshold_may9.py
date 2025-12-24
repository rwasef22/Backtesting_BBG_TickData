"""Debug handler logic on May 9th to see where quotes are blocked"""
import openpyxl
from datetime import datetime
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
import json

# Load config
with open('configs/mm_config.json') as f:
    config = json.load(f)

target_date = datetime(2025, 5, 9).date()

print(f"Simulating handler logic for {target_date}...")
print()

# Initialize
orderbook = OrderBook()
strategy = MarketMakingStrategy(config=config)
strategy.initialize_security('EMAAR')

# Load Excel
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

cfg = strategy.get_config('EMAAR')
threshold = cfg.get('min_local_currency_before_quote', 25000)

rows_for_date = 0
times_bid_failed_threshold = 0
times_ask_failed_threshold = 0
times_both_failed = 0
times_both_passed = 0

for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            if timestamp.date() != target_date:
                continue
                
            rows_for_date += 1
            event_type = str(row[1]).lower() if row[1] else None
            price = float(row[2]) if row[2] is not None else None
            volume = float(row[3]) if row[3] is not None else None
            
            # Skip closing auction
            if strategy.is_in_closing_auction(timestamp):
                continue
            
            # Update orderbook
            orderbook.apply_update({
                'timestamp': timestamp,
                'type': event_type,
                'price': price,
                'volume': volume
            })
            
            # Simulate handler logic every 50 rows
            if rows_for_date % 50 == 0:
                best_bid = orderbook.get_best_bid()
                best_ask = orderbook.get_best_ask()
                
                should_refill_bid = strategy.should_refill_side('EMAAR', timestamp, 'bid')
                should_refill_ask = strategy.should_refill_side('EMAAR', timestamp, 'ask')
                
                quotes = strategy.generate_quotes('EMAAR', best_bid, best_ask)
                
                if quotes and (should_refill_bid or should_refill_ask):
                    bid_price = quotes['bid_price']
                    ask_price = quotes['ask_price']
                    
                    # Check threshold logic from handler
                    bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                    ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                    
                    bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                    ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                    
                    bid_ok = bid_local >= threshold
                    ask_ok = ask_local >= threshold
                    
                    if not bid_ok and not ask_ok:
                        times_both_failed += 1
                        if times_both_failed == 1:
                            print(f"First time both failed (row {rows_for_date}):")
                            print(f"  bid_price: {bid_price}, ask_price: {ask_price}")
                            print(f"  bid_ahead: {bid_ahead}, ask_ahead: {ask_ahead}")
                            print(f"  bid_local: {bid_local:.0f}, ask_local: {ask_local:.0f}")
                            print(f"  threshold: {threshold}")
                            print()
                    elif not bid_ok:
                        times_bid_failed_threshold += 1
                    elif not ask_ok:
                        times_ask_failed_threshold += 1
                    else:
                        times_both_passed += 1
                        if times_both_passed == 1:
                            print(f"First time both passed (row {rows_for_date}):")
                            print(f"  bid_price: {bid_price}, ask_price: {ask_price}")
                            print(f"  bid_ahead: {bid_ahead}, ask_ahead: {ask_ahead}")
                            print(f"  bid_local: {bid_local:.0f}, ask_local: {ask_local:.0f}")
                            print(f"  threshold: {threshold}")
                            print()
                        
        except Exception as e:
            pass

print(f"Results for {target_date} ({rows_for_date} rows):")
print(f"  Both sides failed threshold: {times_both_failed}")
print(f"  Only bid failed: {times_bid_failed_threshold}")
print(f"  Only ask failed: {times_ask_failed_threshold}")
print(f"  Both sides passed: {times_both_passed}")
print(f"\nConclusion: {'LIQUIDITY IS THE ISSUE' if times_both_failed > times_both_passed else 'SOMETHING ELSE IS THE ISSUE'}")
