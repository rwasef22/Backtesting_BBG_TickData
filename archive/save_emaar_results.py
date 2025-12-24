#!/usr/bin/env python
"""Run backtest on EMAAR with file-based output"""
import sys
sys.path.insert(0, '.')

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
import time

# Open output file
with open('emaar_full_results.txt', 'w') as f:
    f.write("Starting EMAAR full dataset backtest...\n\n")
    f.flush()
    
    start = time.time()
    
    try:
        backtest = MarketMakingBacktest()
        handler = create_mm_handler()
        
        f.write(f"[{time.time()-start:.1f}s] Loading and processing data...\n")
        f.flush()
        
        results = backtest.run_streaming(
            file_path='data/raw/TickData.xlsx',
            handler=handler,
            max_sheets=1,
            only_trades=False
        )
        
        elapsed = time.time() - start
        
        f.write(f"\n{'='*70}\n")
        f.write(f"BACKTEST COMPLETE ({elapsed:.1f}s)\n")
        f.write(f"{'='*70}\n\n")
        
        for security in sorted(results.keys()):
            data = results[security]
            f.write(f"{security}:\n")
            f.write(f"  Rows processed: {data.get('rows', 0):,}\n")
            f.write(f"  Bids: {data.get('bid_count', 0):,} | Asks: {data.get('ask_count', 0):,} | Trades: {data.get('trade_count', 0):,}\n")
            f.write(f"  Last price: ${data.get('last_price', 0):.3f}\n")
            f.write(f"  Position: {data.get('position', 0):,}\n")
            f.write(f"  Total P&L: ${data.get('pnl', 0):.2f}\n")
            
            trades = data.get('trades', [])
            if trades:
                f.write(f"  Trades executed: {len(trades)}\n")
                for i, trade in enumerate(trades[:15], 1):
                    fill_qty = int(trade.get('fill_qty', 0))
                    fill_price = trade.get('fill_price', 0)
                    pnl = trade.get('pnl', 0)
                    side = trade.get('side', 'unknown')
                    f.write(f"    {i:>3}. {side.upper():>4} {fill_qty:>10,} @ ${fill_price:>7.3f} | P&L: ${pnl:>10.2f}\n")
                if len(trades) > 15:
                    f.write(f"    ... and {len(trades) - 15} more trades\n")
        
        f.write(f"\n{'='*70}\n")
        f.write(f"Total time: {elapsed:.1f} seconds\n")
        f.write(f"{'='*70}\n\n")
        
    except Exception as e:
        f.write(f"ERROR: {e}\n")
        import traceback
        f.write(traceback.format_exc())
    
    f.flush()

print("Results written to emaar_full_results.txt")
