#!/usr/bin/env python
"""Demo runner for streaming Excel loader.

Usage:
  - Update `EXCEL_FILE` to point to your TickData.xlsx
  - Run: python scripts/run_backtest.py

This script demonstrates streaming sheet/chunk processing without converting to CSV.
"""
import os
from src.market_making_backtest import MarketMakingBacktest

EXCEL_FILE = os.path.join('data', 'raw', 'TickData.xlsx')


def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"Excel file not found: {EXCEL_FILE}")
        print("No data to process. Update EXCEL_FILE path or place TickData.xlsx accordingly.")
        return

    print("Starting streaming backtest (sheet-by-sheet, chunk-by-chunk)...\n")

    backtest = MarketMakingBacktest()
    results = backtest.run_streaming(EXCEL_FILE, header_row=3, chunk_size=200000)

    print("\nBacktest streaming complete. Summary per security:")
    for sec, state in results.items():
        rows = state.get('rows', 0)
        bids = state.get('bid_count', 0)
        asks = state.get('ask_count', 0)
        trades = state.get('trade_count', 0)
        last_price = state.get('last_price', 'N/A')
        print(f"  {sec:30} | Rows: {rows:>8,} | Bids: {bids:>6,} | Asks: {asks:>6,} | Trades: {trades:>6,} | Last price: {last_price}")


if __name__ == '__main__':
    main()
import pandas as pd
from src.data_loader import load_tick_data
from src.backtest import Backtest

def main():
    # Load tick data from Excel
    tick_data = load_tick_data('data/raw/ticks.xlsx')

    # Initialize the backtest
    backtest = Backtest(tick_data)

    # Run the backtest
    results = backtest.run()

    # Output results
    print("Backtest Results:")
    print(results)

if __name__ == "__main__":
    main()