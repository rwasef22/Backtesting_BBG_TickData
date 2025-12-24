import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
import pandas as pd

print("Diagnostic: Streaming EMAAR data with handler...")

mm_config = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=mm_config)

total_rows = 0
chunk_count = 0
security = None
state = {}
ob = None

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    chunk_count += 1
    rows_in_chunk = len(chunk)
    total_rows += rows_in_chunk
    
    sec = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
    if ob is None:
        ob = OrderBook()
        security = sec
    
    # Process chunk
    df = preprocess_chunk_df(chunk)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    first_ts = df['timestamp'].iloc[0]
    last_ts = df['timestamp'].iloc[-1]
    
    print(f"Chunk {chunk_count}: {rows_in_chunk:,} rows | {first_ts} to {last_ts}")
    
    # Call handler
    state = handler(sec, df, ob, state) or state
    
    num_trades = len(state.get('trades', []))
    market_dates = len(state.get('market_dates', set()))
    strategy_dates = len(state.get('strategy_dates', set()))
    print(f"  After chunk: {num_trades} trades, {market_dates} market days, {strategy_dates} strategy days")

print(f"\n=== FINAL SUMMARY ===")
print(f"Total chunks: {chunk_count}")
print(f"Total rows: {total_rows:,}")
print(f"Total trades: {len(state.get('trades', []))}")
print(f"Market trading days: {len(state.get('market_dates', set()))}")
print(f"Strategy traded days: {len(state.get('strategy_dates', set()))}")

# Check last trade date
if state.get('trades'):
    last_trade = state['trades'][-1]
    print(f"Last trade timestamp: {last_trade.get('timestamp')}")
