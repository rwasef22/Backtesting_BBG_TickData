#!/usr/bin/env python
"""Quick backtest test on real TickData.xlsx"""
import sys
sys.path.insert(0, '.')

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
import time

start = time.time()
print("Starting backtest on TickData.xlsx first security...", flush=True)

backtest = MarketMakingBacktest()
handler = create_mm_handler()

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    max_sheets=1,
    only_trades=False
)

print("\n" + "="*70)
print("BACKTEST RESULTS - TickData.xlsx (First Security)")
print("="*70 + "\n")

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
            fill_qty = trade.get('fill_qty', 0)
            fill_price = trade.get('fill_price', 0)
            pnl = trade.get('pnl', 0)
            side = trade.get('side', 'unknown')
            print(f"    {i}. {side.upper():>4} {int(fill_qty):>8,} @ ${fill_price:>7.3f} | P&L: ${pnl:>10.2f}")
        if len(trades) > 5:
            print(f"    ... and {len(trades) - 5} more trades")

elapsed = time.time() - start
print(f"\nElapsed time: {elapsed:.2f} seconds")
print("="*70 + "\n")
