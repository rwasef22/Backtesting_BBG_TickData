"""
Debug v2 strategy to see why no trades are being generated.
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config_loader import load_strategy_config
from src.strategies.v2_price_follow_qty_cooldown import create_v2_price_follow_qty_cooldown_handler
from src.orderbook import OrderBook
from src.data_loader import stream_sheets

# Load config
config = load_strategy_config('configs/mm_config.json')
print(f"Loaded config for {len(config)} securities")

# Create handler
handler = create_v2_price_follow_qty_cooldown_handler(config)
print("Handler created")

# Get strategy reference
strategy = handler.__closure__[0].cell_contents
print(f"Strategy type: {type(strategy)}")

# Process first security with detailed logging
file_path = 'data/raw/TickData.xlsx'
security_name = None
orderbook = OrderBook()
state = {}

print("\n" + "="*80)
print("PROCESSING FIRST 1000 ROWS OF FIRST SECURITY")
print("="*80)

row_count = 0
quote_attempts = 0
liquidity_failures = 0

for sheet_name, chunk_df in stream_sheets(file_path, header_row=3, chunk_size=1000):
    if security_name is None:
        security_name = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
        print(f"\nSecurity: {security_name}")
        print(f"Config: {config.get(security_name, {})}")
        
        # Initialize strategy
        strategy.initialize_security(security_name)
        print(f"Initialized strategy for {security_name}")
        print(f"Position: {strategy.position.get(security_name, 0)}")
        print(f"Quote prices: {strategy.quote_prices.get(security_name, {})}")
        
    # Check columns
    print(f"\nColumns in dataframe: {chunk_df.columns.tolist()}")
    print(f"First few rows:\n{chunk_df.head()}")
    
    # Process rows with logging
    for row in chunk_df.itertuples(index=False):
        row_count += 1
        
        # Handle column names flexibly
        if hasattr(row, 'timestamp'):
            timestamp = row.timestamp
        elif hasattr(row, 'Timestamp'):
            timestamp = row.Timestamp
        elif hasattr(row, 'Date'):
            timestamp = pd.to_datetime(str(row.Date) + ' ' + str(row.Time))
        else:
            print(f"ERROR: Cannot find timestamp column. Row fields: {row._fields}")
            break
        
        event_type = row.Type.lower() if hasattr(row, 'Type') else row.type.lower()
        price = row.Price if hasattr(row, 'Price') else row.price
        volume = row.Volume if hasattr(row, 'Volume') else row.volume
        
        # Skip time windows
        if strategy.is_in_silent_period(timestamp):
            continue
        if strategy.is_in_opening_auction(timestamp):
            continue
        if strategy.is_in_closing_auction(timestamp):
            continue
        
        # Update orderbook
        if event_type == 'bid':
            orderbook.set_bid(price, volume)
        elif event_type == 'ask':
            orderbook.set_ask(price, volume)
        elif event_type == 'trade':
            orderbook.last_trade = {'price': price, 'quantity': volume, 'timestamp': timestamp}
            strategy.process_trade(security_name, timestamp, price, volume, orderbook)
        
        # Try to generate quotes
        best_bid = orderbook.get_best_bid()
        best_ask = orderbook.get_best_ask()
        
        if best_bid or best_ask:
            quotes = strategy.generate_quotes(security_name, best_bid, best_ask, timestamp)
            
            if quotes:
                quote_attempts += 1
                
                # Check liquidity
                cfg = config.get(security_name, {})
                threshold = cfg.get('min_local_currency_before_quote', 25000)
                
                bid_price = quotes['bid_price']
                bid_size = quotes['bid_size']
                bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price else 0
                bid_local = bid_price * bid_ahead if bid_price else 0
                bid_ok = bid_local >= threshold and bid_size > 0
                
                ask_price = quotes['ask_price']
                ask_size = quotes['ask_size']
                ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price else 0
                ask_local = ask_price * ask_ahead if ask_price else 0
                ask_ok = ask_local >= threshold and ask_size > 0
                
                if not bid_ok and not ask_ok:
                    liquidity_failures += 1
                    if liquidity_failures <= 5:
                        print(f"\n  Row {row_count}: Liquidity check failed")
                        print(f"    Timestamp: {timestamp}")
                        print(f"    Event: {event_type} @ {price}")
                        print(f"    Best bid: {best_bid}")
                        print(f"    Best ask: {best_ask}")
                        print(f"    Quotes: bid_price={bid_price}, bid_size={bid_size}")
                        print(f"    Quotes: ask_price={ask_price}, ask_size={ask_size}")
                        print(f"    Bid check: ahead={bid_ahead}, local={bid_local:.0f}, threshold={threshold}, ok={bid_ok}")
                        print(f"    Ask check: ahead={ask_ahead}, local={ask_local:.0f}, threshold={threshold}, ok={ask_ok}")
                else:
                    if quote_attempts <= 5:
                        print(f"\n  Row {row_count}: QUOTE PLACED!")
                        print(f"    Timestamp: {timestamp}")
                        print(f"    Bid: {bid_price} x {bid_size} (ok={bid_ok})")
                        print(f"    Ask: {ask_price} x {ask_size} (ok={ask_ok})")
        
        if row_count >= 1000:
            break
    
    break  # Only process first chunk

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Rows processed: {row_count}")
print(f"Quote attempts: {quote_attempts}")
print(f"Liquidity failures: {liquidity_failures}")
print(f"Trades: {len(strategy.trades.get(security_name, []))}")
print(f"Position: {strategy.position.get(security_name, 0)}")
print(f"P&L: {strategy.pnl.get(security_name, 0.0):.2f}")
