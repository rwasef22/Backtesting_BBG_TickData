"""Debug why certain dates have no trades by checking liquidity threshold"""
import openpyxl
from datetime import datetime
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
import json

# Load config
with open('configs/mm_config.json') as f:
    config = json.load(f)

# Target date with no trades
target_date = datetime(2025, 5, 9).date()

print(f"Debugging {target_date}...")
print(f"Config: {config.get('EMAAR UH Equity', {})}")
print()

# Initialize
orderbook = OrderBook()
strategy = MarketMakingStrategy(config=config)
strategy.initialize_security('EMAAR UH Equity')

# Load Excel
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

rows_processed = 0
checks_performed = 0
bid_threshold_failures = 0
ask_threshold_failures = 0
both_threshold_failures = 0
quote_generation_failures = 0

for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            if timestamp.date() != target_date:
                continue
                
            rows_processed += 1
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
            
            # Try to generate quotes every 100 rows
            if rows_processed % 100 == 0:
                checks_performed += 1
                best_bid = orderbook.get_best_bid()
                best_ask = orderbook.get_best_ask()
                
                quotes = strategy.generate_quotes('EMAAR UH Equity', best_bid, best_ask)
                
                if quotes is None:
                    quote_generation_failures += 1
                    continue
                
                # Check liquidity threshold
                cfg = strategy.get_config('EMAAR UH Equity')
                threshold = cfg.get('min_local_currency_before_quote', 25000)
                
                bid_price = quotes['bid_price']
                ask_price = quotes['ask_price']
                
                bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                
                bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                
                bid_ok = bid_local >= threshold
                ask_ok = ask_local >= threshold
                
                if not bid_ok and not ask_ok:
                    both_threshold_failures += 1
                elif not bid_ok:
                    bid_threshold_failures += 1
                elif not ask_ok:
                    ask_threshold_failures += 1
                    
                if rows_processed == 100:
                    print(f"Sample at row 100:")
                    print(f"  best_bid: {best_bid}, best_ask: {best_ask}")
                    print(f"  bid_price: {bid_price}, ask_price: {ask_price}")
                    print(f"  bid_ahead: {bid_ahead}, ask_ahead: {ask_ahead}")
                    print(f"  bid_local: {bid_local:.0f}, ask_local: {ask_local:.0f}")
                    print(f"  threshold: {threshold}")
                    print(f"  bid_ok: {bid_ok}, ask_ok: {ask_ok}")
                    print()
        except Exception as e:
            print(f"Error: {e}")
            pass

print(f"Results for {target_date}:")
print(f"  Rows processed: {rows_processed}")
print(f"  Checks performed: {checks_performed}")
print(f"  Quote generation failures (None): {quote_generation_failures}")
print(f"  Bid threshold failures: {bid_threshold_failures}")
print(f"  Ask threshold failures: {ask_threshold_failures}")
print(f"  Both sides threshold failure: {both_threshold_failures}")
print(f"  Successful checks: {checks_performed - quote_generation_failures - bid_threshold_failures - ask_threshold_failures - both_threshold_failures}")
