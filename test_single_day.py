"""Test a single non-trading day for ADNOCGAS in isolation."""

from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
from src.mm_handler import create_mm_handler
import json
from datetime import datetime, date

# Load config
with open('configs/mm_config.json', 'r') as f:
    config = json.load(f)

# First missed day from the output
TARGET_DATE = date(2025, 4, 16)

print(f"Testing ADNOCGAS on {TARGET_DATE} (first non-trading day)")
print("=" * 80)

# Collect all ADNOCGAS data
all_data = []
for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=1000000, max_sheets=4):
    if 'ADNOCGAS' not in sheet_name:
        continue
    df = preprocess_chunk_df(chunk)
    all_data.append(df)
    break

if not all_data:
    print("ERROR: No ADNOCGAS data found!")
    exit(1)

import pandas as pd
full_df = pd.concat(all_data, ignore_index=True)

# Filter to target date only
target_df = full_df[full_df['timestamp'].dt.date == TARGET_DATE].copy()

print(f"\nData for {TARGET_DATE}:")
print(f"  Total rows: {len(target_df)}")
print(f"  First timestamp: {target_df['timestamp'].iloc[0] if len(target_df) > 0 else 'N/A'}")
print(f"  Last timestamp: {target_df['timestamp'].iloc[-1] if len(target_df) > 0 else 'N/A'}")
print(f"  Event types: {target_df['type'].value_counts().to_dict()}")

# Run backtest on this day only
strategy = MarketMakingStrategy(config)
orderbook = OrderBook()
security = 'ADNOCGAS'

state = {
    'rows': 0,
    'bid_count': 0,
    'ask_count': 0,
    'trade_count': 0,
    'position': 0,
    'last_date': None,
    'last_flatten_date': None,
    'closed_at_eod': False,
    'market_dates': set(),
    'trades': []
}

# Create handler
handler = create_mm_handler(config)

print(f"\nRunning backtest on {TARGET_DATE}...")
print("-" * 80)

# Process the day
state = handler(security, target_df, orderbook, state)

print("-" * 80)
print(f"\nResults for {TARGET_DATE}:")
print(f"  Rows processed: {state['rows']}")
print(f"  Bids: {state['bid_count']}, Asks: {state['ask_count']}, Trades: {state['trade_count']}")
print(f"  Strategy trades: {len(state['trades'])}")
print(f"  Final position: {state.get('position', 0)}")

if len(state['trades']) == 0:
    print(f"\n⚠️  NO TRADES on {TARGET_DATE}!")
    print("\nChecking orderbook state at key times...")
    
    # Sample a few timestamps to check orderbook
    sample_times = target_df['timestamp'].iloc[::len(target_df)//5].tolist()[:5]
    
    orderbook_test = OrderBook()
    cfg = config.get('ADNOCGAS', {})
    
    print(f"\nConfig: quote_size={cfg.get('quote_size')}, min_currency={cfg.get('min_local_currency_before_quote')}")
    
    for i, ts in enumerate(sample_times, 1):
        # Get data up to this timestamp
        subset = target_df[target_df['timestamp'] <= ts]
        
        # Apply updates
        orderbook_test = OrderBook()
        for _, row in subset.iterrows():
            orderbook_test.apply_update({
                'timestamp': row['timestamp'],
                'type': row['type'],
                'price': row['price'],
                'volume': row['volume']
            })
        
        best_bid = orderbook_test.get_best_bid()
        best_ask = orderbook_test.get_best_ask()
        
        print(f"\n  Sample {i} at {ts}:")
        print(f"    Best bid: {best_bid}")
        print(f"    Best ask: {best_ask}")
        
        if best_bid and best_ask:
            bid_price, bid_qty = best_bid
            ask_price, ask_qty = best_ask
            bid_liquidity = bid_price * bid_qty
            ask_liquidity = ask_price * ask_qty
            print(f"    Bid liquidity: {bid_liquidity:.2f} AED")
            print(f"    Ask liquidity: {ask_liquidity:.2f} AED")
            print(f"    Passes 13,000 threshold? Bid: {bid_liquidity >= 13000}, Ask: {ask_liquidity >= 13000}")
else:
    print(f"\n✓ {len(state['trades'])} trades executed on {TARGET_DATE}")
    print("\nFirst 5 trades:")
    for i, trade in enumerate(state['trades'][:5], 1):
        print(f"  {i}. {trade['side']:4s} {trade['quantity']:6.0f} @ ${trade['price']:6.3f}")

print("\n" + "=" * 80)
