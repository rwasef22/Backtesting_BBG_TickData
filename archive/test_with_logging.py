"""Simple test with detailed logging to understand why no trades."""

import json
from src.mm_handler import create_mm_handler
from src.market_making_backtest import MarketMakingBacktest

# Load config
with open('configs/v1_baseline_config.json', 'r') as f:
    config = json.load(f)

# Create handler
handler = create_mm_handler(config=config)

# Add debug logging by wrapping the handle_row method
original_handle_row = handler.handle_row

quote_attempts = 0
quotes_placed = 0
liquidity_failures = 0

def debug_handle_row(row):
    global quote_attempts, quotes_placed, liquidity_failures
    
    result = original_handle_row(row)
    
    # Check if this was a quote attempt
    if row.get('Type') in ['ASK', 'BID']:
        quote_attempts += 1
        if quote_attempts <= 10:  # Log first 10 attempts
            print(f"Quote attempt {quote_attempts}: Type={row.get('Type')}, Price={row.get('Price')}, Size={row.get('Size')}")
    
    return result

handler.handle_row = debug_handle_row

# Run backtest on first security only
backtest = MarketMakingBacktest()
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=1,
    chunk_size=30000
)

print("\n" + "="*80)
print("RESULTS")
print("="*80)
print(f"Quote attempts: {quote_attempts}")
print(f"Quotes placed: {quotes_placed}")
print(f"Liquidity failures: {liquidity_failures}")

if results:
    for security, sec_result in results.items():
        if isinstance(sec_result, dict):
            trades_df = sec_result.get('trades', None)
            if trades_df is not None:
                print(f"\n{security}: {len(trades_df)} trades")
            else:
                print(f"\n{security}: No trades DataFrame")
        else:
            print(f"\n{security}: {type(sec_result)}")
