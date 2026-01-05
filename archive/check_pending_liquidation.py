"""
Check if stop-loss ever gets PENDING (not just triggered)
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from strategies.v2_1_stop_loss.strategy import V21StopLossStrategy
from orderbook import OrderBook
from data_loader import stream_sheets
from config_loader import load_strategy_config

# Patch should_trigger_stop_loss to log
original_should_trigger = V21StopLossStrategy.should_trigger_stop_loss

def logged_should_trigger(self, security, mid_price):
    result = original_should_trigger(self, security, mid_price)
    if result:
        print(f"[TRIGGER] {security} pos={self.position[security]} triggered stop-loss!")
    return result

V21StopLossStrategy.should_trigger_stop_loss = logged_should_trigger

# Patch trigger_stop_loss to log
original_trigger = V21StopLossStrategy.trigger_stop_loss

def logged_trigger(self, security, timestamp):
    pos = self.position[security]
    print(f"[PENDING] {timestamp} - Setting pending liquidation for {security}, pos={pos}, qty={abs(pos)}")
    return original_trigger(self, security, timestamp)

V21StopLossStrategy.trigger_stop_loss = logged_trigger

# Load config
config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')

# Load data
print("Loading EMAAR data...")
sheet_name, df = next(stream_sheets('data/raw/TickData.xlsx', 
                                     sheet_names_filter=['EMAAR UH Equity'],
                                     chunk_size=681197))  # Load all

df = df.rename(columns={'Dates': 'timestamp', 'Type': 'type', 'Price': 'price', 'Size': 'volume'})
df['type'] = df['type'].str.lower()
df = df[['timestamp', 'type', 'price', 'volume']].copy()

print(f"Loaded {len(df)} rows")

# Create handler with 50% threshold
v2_1_config = {}
for sec, sec_config in config.items():
    v2_1_config[sec] = sec_config.copy()
    v2_1_config[sec]['stop_loss_threshold_pct'] = 50.0

handler = create_v2_1_stop_loss_handler(config=v2_1_config)
ob = OrderBook()
state = {}

print("Running backtest...")
state = handler('EMAAR', df, ob, state)

print(f"\nCompleted: {len(state['trades'])} trades")
print(f"Stop-loss triggers: {state.get('stop_loss_triggered_count', 0)}")

print("\nFirst 10 trades:")
for i, t in enumerate(state['trades'][:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")
