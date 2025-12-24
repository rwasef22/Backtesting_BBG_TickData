#!/usr/bin/env python
"""Quick test of backtest with new opening auction fix."""
from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config

print('Initializing...')
mm_config = load_strategy_config('configs/mm_config.json')
mm_handler = create_mm_handler(config=mm_config)
backtest = MarketMakingBacktest()

print('Running backtest... this may take a minute')
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=mm_handler,
    only_trades=False,
)

print('\nBacktest complete!')
for security in sorted(results.keys()):
    data = results[security]
    position = data.get('position', 0)
    pnl = data.get('pnl', 0)
    trades = len(data.get('trades', []))
    print(f'{security}: Position={position}, P&L=${pnl:.2f}, Trades={trades}')
