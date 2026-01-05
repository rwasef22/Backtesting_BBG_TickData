"""
Check if stop-loss triggers at all with 50% threshold
Monitor the actual unrealized PnL % to see if it ever reaches -50%
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

max_loss_seen = 0.0
trigger_count = 0

# Patch should_trigger_stop_loss to track max loss
original_should_trigger = V21StopLossStrategy.should_trigger_stop_loss

def logged_should_trigger(self, security, mid_price):
    global max_loss_seen, trigger_count
    position = self.position[security]
    if position != 0:
        pnl_pct = self.get_unrealized_pnl_pct(security, mid_price)
        if pnl_pct < max_loss_seen:
            max_loss_seen = pnl_pct
    
    result = original_should_trigger(self, security, mid_price)
    if result:
        trigger_count += 1
        print(f"\n!!! STOP-LOSS TRIGGER #{trigger_count}")
        print(f"    Position: {position}")
        print(f"    Mid price: {mid_price:.2f}")
        print(f"    Entry: {self.entry_price.get(security, 0):.2f}")
        print(f"    PnL %: {pnl_pct:.2f}%")
        print(f"    Cost basis: {self.position_cost_basis[security]:.2f}")
    
    return result

V21StopLossStrategy.should_trigger_stop_loss = logged_should_trigger

# Load config
config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')

# Create config with 50% threshold
v2_1_config = {}
for sec, sec_config in config.items():
    v2_1_config[sec] = sec_config.copy()
    v2_1_config[sec]['stop_loss_threshold_pct'] = 50.0

# Run backtest
print("Running V2.1 backtest with 50% threshold...")
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

print(f"\n{'='*80}")
print(f"RESULTS")
print(f"{'='*80}")
print(f"Total trades: {len(state['trades'])}")
print(f"Stop-loss triggers: {trigger_count}")
print(f"Max unrealized loss seen: {max_loss_seen:.2f}%")
print(f"\nConclusion: ", end="")
if trigger_count == 0:
    print("✅ Stop-loss NEVER triggered (correct for 50% threshold)")
else:
    print(f"❌ Stop-loss triggered {trigger_count} times (shouldn't happen with 50% threshold!)")
