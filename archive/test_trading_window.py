"""Test strict trading window (10:00-14:45) for V2 strategy."""
from src.market_making_backtest import MarketMakingBacktest
from src.strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from src.config_loader import load_strategy_config
import pandas as pd

# Run backtest on EMAAR only
config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')
handler = create_v2_price_follow_qty_cooldown_handler(config)
backtest = MarketMakingBacktest()

print("Running V2 backtest on EMAAR with strict 10:00-14:45 window...")
results = backtest.run_streaming(
    'data/raw/TickData.xlsx', 
    handler=handler, 
    write_csv=False,
    sheet_names_filter=['EMAAR UH Equity']
)

# Analyze trades
trades = pd.DataFrame(results['EMAAR']['trades'])
if len(trades) > 0:
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])
    trades['time'] = trades['timestamp'].dt.time
    
    before_10 = trades[trades['time'] < pd.to_datetime('10:00').time()]
    after_1445 = trades[trades['time'] >= pd.to_datetime('14:45').time()]
    in_window = trades[(trades['time'] >= pd.to_datetime('10:00').time()) & 
                       (trades['time'] < pd.to_datetime('14:45').time())]
    
    print(f"\nResults:")
    print(f"  Total trades: {len(trades)}")
    print(f"  Before 10:00: {len(before_10)}")
    print(f"  After 14:45: {len(after_1445)}")
    print(f"  In window (10:00-14:45): {len(in_window)}")
    
    if len(before_10) > 0:
        print(f"\n❌ ERROR: {len(before_10)} trades before 10:00!")
        print(before_10[['timestamp', 'side', 'fill_qty']].head())
    else:
        print(f"\n✅ No trades before 10:00")
    
    if len(after_1445) > 0:
        print(f"\n❌ ERROR: {len(after_1445)} trades after 14:45!")
        print(after_1445[['timestamp', 'side', 'fill_qty']].head())
    else:
        print(f"\n✅ No trades after 14:45")
else:
    print("No trades generated!")
