import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
import pandas as pd

target_date = pd.Timestamp('2025-05-09').date()
print(f"Debugging why no trades on {target_date}...")

mm_config = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=mm_config)

security = 'EMAAR'
state = {}
ob = OrderBook()

found_date = False
rows_on_date = 0
trades_before = 0
trades_after = 0

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    sec = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
    if ob is None:
        ob = OrderBook()
    
    df = preprocess_chunk_df(chunk)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Check if target date is in this chunk
    dates_in_chunk = df['timestamp'].dt.date.unique()
    if target_date in dates_in_chunk:
        found_date = True
        rows_on_date = len(df[df['timestamp'].dt.date == target_date])
        trades_before = len(state.get('trades', []))
        print(f"\nFound {target_date} in chunk with {rows_on_date} rows")
        
        # Process chunk
        state = handler(sec, df, ob, state) or state
        
        trades_after = len(state.get('trades', []))
        new_trades = trades_after - trades_before
        
        print(f"Trades before chunk: {trades_before}")
        print(f"Trades after chunk: {trades_after}")
        print(f"New trades generated: {new_trades}")
        
        if new_trades == 0:
            print(f"\n>>> NO TRADES GENERATED ON {target_date}")
            print(f"Orderbook state: {len(ob.bids)} bid levels, {len(ob.asks)} ask levels")
            if ob.bids and ob.asks:
                print(f"Best bid: {ob.get_best_bid()}")
                print(f"Best ask: {ob.get_best_ask()}")
        
        break
    else:
        # Process chunk normally
        state = handler(sec, df, ob, state) or state

if not found_date:
    print(f"Date {target_date} not found in data")
