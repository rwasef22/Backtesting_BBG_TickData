"""
Debug version of V3 test with detailed logging.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v3_liquidity_monitor import create_v3_liquidity_monitor_handler


def main():
    """Run V3 strategy test with debug logging."""
    
    # Load V3 configuration
    config_path = Path('configs/v3_liquidity_monitor_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Override EMAAR config to use 30s interval
    config['EMAAR']['refill_interval_sec'] = 30
    
    print("Config for EMAAR:")
    print(f"  quote_size: {config['EMAAR']['quote_size']}")
    print(f"  refill_interval: {config['EMAAR']['refill_interval_sec']}s")
    print(f"  max_position: {config['EMAAR']['max_position']}")
    print(f"  min_liquidity: {config['EMAAR']['min_local_currency_before_quote']} AED")
    print()
    
    # Create V3 handler
    v3_handler = create_v3_liquidity_monitor_handler(config=config)
    
    # Setup backtest
    backtest = MarketMakingBacktest()
    
    print("=" * 80)
    print("V3 DEBUG TEST - EMAAR with 30s")
    print("=" * 80)
    print()
    
    test_security = "EMAAR UH Equity"
    
    # Run backtest on smaller chunk to debug
    results = backtest.run_streaming(
        file_path='data/raw/TickData.xlsx',
        handler=v3_handler,
        sheet_names_filter=[test_security],
        chunk_size=10000,  # Smaller chunks for faster iteration
        output_dir='output/v3_debug',
        write_csv=True
    )
    
    # Display results
    if test_security in results:
        result = results[test_security]
        trades = result.get('trades', [])
        
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"Total Trades: {len(trades)}")
        print(f"Rows processed: {result.get('rows', 0)}")
        print(f"Bid events: {result.get('bid_count', 0)}")
        print(f"Ask events: {result.get('ask_count', 0)}")
        print(f"Trade events: {result.get('trade_count', 0)}")
        print(f"Final Position: {result.get('position', 0)}")
        print(f"Total P&L: {result.get('pnl', 0):,.2f} AED")
        
        if trades:
            print(f"\nFirst 5 trades:")
            for i, t in enumerate(trades[:5]):
                print(f"  {i+1}. {t['timestamp']} - {t['side']} {t['fill_qty']} @ {t['fill_price']}, pnl={t['realized_pnl']}")
        else:
            print("\n⚠ NO TRADES - Something is wrong!")
            print("\nLet me check a sample of orderbook data...")
            # The issue is likely that quotes aren't being placed
    else:
        print(f"\n✗ No results for {test_security}")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
