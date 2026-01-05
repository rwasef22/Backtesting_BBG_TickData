"""
Check if stop-loss PENDING is ever set - focused on first 10 trades
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

# Patch trigger_stop_loss to log
original_trigger = V21StopLossStrategy.trigger_stop_loss

def logged_trigger(self, security, timestamp):
    pos = self.position[security]
    print(f"\n!!! [STOP-LOSS TRIGGERED] {timestamp}")
    print(f"    Security: {security}")
    print(f"    Position: {pos}")
    print(f"    Liquidation qty: {abs(pos)}")
    print(f"    Liquidation side: {'BUY' if pos < 0 else 'SELL'}\n")
    return original_trigger(self, security, timestamp)

V21StopLossStrategy.trigger_stop_loss = logged_trigger

# Load config
config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')

# Create config with 50% threshold
v2_1_config = {}
for sec, sec_config in config.items():
    v2_1_config[sec] = sec_config.copy()
    v2_1_config[sec]['stop_loss_threshold_pct'] = 50.0

# Load data in chunks
print("Loading EMAAR data in chunks...")
handler = create_v2_1_stop_loss_handler(config=v2_1_config)
ob = OrderBook()
state = {}

for sheet_name, df in stream_sheets('data/raw/TickData.xlsx', 
                                      sheet_names_filter=['EMAAR UH Equity'],
                                      chunk_size=100000):
    df = df.rename(columns={'Dates': 'timestamp', 'Type': 'type', 'Price': 'price', 'Size': 'volume'})
    df['type'] = df['type'].str.lower()
    df = df[['timestamp', 'type', 'price', 'volume']].copy()
    
    state = handler('EMAAR', df, ob, state)
    
    trades = len(state.get('trades', []))
    print(f"  Chunk processed: {trades} total trades")
    
    if trades >= 10:
        print("  Stopping after 10 trades")
        break

print(f"\nCompleted: {len(state['trades'])} trades")
print(f"Stop-loss triggers: {state.get('stop_loss_triggered_count', 0)}")

print("\nFirst 10 trades:")
for i, t in enumerate(state['trades'][:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")
