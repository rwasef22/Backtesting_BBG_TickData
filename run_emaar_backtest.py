#!/usr/bin/env python
"""Run backtest on EMAAR with progress tracking"""
import sys
sys.path.insert(0, '.')

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
import time

print("Starting EMAAR backtest (all data)...", flush=True)
start = time.time()

backtest = MarketMakingBacktest()
handler = create_mm_handler()

print(f"[{time.time()-start:.1f}s] Loading data...", flush=True)

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=1,
    only_trades=False
)

elapsed = time.time() - start
print(f"\n{'='*70}")
print(f"BACKTEST COMPLETE ({elapsed:.1f}s)")
print(f"{'='*70}\n")

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
        if trades:
            for i, trade in enumerate(trades[:10], 1):
                fill_qty = int(trade.get('fill_qty', 0))
                fill_price = trade.get('fill_price', 0)
                pnl = trade.get('pnl', 0)
                side = trade.get('side', 'unknown')
                print(f"    {i}. {side.upper():>4} {fill_qty:>10,} @ ${fill_price:>7.3f} | P&L: ${pnl:>10.2f}")
            if len(trades) > 10:
                print(f"    ... and {len(trades) - 10} more trades")

print(f"{'='*70}\n")
print(f"Total time: {elapsed:.1f} seconds")
