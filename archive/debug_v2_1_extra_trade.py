"""
Debug why V2.1 creates extra BUY 2691 trade at 10:17:37
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from orderbook import OrderBook

# Monkey-patch to trace _record_fill calls
original_record_fill = None

def traced_record_fill(self, security, side, price, qty, timestamp):
    if timestamp >= datetime(2025, 4, 14, 10, 17, 36) and timestamp <= datetime(2025, 4, 14, 10, 17, 38):
        print(f"  🔍 _record_fill called: {side.upper()} {qty:.0f} @ {price:.3f}")
        print(f"     Position before: {self.position[security]}")
    
    result = original_record_fill(self, security, side, price, qty, timestamp)
    
    if timestamp >= datetime(2025, 4, 14, 10, 17, 36) and timestamp <= datetime(2025, 4, 14, 10, 17, 38):
        print(f"     Position after: {self.position[security]}")
        print(f"     Total trades: {len(self.trades[security])}")
    
    return result

# Load data
df = pd.read_excel('data/raw/TickData.xlsx', sheet_name='EMAAR UH Equity', nrows=100000)
df['timestamp'] = pd.to_datetime(df['DATE'].astype(str) + ' ' + df['TIME'])
df = df.rename(columns={'TYPE': 'type', 'PRICE': 'price', 'VOLUME': 'volume'})
df['type'] = df['type'].str.lower()
df = df[['timestamp', 'type', 'price', 'volume']]

# Focus on the critical period
df_focus = df[(df['timestamp'] >= '2025-04-14 10:17:35') & (df['timestamp'] <= '2025-04-14 10:17:40')]

print("="*80)
print("DEBUGGING V2.1 EXTRA TRADE")
print("="*80)
print(f"\nMarket events at 10:17:36-10:17:38:")
print(df_focus[['timestamp', 'type', 'price', 'volume']])

# Run V2.1 with tracing
print("\n" + "="*80)
print("RUNNING V2.1 WITH _record_fill TRACING")
print("="*80)

config = {'EMAAR': {'stop_loss_threshold_pct': 50.0}}
v2_1_handler = create_v2_1_stop_loss_handler(config)

# Monkey-patch
from strategies.v2_1_stop_loss.strategy import V21StopLossStrategy
original_record_fill = V21StopLossStrategy._record_fill
V21StopLossStrategy._record_fill = traced_record_fill

# Run backtest
orderbook = OrderBook()
state = {}

print("\nProcessing events...")
for _, row in df.head(50000).iterrows():
    state = v2_1_handler('EMAAR', pd.DataFrame([row]), orderbook, state)
    
    # Stop after we see trade #8
    if 'trades' in state and len(state['trades']) >= 8:
        print(f"\nStopped after {len(state['trades'])} trades")
        break

# Show trades
print("\n" + "="*80)
print("V2.1 TRADES RECORDED:")
print("="*80)
for i, t in enumerate(state['trades'][:10]):
    print(f"{i+1}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:5.0f} @ {t['fill_price']:.3f} → pos={t['position']}")
