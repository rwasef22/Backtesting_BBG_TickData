"""Test ADNOCGAS flattening logic to debug May 14 issue."""
import sys
import json
from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v1_baseline.handler import create_v1_handler

# Load V1 config
with open('configs/v1_baseline_config.json', 'r') as f:
    config = json.load(f)

# Create handler
handler = create_v1_handler(config)

# Create backtest
backtest = MarketMakingBacktest()

print("Running V1 test on ADNOCGAS only...")
print("=" * 80)

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    header_row=3,
    chunk_size=100000,
    only_trades=False,  # Include all events to see bids/asks
    sheet_names_filter=['ADNOCGAS UH Equity'],  # Process only ADNOCGAS
    handler=handler,
    write_csv=False
)

# Print results
for security, state in results.items():
    if 'ADNOCGAS' in security or 'GAS' in security:
        print(f"\nSecurity: {security}")
        print(f"Total trades: {len(state.get('trades', []))}")
        
        # Find May 14 trades
        trades = state.get('trades', [])
        may_14_trades = [t for t in trades if '2025-05-14' in str(t['timestamp'])]
        
        if may_14_trades:
            print(f"\nMay 14, 2025 trades (last 10):")
            for t in may_14_trades[-10:]:
                print(f"  {t['timestamp']} | {t['side']} | Price: {t['fill_price']} | Qty: {t['fill_qty']} | Pos: {t['position']} | PnL: {t['realized_pnl']:.2f}")
        
        # Find first May 15 trades
        may_15_trades = [t for t in trades if '2025-05-15' in str(t['timestamp'])]
        if may_15_trades:
            print(f"\nMay 15, 2025 trades (first 5):")
            for t in may_15_trades[:5]:
                print(f"  {t['timestamp']} | {t['side']} | Price: {t['fill_price']} | Qty: {t['fill_qty']} | Pos: {t['position']} | PnL: {t['realized_pnl']:.2f}")

print("\n" + "=" * 80)
print("Test complete")
