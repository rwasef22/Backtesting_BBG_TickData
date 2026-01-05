"""
Quick V2.1 Validation Test using existing comprehensive sweep results

This compares V2 @ 30s with V2.1 @ 30s with 50% threshold
by running just V2.1 and comparing to the existing V2 results.
"""
import sys
import os
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler

def main():
    print(f"\n{'='*80}")
    print(f"QUICK V2.1 VALIDATION TEST")
    print(f"{'='*80}")
    print(f"Comparing: V2.1 (50% stop-loss) vs existing V2 results")
    print(f"Security: EMAAR UH Equity")
    print(f"Interval: 30 seconds")
    print(f"{'='*80}\n")
    
    # Check if V2 results exist
    v2_results_path = Path('output/comprehensive_sweep/v2_30s/EMAAR_trades.csv')
    
    if not v2_results_path.exists():
        print(f"❌ ERROR: V2 results not found at {v2_results_path}")
        print(f"   Please run V2 first:")
        print(f"   python scripts/comprehensive_sweep.py --strategies v2 --intervals 30 --max-sheets 3")
        return 1
    
    # Load V2 results
    print(f"📂 Loading V2 results from {v2_results_path}...")
    v2_df = pd.read_csv(v2_results_path)
    v2_trades = len(v2_df)
    v2_pnl = v2_df['realized_pnl'].sum()
    v2_final_position = v2_df['position'].iloc[-1] if len(v2_df) > 0 else 0
    
    print(f"✅ V2 Results:")
    print(f"   Trades: {v2_trades:,}")
    print(f"   P&L: {v2_pnl:,.2f} AED")
    print(f"   Final Position: {v2_final_position}")
    
    # Run V2.1 with 50% stop-loss
    print(f"\n🟣 Running V2.1 with 50% stop-loss...")
    
    data_path = 'data/raw/TickData.xlsx'
    security = 'EMAAR UH Equity'
    interval_sec = 30
    stop_loss_threshold = 50.0
    
    # Load config
    v2_config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')
    
    # Create V2.1 config
    v2_1_run_config = {}
    for sec, cfg in v2_config.items():
        v2_1_run_config[sec] = cfg.copy()
        v2_1_run_config[sec]['refill_interval_sec'] = interval_sec
        v2_1_run_config[sec]['stop_loss_threshold_pct'] = stop_loss_threshold
    
    # Run V2.1
    v2_1_handler = create_v2_1_stop_loss_handler(config=v2_1_run_config)
    backtest_v2_1 = MarketMakingBacktest()
    
    try:
        v2_1_results = backtest_v2_1.run_streaming(
            file_path=data_path,
            handler=v2_1_handler,
            max_sheets=None,
            chunk_size=100000,
            sheet_names_filter=[security]
        )
    except KeyboardInterrupt:
        print(f"\n⚠️  Interrupted by user")
        return 1
    
    # Extract V2.1 results
    v2_1_data = v2_1_results.get(security, {})
    v2_1_trades_list = v2_1_data.get('trades', [])
    v2_1_trades = len(v2_1_trades_list)
    v2_1_pnl = v2_1_data.get('pnl', 0)
    v2_1_position = v2_1_data.get('position', 0)
    
    print(f"✅ V2.1 Results:")
    print(f"   Trades: {v2_1_trades:,}")
    print(f"   P&L: {v2_1_pnl:,.2f} AED")
    print(f"   Final Position: {v2_1_position}")
    
    # Check for stop-loss triggers
    stop_loss_count = sum(1 for t in v2_1_trades_list if t.get('stop_loss_triggered', False))
    print(f"   Stop-Loss Triggers: {stop_loss_count}")
    
    # Compare
    print(f"\n{'='*80}")
    print(f"COMPARISON")
    print(f"{'='*80}\n")
    
    differences = []
    all_match = True
    
    # Trade count
    if v2_trades == v2_1_trades:
        print(f"✅ Trade Count: {v2_trades:,} (match)")
    else:
        print(f"❌ Trade Count: V2={v2_trades:,}, V2.1={v2_1_trades:,} (diff: {v2_1_trades - v2_trades:+,})")
        differences.append('trade_count')
        all_match = False
    
    # P&L
    pnl_diff = abs(v2_1_pnl - v2_pnl)
    if pnl_diff < 0.01:
        print(f"✅ P&L: {v2_pnl:,.2f} AED (match)")
    else:
        print(f"❌ P&L: V2={v2_pnl:,.2f}, V2.1={v2_1_pnl:,.2f} (diff: {v2_1_pnl - v2_pnl:+,.2f})")
        differences.append('pnl')
        all_match = False
    
    # Position
    if v2_final_position == v2_1_position:
        print(f"✅ Final Position: {v2_final_position} (match)")
    else:
        print(f"❌ Final Position: V2={v2_final_position}, V2.1={v2_1_position}")
        differences.append('position')
        all_match = False
    
    # Stop-loss triggers
    if stop_loss_count == 0:
        print(f"✅ No stop-loss triggers (as expected)")
    else:
        print(f"❌ {stop_loss_count} stop-loss triggers found (should be 0 with 50% threshold)")
        differences.append('stop_loss_triggers')
        all_match = False
    
    # Final verdict
    print(f"\n{'='*80}")
    print(f"VALIDATION RESULT")
    print(f"{'='*80}\n")
    
    if all_match:
        print(f"✅ VALIDATION PASSED")
        print(f"   V2.1 with 50% stop-loss matches V2 exactly")
        print(f"   The V2.1 implementation is working correctly\n")
        return 0
    else:
        print(f"❌ VALIDATION FAILED")
        print(f"   Differences found in: {', '.join(differences)}")
        print(f"   V2.1 should match V2 exactly with 50% stop-loss")
        print(f"   Investigation needed in V2.1 strategy implementation\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
