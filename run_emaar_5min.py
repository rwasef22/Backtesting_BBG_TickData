#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
import time

print("Running EMAAR backtest with refill_interval_sec=300 (5 minutes)")
start = time.time()

cfg = {'EMAAR': {'refill_interval_sec': 300}}
handler = create_mm_handler(config=cfg)
backtest = MarketMakingBacktest()

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=1,
    only_trades=False
)

elapsed = time.time() - start
print(f"\nElapsed time: {elapsed:.1f}s\n")

for security in sorted(results.keys()):
    data = results[security]
    print(f"{security}:")
    print(f"  Rows processed: {data.get('rows', 0):,}")
    print(f"  Bids: {data.get('bid_count', 0):,} | Asks: {data.get('ask_count', 0):,} | Trades: {data.get('trade_count', 0):,}")
    print(f"  Last price: ${data.get('last_price', 0):.3f}")
    print(f"  Position: {data.get('position', 0):,}")
    print(f"  Total P&L: ${data.get('pnl', 0):.2f}")
    trades = data.get('trades', [])
    if trades:
        print(f"  Trades executed: {len(trades)}")
        for i, trade in enumerate(trades[:5], 1):
            fill_qty = int(trade.get('fill_qty', 0))
            fill_price = trade.get('fill_price', 0)
            pnl = trade.get('pnl', 0)
            side = trade.get('side', 'unknown')
            print(f"    {i}. {side.upper():>4} {fill_qty:>8,} @ ${fill_price:>7.3f} | P&L: ${pnl:>10.2f}")
        if len(trades) > 5:
            print(f"    ... and {len(trades) - 5} more trades")

print('\nDone.')
