"""
Compare V2 and V2.1 internal state side-by-side to find the difference
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from orderbook import OrderBook
from data_loader import stream_sheets

# Load data
print("Loading data...")
sheet_name, df = next(stream_sheets('data/raw/TickData.xlsx', 
                                     sheet_names_filter=['EMAAR UH Equity'],
                                     chunk_size=100000))

df = df.rename(columns={'Dates': 'timestamp', 'Type': 'type', 'Price': 'price', 'Size': 'volume'})
df['type'] = df['type'].str.lower()
df = df[['timestamp', 'type', 'price', 'volume']].copy()

# Create handlers
v2_handler = create_v2_price_follow_qty_cooldown_handler()
v2_1_handler = create_v2_1_stop_loss_handler({'EMAAR': {'stop_loss_threshold_pct': 50.0}})

# Separate orderbooks
v2_ob = OrderBook()
v2_1_ob = OrderBook()

v2_state = {}
v2_1_state = {}

# Access the strategy objects
v2_strategy = None
v2_1_strategy = None

# Extract strategy from handler closure
import types
for item in v2_handler.__code__.co_consts:
    if isinstance(item, types.CodeType) and item.co_name == 'v2_handler':
        # Get the strategy from closure
        v2_strategy = v2_handler.__closure__[0].cell_contents
        break

for item in v2_1_handler.__code__.co_consts:
    if isinstance(item, types.CodeType) and item.co_name == 'v2_1_handler':
        v2_1_strategy = v2_1_handler.__closure__[0].cell_contents
        break

print("="*80)
print("PROCESSING EVENTS SIDE-BY-SIDE")
print("="*80)

trade_count = 0
for idx, row in df.iterrows():
    # Process both
    v2_state = v2_handler('EMAAR', pd.DataFrame([row]), v2_ob, v2_state)
    v2_1_state = v2_1_handler('EMAAR', pd.DataFrame([row]), v2_1_ob, v2_1_state)
    
    # Check for trades
    v2_trades = len(v2_state.get('trades', []))
    v2_1_trades = len(v2_1_state.get('trades', []))
    
    # Show state around trade #6 and #7
    if v2_trades >= 6 or v2_1_trades >= 6:
        if row['timestamp'] >= datetime(2025, 4, 14, 10, 17, 37) and row['timestamp'] <= datetime(2025, 4, 14, 10, 17, 38):
            if v2_trades != trade_count or v2_1_trades != trade_count:
                print(f"\n[{row['timestamp']}] {row['type'].upper()} @ {row['price']:.3f}")
                print(f"  V2   trades: {v2_trades}, pos: {v2_strategy.position['EMAAR']:6.0f}, entry: {v2_strategy.entry_price.get('EMAAR', 0):.3f}")
                print(f"  V2.1 trades: {v2_1_trades}, pos: {v2_1_strategy.position['EMAAR']:6.0f}, entry: {v2_1_strategy.entry_price.get('EMAAR', 0):.3f}")
                
                # Show quote prices
                v2_quotes = v2_strategy.quote_prices.get('EMAAR', {})
                v2_1_quotes = v2_1_strategy.quote_prices.get('EMAAR', {})
                print(f"  V2   quotes: BID={v2_quotes.get('bid')}, ASK={v2_quotes.get('ask')}")
                print(f"  V2.1 quotes: BID={v2_1_quotes.get('bid')}, ASK={v2_1_quotes.get('ask')}")
                
                # Show active orders
                v2_ao = v2_strategy.active_orders.get('EMAAR', {})
                v2_1_ao = v2_1_strategy.active_orders.get('EMAAR', {})
                print(f"  V2   active: BID rem={v2_ao.get('bid', {}).get('our_remaining', 0)}, ASK rem={v2_ao.get('ask', {}).get('our_remaining', 0)}")
                print(f"  V2.1 active: BID rem={v2_1_ao.get('bid', {}).get('our_remaining', 0)}, ASK rem={v2_1_ao.get('ask', {}).get('our_remaining', 0)}")
                
                trade_count = max(v2_trades, v2_1_trades)
    
    if v2_trades >= 8 and v2_1_trades >= 8:
        break

print("\n" + "="*80)
print("TRADES COMPARISON")
print("="*80)
print("\nV2 trades:")
for i, t in enumerate(v2_state.get('trades', [])[:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")

print("\nV2.1 trades:")
for i, t in enumerate(v2_1_state.get('trades', [])[:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")
