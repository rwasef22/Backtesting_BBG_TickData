"""
Test script for V3 Liquidity Monitor strategy.

This script runs a backtest using the V3 strategy which extends V2
with continuous orderbook depth monitoring.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v3_liquidity_monitor import create_v3_liquidity_monitor_handler


def main():
    """Run V3 strategy test on a single security."""
    
    # Load V3 configuration
    config_path = Path('configs/v3_liquidity_monitor_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Override EMAAR config to use 30s interval for testing
    config['EMAAR']['refill_interval_sec'] = 30
    
    # Create V3 handler
    v3_handler = create_v3_liquidity_monitor_handler(config=config)
    
    # Setup backtest
    backtest = MarketMakingBacktest()
    
    print("=" * 80)
    print("V3 LIQUIDITY MONITOR STRATEGY TEST")
    print("=" * 80)
    print("\nStrategy Features:")
    print("  ✓ Continuous price following (from V2)")
    print("  ✓ Quantity cooldown after fills (from V2)")
    print("  ✓ Continuous liquidity monitoring (NEW in V3)")
    print("  ✓ Auto-withdraw quotes when depth drops below threshold")
    print("  ✓ Auto-restore quotes when depth returns")
    print()
    
    # Run on single security for testing
    test_security = "EMAAR UH Equity"
    print(f"Testing on: {test_security}")
    print(f"Config: refill_interval={config['EMAAR']['refill_interval_sec']}s, "
          f"min_liquidity={config['EMAAR']['min_local_currency_before_quote']} AED")
    print()
    
    # Run backtest
    results = backtest.run_streaming(
        file_path='data/raw/TickData.xlsx',
        handler=v3_handler,
        sheet_names_filter=[test_security],
        chunk_size=100000,
        output_dir='output/v3_test',
        write_csv=True
    )
    
    # Display results
    if test_security in results:
        result = results[test_security]
        trades = result.get('trades', [])
        pnl = result.get('pnl', 0)
        position = result.get('position', 0)
        
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"Security: {test_security}")
        print(f"Total Trades: {len(trades)}")
        print(f"Final Position: {position}")
        print(f"Total P&L: {pnl:,.2f} AED")
        
        if trades:
            print(f"\nFirst Trade: {trades[0]['timestamp']} - {trades[0]['side']} @ {trades[0]['fill_price']}")
            print(f"Last Trade: {trades[-1]['timestamp']} - {trades[-1]['side']} @ {trades[-1]['fill_price']}")
            
            # Calculate some stats
            buys = [t for t in trades if t['side'] == 'buy']
            sells = [t for t in trades if t['side'] == 'sell']
            print(f"\nBuy trades: {len(buys)}")
            print(f"Sell trades: {len(sells)}")
            
            print("\nOutput saved to: output/v3_test/")
    else:
        print(f"\nNo results for {test_security}")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
