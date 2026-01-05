"""
Check WHY stop-loss triggers at 10:17:37 with 50% threshold
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

# Patch should_trigger_stop_loss to log details
original_should_trigger = V21StopLossStrategy.should_trigger_stop_loss

def logged_should_trigger(self, security, mid_price):
    position = self.position[security]
    if position != 0:
        pnl_pct = self.get_unrealized_pnl_pct(security, mid_price)
        cfg = self.get_config(security)
        threshold_pct = cfg.get('stop_loss_threshold_pct', 2.0)
        cost_basis = self.position_cost_basis[security]
        entry_price = self.entry_price.get(security, 0)
        
        # Log around first trigger
        if position == -2691:
            print(f"\n[CHECK] pos={position}, mid_price={mid_price:.2f}, entry={entry_price:.2f}")
            print(f"        cost_basis={cost_basis:.2f}, pnl_pct={pnl_pct:.2f}%, threshold={threshold_pct}%")
    
    result = original_should_trigger(self, security, mid_price)
    if result and position == -2691:
        print(f"        => TRIGGER! pnl_pct ({pnl_pct:.2f}%) < -threshold ({-threshold_pct}%)")
    return result

V21StopLossStrategy.should_trigger_stop_loss = logged_should_trigger

# Load config
config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')

# Create config with 50% threshold
v2_1_config = {}
for sec, sec_config in config.items():
    v2_1_config[sec] = sec_config.copy()
    v2_1_config[sec]['stop_loss_threshold_pct'] = 50.0

# Load data
print("Loading EMAAR data...")
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
    
    if trades >= 10:
        print(f"\nStopping after {trades} trades")
        break

print(f"\nFirst 10 trades:")
for i, t in enumerate(state['trades'][:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:6.0f} pos={t['position']:6.0f}")
