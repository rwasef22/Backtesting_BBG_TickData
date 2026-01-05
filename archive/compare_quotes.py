"""
Compare V2 and V2.1 - log when they generate different quotes
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from strategies.v2_price_follow_qty_cooldown.strategy import V2PriceFollowQtyCooldownStrategy
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from strategies.v2_1_stop_loss.strategy import V21StopLossStrategy
from orderbook import OrderBook
from data_loader import stream_sheets

# Store quotes for comparison
v2_last_quotes = {}
v2_1_last_quotes = {}

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

v2_ob = OrderBook()
v2_1_ob = OrderBook()

v2_state = {}
v2_1_state = {}

print("Running backtests...")

for idx, row in df.iterrows():
    v2_state = v2_handler('EMAAR', pd.DataFrame([row]), v2_ob, v2_state)
    v2_1_state = v2_1_handler('EMAAR', pd.DataFrame([row]), v2_1_ob, v2_1_state)
    
    v2_trades = len(v2_state.get('trades', []))
    v2_1_trades = len(v2_1_state.get('trades', []))
    
    if v2_trades >= 8 and v2_1_trades >= 8:
        break

# Compare quotes around the divergence
print("\n" + "="*80)
print("QUOTE GENERATION COMPARISON (10:17:37 area)")
print("="*80)

all_times = sorted(set(list(v2_last_quotes.keys()) + list(v2_1_last_quotes.keys())))

for ts in all_times:
    v2_data = v2_last_quotes.get(ts, {})
    v2_1_data = v2_1_last_quotes.get(ts, {})
    
    v2_q = v2_data.get('result')
    v2_1_q = v2_1_data.get('result')
    
    # Check if quotes differ
    quotes_differ = False
    if v2_q != v2_1_q:
        if v2_q and v2_1_q:
            if (v2_q.get('bid_price') != v2_1_q.get('bid_price') or
                v2_q.get('ask_price') != v2_1_q.get('ask_price') or
                v2_q.get('bid_size') != v2_1_q.get('bid_size') or
                v2_q.get('ask_size') != v2_1_q.get('ask_size')):
                quotes_differ = True
        else:
            quotes_differ = True
    
    if quotes_differ or v2_data.get('position') != v2_1_data.get('position'):
        print(f"\n[{ts}]")
        print(f"  V2   pos={v2_data.get('position', 'N/A'):6}, entry={v2_data.get('entry_price', 0):.3f}")
        if v2_q:
            print(f"       BID: {v2_q.get('bid_price')} x {v2_q.get('bid_size')}, ASK: {v2_q.get('ask_price')} x {v2_q.get('ask_size')}")
        else:
            print(f"       No quotes")
        
        print(f"  V2.1 pos={v2_1_data.get('position', 'N/A'):6}, entry={v2_1_data.get('entry_price', 0):.3f}")
        if v2_1_q:
            print(f"       BID: {v2_1_q.get('bid_price')} x {v2_1_q.get('bid_size')}, ASK: {v2_1_q.get('ask_price')} x {v2_1_q.get('ask_size')}")
        else:
            print(f"       No quotes")

print("\n" + "="*80)
print("FINAL TRADES")
print("="*80)
print(f"\nV2: {len(v2_state.get('trades', []))} trades")
for i, t in enumerate(v2_state.get('trades', [])[:8]):
    print(f"{i+1}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")

print(f"\nV2.1: {len(v2_1_state.get('trades', []))} trades")
for i, t in enumerate(v2_1_state.get('trades', [])[:8]):
    print(f"{i+1}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")
