"""Test ADNOCGAS with 120s interval to verify EOD flatten fix."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.mm_handler import create_mm_handler

print("="*80)
print("ADNOCGAS 120s Test - Verify EOD Flatten Fix")
print("="*80)

# Load V1 config
base_config = load_strategy_config('configs/v1_baseline_config.json')

# Override refill interval to 120s
config = {}
for security, params in base_config.items():
    config[security] = params.copy()
    config[security]['refill_interval_sec'] = 120

# Create handler with 120s interval
handler = create_mm_handler(config=config)

# Initialize backtest
backtest = MarketMakingBacktest()

# Run only ADNOCGAS with 120s interval
print("\nRunning V1 strategy on ADNOCGAS with 120s interval...")
print("-"*80)

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    sheet_names_filter=['ADNOCGAS UH Equity'],
    max_sheets=None,
    only_trades=False
)

# Display results
print("\n" + "="*80)
print("RESULTS")
print("="*80)

for security, data in results.items():
    print(f"\nSecurity: {security}")
    print(f"  Total trades: {len(data['trades'])}")
    print(f"  Final P&L: {data['pnl']:.2f} AED")
    print(f"  Final position: {data['position']}")
    
    # Check May 14 trades
    may14_trades = [t for t in data['trades'] 
                   if t['timestamp'].date().strftime('%Y-%m-%d') == '2025-05-14']
    
    if may14_trades:
        last_may14 = may14_trades[-1]
        print(f"\n  May 14 last trade (EOD flatten):")
        print(f"    Timestamp: {last_may14['timestamp']}")
        print(f"    Side: {last_may14['side']}")
        print(f"    Price: {last_may14['fill_price']:.2f}")
        print(f"    Quantity: {last_may14['fill_qty']}")
        print(f"    P&L: {last_may14['pnl']:.2f}")
        
        if abs(last_may14['fill_price'] - 3.26) < 0.01:
            print(f"\n  ✓ SUCCESS: EOD flatten used correct trade price 3.26")
        elif abs(last_may14['fill_price'] - 3.76) < 0.01:
            print(f"\n  ✗ FAILURE: EOD flatten used wrong bid price 3.76")
        else:
            print(f"\n  ? UNEXPECTED: EOD flatten price is {last_may14['fill_price']:.2f}")

print("\n" + "="*80)
