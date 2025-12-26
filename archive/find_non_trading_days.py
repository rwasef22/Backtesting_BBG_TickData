"""Find which days ADNOCGAS has market data but doesn't trade."""

from src.data_loader import stream_sheets, preprocess_chunk_df
from src.market_making_backtest import MarketMakingBacktest
from src.market_making_strategy import MarketMakingStrategy
from src.mm_handler import create_mm_handler
import json

# Load config
with open('configs/mm_config.json', 'r') as f:
    config = json.load(f)

strategy = MarketMakingStrategy(config)
backtest = MarketMakingBacktest(strategy)
mm_handler = create_mm_handler(config)

file_path = 'data/raw/TickData.xlsx'

print("Finding days where ADNOCGAS has data but doesn't trade...")
print("=" * 80)

# Run backtest to get trading days
results = backtest.run_streaming(
    file_path=file_path,
    header_row=3,
    chunk_size=100000,
    only_trades=False,
    max_sheets=4,
    handler=mm_handler,
    write_csv=False
)

adnocgas_result = results.get('ADNOCGAS', {})
market_dates = adnocgas_result.get('market_dates', set())
trading_dates = set()

# Get dates where we actually traded
for trade in adnocgas_result.get('trades', []):
    trading_dates.add(trade['timestamp'].date())

market_dates_list = sorted(market_dates)
trading_dates_list = sorted(trading_dates)
non_trading_dates = sorted(market_dates - trading_dates)

print(f"\nTotal market days: {len(market_dates)}")
print(f"Trading days: {len(trading_dates)}")
print(f"Non-trading days: {len(non_trading_dates)}")

print(f"\n{'='*80}")
print("FIRST 10 NON-TRADING DAYS:")
print(f"{'='*80}")
for i, date in enumerate(non_trading_dates[:10], 1):
    print(f"{i}. {date}")

print(f"\n{'='*80}")
print(f"First non-trading day to test in isolation: {non_trading_dates[0]}")
print(f"{'='*80}")
