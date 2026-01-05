"""
Check if stop-loss is being triggered in V2.1 with detailed logging
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from strategies.v2_1_stop_loss.strategy import V21StopLossStrategy
from orderbook import OrderBook
from data_loader import stream_sheets

# Monkey-patch should_trigger_stop_loss to log checks
original_should_trigger = V21StopLossStrategy.should_trigger_stop_loss

def logged_should_trigger(self, security, current_price):
    result = original_should_trigger(self, security, current_price)
    
    if result or self.position[security] != 0:
        pnl_pct = self.get_unrealized_pnl_pct(security, current_price)
        cfg = self.get_config(security)
        threshold = cfg.get('stop_loss_threshold_pct', 2.0)
        
        print(f"Stop-loss check: pos={self.position[security]:6.0f}, pnl%={pnl_pct:+.2f}%, threshold={threshold:.0f}%, trigger={result}")
    
    return result

V21StopLossStrategy.should_trigger_stop_loss = logged_should_trigger

# Monkey-patch trigger_stop_loss to log when called
original_trigger = V21StopLossStrategy.trigger_stop_loss

def logged_trigger(self, security, timestamp):
    print(f"\n!!! STOP-LOSS TRIGGERED at {timestamp} !!!")
    print(f"    Position: {self.position[security]}")
    print(f"    Pending before: {self.stop_loss_pending[security]}")
    result = original_trigger(self, security, timestamp)
    print(f"    Pending after: {self.stop_loss_pending[security]}")
    return result

V21StopLossStrategy.trigger_stop_loss = logged_trigger

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
print("RUNNING V2.1 WITH STOP-LOSS LOGGING")
print("="*80)

for idx, row in df.iterrows():
    state = handler('EMAAR', pd.DataFrame([row]), orderbook, state)
    
    if 'trades' in state and len(state['trades']) >= 10:
        print(f"\nStopping after {len(state['trades'])} trades")
        break

print("\n" + "="*80)
print("FIRST 10 TRADES:")
print("="*80)
for i, t in enumerate(state.get('trades', [])[:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")
