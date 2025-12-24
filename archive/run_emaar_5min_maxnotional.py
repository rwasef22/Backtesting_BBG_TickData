#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run EMAAR 5-min backtest with config file.')
    parser.add_argument('--config-file', '-c', default='configs/mm_config.json', help='Path to JSON config file')
    parser.add_argument('--excel-file', '-f', default='data/raw/TickData.xlsx', help='Path to tick data Excel file')
    args = parser.parse_args()

    cfg = load_strategy_config(args.config_file)

    print(f"Running EMAAR backtest with config from {args.config_file}", flush=True)
    print(f"Configured securities: {', '.join(sorted(cfg.keys()))}", flush=True)
    print(f"Processing all sheets (max_sheets=None)...", flush=True)
    start = time.time()

    handler = create_mm_handler(config=cfg)
    backtest = MarketMakingBacktest()

    results = backtest.run_streaming(
        file_path=args.excel_file,
        handler=handler,
        max_sheets=None,
        only_trades=False
    )
    
    print(f"Backtest completed. Results keys: {list(results.keys())}", flush=True)

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


if __name__ == '__main__':
    main()
