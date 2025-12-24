#!/usr/bin/env python
"""Generate plots and save CSV with per-side quoting."""
import sys
import traceback
from pathlib import Path

output_file = Path('output/run_log.txt')
output_file.parent.mkdir(parents=True, exist_ok=True)

try:
    with open(output_file, 'w') as log:
        log.write('Starting plot generation...\n')
        log.flush()
        
        sys.path.insert(0, str(Path('.').resolve()))
        log.write('Path configured\n')
        log.flush()
        
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from src.market_making_backtest import MarketMakingBacktest
        from src.mm_handler import create_mm_handler
        from src.config_loader import load_strategy_config
        
        log.write('Imports successful\n')
        log.flush()
        
        cfg = load_strategy_config('configs/mm_config.json')
        log.write(f'Config loaded: {list(cfg.keys())}\n')
        log.flush()
        
        handler = create_mm_handler(config=cfg)
        log.write('Handler created\n')
        log.flush()
        
        backtest = MarketMakingBacktest()
        log.write('Backtest initialized\n')
        log.flush()
        
        results = backtest.run_streaming(
            file_path='data/raw/TickData.xlsx',
            handler=handler,
            max_sheets=None,
            only_trades=False
        )
        
        log.write('Backtest complete\n')
        log.flush()
        
        sec_key = 'EMAAR'
        state = results[sec_key]
        trades = state.get('trades', [])
        
        log.write(f'Trades: {len(trades)}\n')
        log.flush()
        
        if trades:
            trade_df = pd.DataFrame(trades)
            trade_df = trade_df.sort_values('timestamp').reset_index(drop=True)
            trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])
            
            csv_path = Path('output/emaar_5min_trades_timeseries.csv')
            trade_df[['timestamp','position','pnl']].to_csv(csv_path, index=False)
            log.write(f'CSV saved to {csv_path}\n')
            log.flush()
            
            fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
            axes[0].plot(trade_df['timestamp'], trade_df['position'], color='tab:blue')
            axes[0].set_title('EMAAR - Inventory vs Time (5-min refill, per-side quoting)')
            axes[0].set_ylabel('Position (shares)')
            axes[0].grid(True, linestyle='--', alpha=0.3)
            
            axes[1].plot(trade_df['timestamp'], trade_df['pnl'], color='tab:green')
            axes[1].set_title('EMAAR - P&L vs Time (realized)')
            axes[1].set_ylabel('P&L (local currency)')
            axes[1].set_xlabel('Time')
            axes[1].grid(True, linestyle='--', alpha=0.3)
            
            fig.autofmt_xdate()
            
            img_path = Path('output/emaar_5min_inventory_pnl.png')
            plt.tight_layout()
            plt.savefig(img_path, dpi=144)
            log.write(f'Plot saved to {img_path}\n')
            log.flush()
        
        log.write('DONE!\n')
        
except Exception as e:
    with open(output_file, 'a') as log:
        log.write(f'ERROR: {e}\n')
        log.write(traceback.format_exc())
