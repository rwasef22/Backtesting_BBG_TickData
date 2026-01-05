"""
Debug V2.1 to see if stop-loss is triggering with 50% threshold
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler

# Monkey-patch the handler to add debug output
from src.strategies.v2_1_stop_loss import handler as v2_1_handler

original_on_market_event = v2_1_handler.V2_1StopLossHandler.on_market_event

def debug_on_market_event(self, security, event_type, orderbook, timestamp):
    result = original_on_market_event(self, security, event_type, orderbook, timestamp)
    
    # Check if stop-loss is pending
    strategy = self.strategy
    if hasattr(strategy, 'stop_loss_pending') and security in strategy.stop_loss_pending:
        if strategy.stop_loss_pending[security] is not None:
            pending = strategy.stop_loss_pending[security]
            print(f"⚠️  Stop-loss PENDING at {timestamp}: {security} {pending['side']} {pending['remaining']}")
    
    return result

v2_1_handler.V2_1StopLossHandler.on_market_event = debug_on_market_event

def main():
    print("\n" + "="*80)
    print("DEBUG V2.1 STOP-LOSS WITH 50% THRESHOLD")
    print("="*80 + "\n")
    
    data_path = 'data/raw/TickData.xlsx'
    security = 'EMAAR UH Equity'
    interval_sec = 30
    stop_loss_threshold = 50.0
    
    # Load config
    v2_config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')
    
    # Create V2.1 config
    config = {}
    for sec, cfg in v2_config.items():
        config[sec] = cfg.copy()
        config[sec]['refill_interval_sec'] = interval_sec
        config[sec]['stop_loss_threshold_pct'] = stop_loss_threshold
    
    print(f"Running V2.1 with {stop_loss_threshold}% stop-loss on {security}")
    print(f"Watching for stop-loss triggers...\n")
    
    # Run backtest
    handler = create_v2_1_stop_loss_handler(config=config)
    backtest = MarketMakingBacktest()
    
    results = backtest.run_streaming(
        file_path=data_path,
        handler=handler,
        max_sheets=1,  # Just first chunk for quick debug
        chunk_size=100000,
        sheet_names_filter=[security]
    )
    
    data = results.get(security, {})
    trades = data.get('trades', [])
    
    print(f"\n" + "="*80)
    print(f"RESULTS")
    print("="*80)
    print(f"Trades: {len(trades):,}")
    print(f"P&L: {data.get('pnl', 0):,.2f} AED")
    
    # Check for stop-loss triggers in strategy state
    if hasattr(handler.strategy, 'stop_loss_pending'):
        print(f"\nFinal stop_loss_pending state:")
        for sec, pending in handler.strategy.stop_loss_pending.items():
            if pending is not None:
                print(f"  {sec}: {pending}")
            else:
                print(f"  {sec}: None")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
