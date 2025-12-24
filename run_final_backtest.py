#!/usr/bin/env python
"""
Run the market-making backtest and output results to CSV files.
This includes the fix for opening auction handling.
"""
import sys
import os
from pathlib import Path
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config


def main():
    print("\n" + "="*80)
    print("MARKET-MAKING BACKTEST WITH OPENING AUCTION FIX")
    print("="*80 + "\n")
    
    # Load config
    config_file = 'configs/mm_config.json'
    with open(config_file) as f:
        mm_config = json.load(f)
    
    print(f"Config: {mm_config}\n")
    
    # Create handler
    mm_handler = create_mm_handler(config=mm_config)
    
    # Run backtest
    backtest = MarketMakingBacktest()
    print("Running backtest on full dataset...")
    print("(This may take 2-3 minutes)\n")
    
    results = backtest.run_streaming(
        file_path='data/raw/TickData.xlsx',
        handler=mm_handler,
        only_trades=False,
    )
    
    # Print results
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80 + "\n")
    
    for security in sorted(results.keys()):
        data = results[security]
        trades_list = data.get('trades', [])
        position = data.get('position', 0)
        pnl = data.get('pnl', 0)
        
        print(f"\n{security}:")
        print(f"  Total rows processed: {data.get('rows', 0):,}")
        print(f"  Bid events: {data.get('bid_count', 0):,}")
        print(f"  Ask events: {data.get('ask_count', 0):,}")
        print(f"  Trade events: {data.get('trade_count', 0):,}")
        print(f"  Final position: {position:,}")
        print(f"  Total P&L: ${pnl:,.2f}")
        print(f"  Total fills: {len(trades_list)}")
        
        if trades_list:
            # Count trades by side and date
            buy_trades = [t for t in trades_list if t.get('side') == 'buy']
            sell_trades = [t for t in trades_list if t.get('side') == 'sell']
            
            print(f"    Buy trades: {len(buy_trades)}")
            print(f"    Sell trades: {len(sell_trades)}")
            
            # Show date range of trades
            if trades_list:
                dates = set()
                for trade in trades_list:
                    ts = trade.get('timestamp')
                    if ts is not None:
                        dates.add(str(ts.date()))
                if dates:
                    min_date = min(dates)
                    max_date = max(dates)
                    print(f"    Date range: {min_date} to {max_date}")
            
            # Show first and last few trades
            print(f"\n  First 5 trades:")
            for i, trade in enumerate(trades_list[:5], 1):
                side = trade.get('side', 'unknown').upper()
                qty = trade.get('fill_qty', 0)
                price = trade.get('fill_price', 0)
                ts = trade.get('timestamp')
                print(f"    {i}. {ts} | {side:>4} {qty:>8,} @ ${price:>7.3f}")
            
            if len(trades_list) > 10:
                print(f"\n  Last 5 trades:")
                for i, trade in enumerate(trades_list[-5:], len(trades_list)-4):
                    side = trade.get('side', 'unknown').upper()
                    qty = trade.get('fill_qty', 0)
                    price = trade.get('fill_price', 0)
                    ts = trade.get('timestamp')
                    print(f"    {i}. {ts} | {side:>4} {qty:>8,} @ ${price:>7.3f}")
    
    print("\n" + "="*80)
    print("Backtest complete!")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
