#!/usr/bin/env python
"""Run backtest and inspect trades during gap period."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
from datetime import date
import time

gap_start = date(2025, 4, 23)
gap_end = date(2025, 6, 18)

print("Running backtest and checking trades in gap period...\n")

cfg = load_strategy_config('configs/mm_config.json')
handler = create_mm_handler(config=cfg)
backtest = MarketMakingBacktest()

start_time = time.time()
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=1,
    only_trades=False
)
elapsed = time.time() - start_time

for security in sorted(results.keys()):
    data = results[security]
    trades = data.get('trades', [])
    
    print(f"{security}:")
    print(f"  Total trades executed: {len(trades)}")
    print(f"  Final position: {data.get('position', 0)}")
    print(f"  Total P&L: ${data.get('pnl', 0):.2f}")
    print(f"  Elapsed: {elapsed:.1f}s")
    
    # Check trades in gap
    trades_in_gap = [t for t in trades if hasattr(t.get('timestamp'), 'date') and gap_start <= t['timestamp'].date() <= gap_end]
    
    print(f"\n  Trades during gap ({gap_start} to {gap_end}): {len(trades_in_gap)}")
    
    if len(trades_in_gap) > 0:
        print(f"  First 5 trades in gap:")
        for t in trades_in_gap[:5]:
            print(f"    {t['timestamp']}: {t['side']} {t['fill_qty']:.0f} @ ${t['fill_price']:.2f}, pos={t['position']}, pnl=${t['pnl']:.2f}")
    else:
        print(f"  ⚠️  NO TRADES during gap period!")
        
        # Show trades before and after gap
        trades_before = [t for t in trades if hasattr(t.get('timestamp'), 'date') and t['timestamp'].date() < gap_start]
        trades_after = [t for t in trades if hasattr(t.get('timestamp'), 'date') and t['timestamp'].date() > gap_end]
        
        if trades_before:
            last_before = trades_before[-1]
            print(f"  Last trade before gap: {last_before['timestamp']} - {last_before['side']} {last_before['fill_qty']:.0f} @ ${last_before['fill_price']:.2f}")
        
        if trades_after:
            first_after = trades_after[0]
            print(f"  First trade after gap: {first_after['timestamp']} - {first_after['side']} {first_after['fill_qty']:.0f} @ ${first_after['fill_price']:.2f}")
