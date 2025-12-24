#!/usr/bin/env python
"""Debug: run backtest and log why quotes are blocked during gap."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
from src.market_making_strategy import MarketMakingStrategy
from datetime import date

# Patch the strategy to log blocking reasons
original_generate_quotes = MarketMakingStrategy.generate_quotes

def logged_generate_quotes(self, security, best_bid, best_ask):
    """Wrapped version that logs why quotes might be blocked."""
    cfg = self.get_config(security)
    current_pos = self.position[security]
    max_pos = cfg['max_position']
    max_notional = cfg.get('max_notional')
    
    if best_bid and best_ask:
        bid_price, _ = best_bid
        ask_price, _ = best_ask
        if max_notional and bid_price > 0 and ask_price > 0:
            mid = (bid_price + ask_price) / 2
            dynamic_max = int(max_notional / mid)
            if dynamic_max < current_pos:
                print(f"[BLOCKED by max_notional] pos={current_pos}, dynamic_max={dynamic_max}, mid={mid:.2f}")
    
    return original_generate_quotes(self, security, best_bid, best_ask)

MarketMakingStrategy.generate_quotes = logged_generate_quotes

# Run backtest with logging
cfg = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=cfg)
backtest = MarketMakingBacktest()

print("Running EMAAR backtest with quote blocking logging...\n")

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=1,
    only_trades=False
)

for security in results.keys():
    data = results[security]
    print(f"\n{security}:")
    print(f"  Position: {data['position']}")
    print(f"  P&L: ${data['pnl']:.2f}")
    print(f"  Trades: {len(data.get('trades', []))}")
