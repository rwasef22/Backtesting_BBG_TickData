import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
from src.config_loader import load_strategy_config
import pandas as pd
from collections import defaultdict

print("Investigating why quotes aren't generated on missing days...")

mm_config = load_strategy_config('configs/mm_config.json')
strategy = MarketMakingStrategy(config=mm_config)
security = 'EMAAR'
strategy.initialize_security(security)

ob = OrderBook()
quote_attempts = defaultdict(int)
quote_successes = defaultdict(int)
no_best_bid_ask = defaultdict(int)
refill_failures = defaultdict(int)

chunk_num = 0
for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    chunk_num += 1
    if chunk_num > 3:  # Just check first 3 chunks
        break
    
    df = preprocess_chunk_df(chunk)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sample some rows from this chunk
    sample_indices = [0, len(df)//4, len(df)//2, 3*len(df)//4, len(df)-1]
    
    for idx in sample_indices:
        row = df.iloc[idx]
        timestamp = row['timestamp']
        date = timestamp.date()
        
        # Update orderbook with this row
        ob.apply_update({
            'timestamp': timestamp,
            'type': row['type'],
            'price': row['price'],
            'volume': row['volume']
        })
        
        # Try to generate quotes
        best_bid = ob.get_best_bid()
        best_ask = ob.get_best_ask()
        
        quote_attempts[date] += 1
        
        if best_bid is None or best_ask is None:
            no_best_bid_ask[date] += 1
            continue
        
        quotes = strategy.generate_quotes(security, best_bid, best_ask)
        if quotes:
            # Check refill
            should_refill_bid = strategy.should_refill_side(security, timestamp, 'bid')
            should_refill_ask = strategy.should_refill_side(security, timestamp, 'ask')
            
            if should_refill_bid or should_refill_ask:
                quote_successes[date] += 1
            else:
                refill_failures[date] += 1

print("\n=== ANALYSIS ===")
print(f"Dates with quote attempts: {len(quote_attempts)}")
print(f"\nDates with NO best bid/ask:")
for date in sorted(no_best_bid_ask.keys())[:10]:
    print(f"  {date}: {no_best_bid_ask[date]}/{quote_attempts[date]} samples had no best bid/ask")

print(f"\nDates with refill failures:")
for date in sorted(refill_failures.keys())[:10]:
    print(f"  {date}: {refill_failures[date]} samples failed refill check")

print(f"\nDates with successful quote generation:")
for date in sorted(quote_successes.keys())[:10]:
    print(f"  {date}: {quote_successes[date]} samples passed all checks")
