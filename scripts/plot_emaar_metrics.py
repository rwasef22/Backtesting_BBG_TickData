#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config

OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_FILE = 'data/raw/TickData.xlsx'
SEC_NAME = 'EMAAR'  # normalized in backtest removing ' UH Equity'


def main():
    parser = argparse.ArgumentParser(description='Run EMAAR plotting backtest with external config.')
    parser.add_argument('--config-file', '-c', default='configs/mm_config.json', help='Path to JSON config file')
    parser.add_argument('--excel-file', '-f', default=EXCEL_FILE, help='Path to tick data Excel file')
    args = parser.parse_args()

    cfg = load_strategy_config(args.config_file)
    handler = create_mm_handler(config=cfg)
    backtest = MarketMakingBacktest()

    print(f'Running EMAAR backtest (5-min refill) with config {args.config_file} to collect metrics...')
    results = backtest.run_streaming(
        file_path=args.excel_file,
        handler=handler,
        max_sheets=None,
        only_trades=False,
    )

    if SEC_NAME not in results:
        # Some sheet names might be normalized differently, try to pick the single entry
        if len(results) == 1:
            sec_key = list(results.keys())[0]
        else:
            raise SystemExit(f"Security {SEC_NAME} not found in results: {list(results.keys())}")
    else:
        sec_key = SEC_NAME

    state = results[sec_key]
    trades = state.get('trades', [])
    if not trades:
        print('No trades recorded; cannot plot inventory/P&L series.')
        sys.exit(0)

    # Build DataFrame from trades
    trade_df = pd.DataFrame(trades)
    trade_df = trade_df.sort_values('timestamp').reset_index(drop=True)
    # Ensure timestamp is datetime
    trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])

    # Save CSV for reference
    csv_path = OUTPUT_DIR / 'emaar_5min_trades_timeseries.csv'
    trade_df[['timestamp','position','pnl']].to_csv(csv_path, index=False)

    # Extract configuration parameters
    emaar_config = cfg.get('EMAAR', cfg.get(sec_key, {}))
    base_quote_size = emaar_config.get('quote_size', 50000)
    quote_size_bid = emaar_config.get('quote_size_bid', base_quote_size)
    quote_size_ask = emaar_config.get('quote_size_ask', base_quote_size)
    min_qty_front = emaar_config.get('min_local_currency_before_quote', 25000)
    refill_period = emaar_config.get('refill_interval_sec', 60)
    max_position = emaar_config.get('max_position', 2000000)
    
    # Format quote size display
    if quote_size_bid == quote_size_ask:
        quote_size_str = f"{quote_size_bid:,}"
    else:
        quote_size_str = f"{quote_size_bid:,} / {quote_size_ask:,} (bid/ask)"
    
    # Create parameter text
    param_text = (
        f"Quote Size: {quote_size_str}\n"
        f"Min Qty in Front: {min_qty_front:,}\n"
        f"Refill Period: {refill_period}s\n"
        f"Max Position: {max_position:,}"
    )

    # Plot inventory and P&L vs time
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(trade_df['timestamp'], trade_df['position'], color='tab:blue', linewidth=1.5)
    axes[0].set_title('EMAAR - Inventory vs Time (5-min refill)')
    axes[0].set_ylabel('Position (shares)')
    axes[0].grid(True, linestyle='--', alpha=0.3)
    axes[0].axhline(y=0, color='red', linestyle='--', alpha=0.5)
    
    # Add parameter text box
    axes[0].text(0.02, 0.98, param_text, transform=axes[0].transAxes,
               fontsize=9, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    axes[1].plot(trade_df['timestamp'], trade_df['pnl'], color='tab:green', linewidth=1.5)
    axes[1].set_title('EMAAR - P&L vs Time (realized)')
    axes[1].set_ylabel('P&L (local currency)')
    axes[1].set_xlabel('Time')
    axes[1].grid(True, linestyle='--', alpha=0.3)
    axes[1].axhline(y=0, color='red', linestyle='--', alpha=0.5)

    fig.autofmt_xdate()

    img_path = OUTPUT_DIR / 'emaar_5min_inventory_pnl.png'
    plt.tight_layout()
    plt.savefig(img_path, dpi=144)
    print(f'Saved plots to {img_path}')
    print(f'Saved time series CSV to {csv_path}')


if __name__ == '__main__':
    main()
