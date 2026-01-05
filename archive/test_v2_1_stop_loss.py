"""
Test script for V2.1 Stop Loss strategy.

Run a single security (EMAAR) to verify:
1. Stop loss triggers correctly at 2% loss
2. Partial liquidation works when liquidity insufficient
3. Full liquidation completes when liquidity available
4. Strategy maintains V2 profitability while reducing drawdowns
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v2_1_stop_loss import create_v2_1_stop_loss_handler


def load_config(config_path: str) -> dict:
    """Load strategy configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def test_v2_1_emaar():
    """Test V2.1 with EMAAR."""
    print("=" * 80)
    print("V2.1 STOP LOSS STRATEGY TEST")
    print("Security: EMAAR")
    print("Stop Loss Threshold: 2.0%")
    print("=" * 80)
    print()
    
    # Load config
    config_path = "configs/v2_1_stop_loss_config.json"
    config = load_config(config_path)
    
    # Create handler
    handler = create_v2_1_stop_loss_handler(config=config)
    
    # Run backtest
    security = "EMAAR"
    backtest = MarketMakingBacktest()
    results = backtest.run_streaming(
        file_path='data/raw/TickData.xlsx',
        handler=handler,
        only_trades=False,
        max_sheets=1  # Process only first sheet (EMAAR)
    )
    
    # Display results
    # The security key might not be exactly "EMAAR" - check what we got
    if not results:
        print("\nNo results found")
        return
    
    # Get first (and only) security
    security = list(results.keys())[0]
    state = results[security]
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total Rows Processed: {state.get('rows', 0):,}")
    print(f"  - Bid Updates: {state.get('bid_count', 0):,}")
    print(f"  - Ask Updates: {state.get('ask_count', 0):,}")
    print(f"  - Trades: {state.get('trade_count', 0):,}")
    print()
    print(f"Strategy Trades: {len(state.get('trades', []))}")
    print(f"Stop Loss Triggers: {state.get('stop_loss_triggered_count', 0)}")
    print(f"Final Position: {state.get('position', 0)}")
    print(f"Total P&L: {state.get('pnl', 0):,.2f} AED")
    print()
    
    # Show trade details
    trades = state.get('trades', [])
    if trades:
        print("TRADE DETAILS:")
        print("-" * 80)
        buy_trades = [t for t in trades if t['side'] == 'buy']
        sell_trades = [t for t in trades if t['side'] == 'sell']
        
        print(f"Buy Trades: {len(buy_trades)}")
        print(f"Sell Trades: {len(sell_trades)}")
        print()
        
        # Show first 10 and last 10 trades
        print("First 10 trades:")
        for i, trade in enumerate(trades[:10], 1):
            print(f"  {i}. {trade['timestamp']} | {trade['side']:4s} | "
                  f"Price: {trade['fill_price']:7.2f} | Qty: {trade['fill_qty']:5d} | "
                  f"P&L: {trade['pnl']:8.2f}")
        
        if len(trades) > 20:
            print(f"  ... ({len(trades) - 20} trades omitted) ...")
        
        if len(trades) > 10:
            print("Last 10 trades:")
            for i, trade in enumerate(trades[-10:], len(trades) - 9):
                print(f"  {i}. {trade['timestamp']} | {trade['side']:4s} | "
                      f"Price: {trade['fill_price']:7.2f} | Qty: {trade['fill_qty']:5d} | "
                      f"P&L: {trade['pnl']:8.2f}")
    
    print("=" * 80)
    
    # Compare with V2 results (if available)
    print("\nTo compare with V2 baseline, run:")
    print("  python run_v2_simple.py")


if __name__ == "__main__":
    test_v2_1_emaar()
