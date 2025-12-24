#!/usr/bin/env python
"""Quick plot regeneration with per-side quoting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

import pandas as pd
import matplotlib.pyplot as plt
from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config

OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print('Running EMAAR backtest with per-side quoting...', flush=True)

cfg = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=cfg)
backtest = MarketMakingBacktest()

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=None,
    only_trades=False
)

sec_key = 'EMAAR'
state = results[sec_key]
trades = state.get('trades', [])

print(f'Trades collected: {len(trades)}', flush=True)

if not trades:
    print('No trades recorded.')
    sys.exit(0)

# Build DataFrame
trade_df = pd.DataFrame(trades)
trade_df = trade_df.sort_values('timestamp').reset_index(drop=True)
trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])

# Save CSV
csv_path = OUTPUT_DIR / 'emaar_5min_trades_timeseries.csv'
trade_df[['timestamp','position','pnl']].to_csv(csv_path, index=False)
print(f'Saved CSV: {csv_path}', flush=True)

# Plot
fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
axes[0].plot(trade_df['timestamp'], trade_df['position'], color='tab:blue')
axes[0].set_title('EMAAR - Inventory vs Time (5-min refill, per-side quoting)')
axes[0].set_ylabel('Position (shares)')
axes[0].grid(True, linestyle='--', alpha=0.3)

axes[1].plot(trade_df['timestamp'], trade_df['pnl'], color='tab:green')
axes[1].set_title('EMAAR - P&L vs Time (realized)')
axes[1].set_ylabel('P&L (local currency)')
axes[1].set_xlabel('Time')
axes[1].grid(True, linestyle='--', alpha=0.3)

fig.autofmt_xdate()

img_path = OUTPUT_DIR / 'emaar_5min_inventory_pnl.png'
plt.tight_layout()
plt.savefig(img_path, dpi=144)
print(f'Saved plot: {img_path}', flush=True)
print('Done!', flush=True)
