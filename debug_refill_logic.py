"""Debug refill timing logic across chunks"""
import openpyxl
from datetime import datetime
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
import json

# Load config
with open('configs/mm_config.json') as f:
    config = json.load(f)

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
chunk_boundaries = [0, 100000, 200000, 300000, 400000]
current_chunk = 0
refill_checks = []

for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                
            rows_processed += 1
            
            # Check for chunk boundary
            if current_chunk < len(chunk_boundaries) - 1 and rows_processed >= chunk_boundaries[current_chunk + 1]:
                current_chunk += 1
                print(f"\n=== Crossed into chunk {current_chunk} at row {rows_processed} ===")
                print(f"  Timestamp: {timestamp}")
                print(f"  Last refill bid: {strategy.last_refill_time.get('EMAAR UH Equity', {}).get('bid')}")
                print(f"  Last refill ask: {strategy.last_refill_time.get('EMAAR UH Equity', {}).get('ask')}")
                print(f"  Current position: {strategy.position.get('EMAAR UH Equity', 0)}")
                
                # Check if refill would be triggered
                should_refill_bid = strategy.should_refill_side('EMAAR UH Equity', timestamp, 'bid')
                should_refill_ask = strategy.should_refill_side('EMAAR UH Equity', timestamp, 'ask')
                print(f"  Should refill bid: {should_refill_bid}")
                print(f"  Should refill ask: {should_refill_ask}")
            
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
            
            # Simulate some refills
            if rows_processed in [1000, 50000, 100001, 150000, 200001, 250000, 300001]:
                best_bid = orderbook.get_best_bid()
                best_ask = orderbook.get_best_ask()
                
                should_refill_bid = strategy.should_refill_side('EMAAR UH Equity', timestamp, 'bid')
                should_refill_ask = strategy.should_refill_side('EMAAR UH Equity', timestamp, 'ask')
                
                print(f"\nRow {rows_processed} at {timestamp}:")
                print(f"  Should refill bid: {should_refill_bid}, ask: {should_refill_ask}")
                print(f"  Last refill bid: {strategy.last_refill_time.get('EMAAR UH Equity', {}).get('bid')}")
                print(f"  Last refill ask: {strategy.last_refill_time.get('EMAAR UH Equity', {}).get('ask')}")
                
                # Simulate setting refill time
                if should_refill_bid:
                    strategy.set_refill_time('EMAAR UH Equity', 'bid', timestamp)
                    print(f"  -> Set bid refill time to {timestamp}")
                if should_refill_ask:
                    strategy.set_refill_time('EMAAR UH Equity', 'ask', timestamp)
                    print(f"  -> Set ask refill time to {timestamp}")
                    
            if rows_processed >= 350000:
                break
                
        except Exception as e:
            pass

print(f"\n\nTotal rows processed: {rows_processed}")
