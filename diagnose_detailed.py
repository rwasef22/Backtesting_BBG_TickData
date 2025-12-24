import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
import pandas as pd

print("Detailed diagnostic: Checking why trades stop...")

mm_config = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=mm_config)

security = None
state = {}
ob = None
last_strategy_date = None
checked_dates = set()

for sheet_name, chunk in stream_sheets('data/raw/TickData.xlsx', header_row=3, chunk_size=100000, max_sheets=1, only_trades=False):
    sec = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
    if ob is None:
        ob = OrderBook()
        security = sec
    
    # Process chunk
    df = preprocess_chunk_df(chunk)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Call handler
    state = handler(sec, df, ob, state) or state
    
    # Check strategy dates after this chunk
    strategy_dates = state.get('strategy_dates', set())
    current_last_date = max(strategy_dates) if strategy_dates else None
    
    if current_last_date != last_strategy_date:
        print(f"Last strategy trade date moved from {last_strategy_date} to {current_last_date}")
        last_strategy_date = current_last_date
    
    # Check a specific date that should have trades but doesn't
    market_dates = state.get('market_dates', set())
    new_market_dates = market_dates - checked_dates
    
    for date in sorted(new_market_dates):
        if date not in strategy_dates and date not in checked_dates:
            # This is a market date with no strategy trades - investigate why
            date_str = str(date)
            if '2025-05-09' in date_str or '2025-05-20' in date_str:
                print(f"\n>>> Investigating {date}: Market traded but strategy didn't")
                print(f"    Orderbook bids: {len(ob.bids)} levels, asks: {len(ob.asks)} levels")
                if ob.bids:
                    print(f"    Best bid: {ob.get_best_bid()}")
                if ob.asks:
                    print(f"    Best ask: {ob.get_best_ask()}")
        checked_dates.add(date)
    
    # Stop after processing enough to see the pattern
    if len(checked_dates) > 50:
        break

print(f"\n=== SUMMARY ===")
print(f"Market dates checked: {len(checked_dates)}")
print(f"Strategy traded dates: {len(state.get('strategy_dates', set()))}")
print(f"Last orderbook state: {len(ob.bids)} bid levels, {len(ob.asks)} ask levels")
