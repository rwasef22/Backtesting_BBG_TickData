"""Simple script to run v2 strategy - handles encoding better"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config_loader import load_strategy_config
from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v2_price_follow_qty_cooldown import create_v2_price_follow_qty_cooldown_handler
import pandas as pd

print("=" * 80)
print("V2 PRICE FOLLOW QTY COOLDOWN BACKTEST")
print("=" * 80)

# Load config
config = load_strategy_config('configs/mm_config.json')
print(f"\nLoaded config for {len(config)} securities")

# Create handler
handler = create_v2_price_follow_qty_cooldown_handler(config)
print("Handler created")

# Run backtest
print("\nRunning backtest...")
backtest = MarketMakingBacktest()

results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    only_trades=False
)

print(f"\nProcessed {len(results)} securities")

# Save results
output_dir = Path('output/v2_price_follow_qty_cooldown')
output_dir.mkdir(parents=True, exist_ok=True)

summary_data = []
for security, data in results.items():
    trades = data.get('trades', [])
    if trades:
        trade_df = pd.DataFrame(trades)
        
        summary_data.append({
            'security': security,
            'total_trades': len(trades),
            'total_pnl': data.get('pnl', 0),
            'final_position': data.get('position', 0),
            'avg_pnl_per_trade': data.get('pnl', 0) / len(trades) if trades else 0
        })
        
        # Save CSV
        csv_file = output_dir / f'{security}_trades_timeseries.csv'
        trade_df.to_csv(csv_file, index=False)
        print(f"Saved {security}: {len(trades)} trades")

if summary_data:
    summary_df = pd.DataFrame(summary_data)
    summary_file = output_dir / 'backtest_summary.csv'
    summary_df.to_csv(summary_file, index=False)
    print(f"\nSaved summary to {summary_file}")
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(summary_df.to_string(index=False))
    print("=" * 80)

print(f"\nAll files saved to {output_dir}/")
print("Backtest complete!")
