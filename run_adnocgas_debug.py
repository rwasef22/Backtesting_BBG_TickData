"""Run ADNOCGAS only with detailed day-by-day logging."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
from collections import defaultdict

# Load config
mm_config = load_strategy_config('configs/mm_config.json')

# Track daily activity
daily_log = defaultdict(lambda: {
    'bids': 0,
    'asks': 0,
    'trades': 0,
    'rows': 0,
    'liquidity_checks': 0,
    'quotes_generated': 0,
    'bid_quotes': 0,
    'ask_quotes': 0,
    'strategy_trades': 0
})

# Wrap the handler to log activity
original_handler = create_mm_handler(config=mm_config)

def logging_handler(security, df, orderbook, state):
    """Wrapped handler with daily logging."""
    # Skip non-ADNOCGAS securities
    if security != 'ADNOCGAS':
        return original_handler(security, df, orderbook, state)
    
    # Track daily stats
    if not df.empty:
        current_date = df['timestamp'].iloc[0].date()
        daily_log[current_date]['rows'] += len(df)
        daily_log[current_date]['bids'] += (df['type'] == 'bid').sum()
        daily_log[current_date]['asks'] += (df['type'] == 'ask').sum()
        daily_log[current_date]['trades'] += (df['type'] == 'trade').sum()
    
    # Call original handler
    result = original_handler(security, df, orderbook, state)
    
    # Track strategy trades
    if not df.empty:
        current_trades = state.get('trades', 0)
        if isinstance(current_trades, (int, float)):
            daily_log[current_date]['strategy_trades'] = int(current_trades)
    
    return result

# Run backtest for ADNOCGAS only
print(f"\n{'='*80}")
print(f"ADNOCGAS Detailed Day-by-Day Backtest")
print(f"{'='*80}\n")

backtest = MarketMakingBacktest()
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=logging_handler,
    max_sheets=None,  # All sheets
    only_trades=False
)

# Analyze results
print(f"\n{'='*80}")
print("Daily Analysis")
print(f"{'='*80}\n")

adnocgas_result = results.get('ADNOCGAS', {})
total_trades = adnocgas_result.get('trades', 0)
print(f"Total strategy trades: {total_trades}")

# Analyze non-trading days
trading_days = []
no_trading_days = []

for date in sorted(daily_log.keys()):
    stats = daily_log[date]
    if stats['strategy_trades'] > 0:
        trading_days.append(date)
    else:
        no_trading_days.append(date)

print(f"\n Days with trading: {len(trading_days)}")
print(f"Days without trading: {len(no_trading_days)}")
print(f"Coverage: {len(trading_days)/len(daily_log)*100:.1f}%\n")

# Show sample non-trading days
print("Sample non-trading days:")
for date in no_trading_days[:20]:
    stats = daily_log[date]
    print(f"  {date}: {stats['rows']:5d} rows, {stats['bids']:4d} bids, "
          f"{stats['asks']:4d} asks, {stats['trades']:4d} trades")

if len(no_trading_days) > 20:
    print(f"  ... and {len(no_trading_days)-20} more\n")

# Show all days for deeper analysis
print(f"\n{'='*80}")
print("All Days Summary")
print(f"{'='*80}")
with open('output/adnocgas_daily_log.txt', 'w') as f:
    f.write("Date       | Rows | Bids | Asks | Trades | Strategy Trades\n")
    f.write("-" * 70 + "\n")
    for date in sorted(daily_log.keys()):
        stats = daily_log[date]
        line = f"{date} | {stats['rows']:5d} | {stats['bids']:4d} | {stats['asks']:4d} | {stats['trades']:5d} | {stats['strategy_trades']:5d}\n"
        f.write(line)
        if stats['strategy_trades'] == 0:
            print(line.strip())

print(f"\nFull log saved to: output/adnocgas_daily_log.txt")
