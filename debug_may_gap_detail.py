"""Debug why no trades during May 9 - July 18 gap when liquidity is fine"""
import openpyxl
from datetime import datetime
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
import json

# Load config
with open('configs/mm_config.json') as f:
    config = json.load(f)

# Check a specific date in the gap
target_date = datetime(2025, 5, 9).date()

print(f"Debugging {target_date} (date in the gap)...")
print(f"Config: {config.get('EMAAR', {})}")
print()

# Initialize
orderbook = OrderBook()
strategy = MarketMakingStrategy(config=config)
strategy.initialize_security('EMAAR')

# Load Excel
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

rows_for_date = 0
quote_checks = 0
quotes_none = 0
bid_size_zero = 0
ask_size_zero = 0
both_zero = 0
refill_blocked_bid = 0
refill_blocked_ask = 0
position_values = []

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
            
            # Track position
            position_values.append(strategy.position.get('EMAAR', 0))
            
            # Check every 100 rows
            if rows_for_date % 100 == 0:
                quote_checks += 1
                best_bid = orderbook.get_best_bid()
                best_ask = orderbook.get_best_ask()
                
                # Check refill conditions
                should_refill_bid = strategy.should_refill_side('EMAAR', timestamp, 'bid')
                should_refill_ask = strategy.should_refill_side('EMAAR', timestamp, 'ask')
                
                if not should_refill_bid:
                    refill_blocked_bid += 1
                if not should_refill_ask:
                    refill_blocked_ask += 1
                
                # Try to generate quotes
                quotes = strategy.generate_quotes('EMAAR', best_bid, best_ask)
                
                if quotes is None:
                    quotes_none += 1
                    if rows_for_date == 100:
                        print(f"Row {rows_for_date}: quotes=None")
                        print(f"  best_bid: {best_bid}, best_ask: {best_ask}")
                else:
                    bid_size = quotes['bid_size']
                    ask_size = quotes['ask_size']
                    
                    if bid_size == 0 and ask_size == 0:
                        both_zero += 1
                        if rows_for_date == 100:
                            print(f"Row {rows_for_date}: Both sizes zero")
                            print(f"  quotes: {quotes}")
                            print(f"  position: {strategy.position.get('EMAAR', 0)}")
                            print(f"  best_bid: {best_bid}, best_ask: {best_ask}")
                    elif bid_size == 0:
                        bid_size_zero += 1
                    elif ask_size == 0:
                        ask_size_zero += 1
                    
                    if rows_for_date == 100:
                        print(f"Row {rows_for_date}: bid_size={bid_size}, ask_size={ask_size}")
                        print(f"  position: {strategy.position.get('EMAAR', 0)}")
                        print(f"  should_refill_bid: {should_refill_bid}, should_refill_ask: {should_refill_ask}")
                        
        except Exception as e:
            if rows_for_date <= 10:
                print(f"Error at row {rows_for_date}: {e}")

print(f"\nResults for {target_date}:")
print(f"  Rows processed: {rows_for_date}")
print(f"  Quote checks: {quote_checks}")
print(f"  Quotes returned None: {quotes_none}")
print(f"  Bid size zero: {bid_size_zero}")
print(f"  Ask size zero: {ask_size_zero}")
print(f"  Both sizes zero: {both_zero}")
print(f"  Refill blocked bid: {refill_blocked_bid}")
print(f"  Refill blocked ask: {refill_blocked_ask}")
if position_values:
    print(f"  Position range: {min(position_values)} to {max(position_values)}")
