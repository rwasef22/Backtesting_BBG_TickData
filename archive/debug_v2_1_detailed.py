"""
Debug V2.1 with comprehensive logging to find where BUY 2691 comes from
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from strategies.v2_1_stop_loss.strategy import V21StopLossStrategy
from orderbook import OrderBook
from data_loader import stream_sheets

# Monkey-patch _record_fill to log all fills
original_record_fill = V21StopLossStrategy._record_fill

def logged_record_fill(self, security, side, price, qty, timestamp):
    if timestamp >= datetime(2025, 4, 14, 10, 17, 36) and timestamp <= datetime(2025, 4, 14, 10, 17, 38):
        print(f"\n>>> _record_fill called:")
        print(f"    Time: {timestamp}")
        print(f"    Side: {side}, Qty: {qty}, Price: {price}")
        print(f"    Position before: {self.position[security]}")
    
    original_record_fill(self, security, side, price, qty, timestamp)
    
    if timestamp >= datetime(2025, 4, 14, 10, 17, 36) and timestamp <= datetime(2025, 4, 14, 10, 17, 38):
        print(f"    Position after: {self.position[security]}")
        print(f"    Total trades: {len(self.trades[security])}")

V21StopLossStrategy._record_fill = logged_record_fill

# Monkey-patch generate_quotes to log quote generation
original_generate_quotes = V21StopLossStrategy.generate_quotes

def logged_generate_quotes(self, security, best_bid, best_ask, timestamp):
    result = original_generate_quotes(self, security, best_bid, best_ask, timestamp)
    
    if timestamp >= datetime(2025, 4, 14, 10, 17, 36) and timestamp <= datetime(2025, 4, 14, 10, 17, 38):
        if result:
            print(f"\n>>> Quotes generated at {timestamp}:")
            print(f"    Position: {self.position[security]}")
            print(f"    BID: {result.get('bid_price')} x {result.get('bid_size')}")
            print(f"    ASK: {result.get('ask_price')} x {result.get('ask_size')}")
    
    return result

V21StopLossStrategy.generate_quotes = logged_generate_quotes

# Load data
print("Loading data...")
sheet_name, df = next(stream_sheets('data/raw/TickData.xlsx', 
                                     sheet_names_filter=['EMAAR UH Equity'],
                                     chunk_size=100000))

df = df.rename(columns={'Dates': 'timestamp', 'Type': 'type', 'Price': 'price', 'Size': 'volume'})
df['type'] = df['type'].str.lower()
df = df[['timestamp', 'type', 'price', 'volume']].copy()

print(f"Loaded {len(df):,} rows\n")

# Run V2.1
handler = create_v2_1_stop_loss_handler({'EMAAR': {'stop_loss_threshold_pct': 50.0}})
orderbook = OrderBook()
state = {}

print("="*80)
print("PROCESSING EVENTS (10:17:36 - 10:17:38)")
print("="*80)

for idx, row in df.iterrows():
    if row['timestamp'] >= datetime(2025, 4, 14, 10, 17, 36) and row['timestamp'] <= datetime(2025, 4, 14, 10, 17, 38):
        print(f"\n[{row['timestamp']}] Market Event: {row['type'].upper():5s} @ {row['price']:.3f} vol={row['volume']}")
    
    state = handler('EMAAR', pd.DataFrame([row]), orderbook, state)
    
    if 'trades' in state and len(state['trades']) >= 8:
        print(f"\n{'='*80}")
        print(f"Stopping after {len(state['trades'])} trades")
        print(f"{'='*80}")
        break

print("\n" + "="*80)
print("TRADES RECORDED:")
print("="*80)
for i, t in enumerate(state.get('trades', [])[:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")
