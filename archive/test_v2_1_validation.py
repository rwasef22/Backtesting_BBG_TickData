"""
Test V2.1 Stop Loss Strategy Validation

This script validates that V2.1 with a 50% stop-loss threshold produces
identical results to V2 (since 50% stop-loss should never trigger).

Any differences indicate a bug in the V2.1 implementation.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.market_making_backtest import MarketMakingBacktest
from src.config_loader import load_strategy_config
from src.strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from src.strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler

def compare_results(v2_results, v2_1_results, security):
    """Compare V2 and V2.1 results in detail."""
    print(f"\n{'='*80}")
    print(f"COMPARING {security}")
    print(f"{'='*80}")
    
    v2_data = v2_results.get(security, {})
    v2_1_data = v2_1_results.get(security, {})
    
    v2_trades = v2_data.get('trades', [])
    v2_1_trades = v2_1_data.get('trades', [])
    
    v2_pnl = v2_data.get('pnl', 0)
    v2_1_pnl = v2_1_data.get('pnl', 0)
    
    v2_position = v2_data.get('position', 0)
    v2_1_position = v2_1_data.get('position', 0)
    
    print(f"\n📊 Summary Metrics:")
    print(f"  V2   - Trades: {len(v2_trades):,}  |  P&L: {v2_pnl:,.2f} AED  |  Position: {v2_position}")
    print(f"  V2.1 - Trades: {len(v2_1_trades):,}  |  P&L: {v2_1_pnl:,.2f} AED  |  Position: {v2_1_position}")
    
    # Check for differences
    differences = []
    
    if len(v2_trades) != len(v2_1_trades):
        diff = len(v2_1_trades) - len(v2_trades)
        differences.append(f"❌ Trade count mismatch: V2={len(v2_trades)}, V2.1={len(v2_1_trades)} (diff: {diff:+d})")
    else:
        differences.append(f"✅ Trade count matches: {len(v2_trades):,}")
    
    pnl_diff = abs(v2_1_pnl - v2_pnl)
    if pnl_diff > 0.01:  # Allow 1 fils tolerance for rounding
        differences.append(f"❌ P&L mismatch: V2={v2_pnl:,.2f}, V2.1={v2_1_pnl:,.2f} (diff: {v2_1_pnl - v2_pnl:+,.2f})")
    else:
        differences.append(f"✅ P&L matches: {v2_pnl:,.2f} AED")
    
    if v2_position != v2_1_position:
        differences.append(f"❌ Final position mismatch: V2={v2_position}, V2.1={v2_1_position}")
    else:
        differences.append(f"✅ Final position matches: {v2_position}")
    
    print(f"\n🔍 Validation Results:")
    for diff in differences:
        print(f"  {diff}")
    
    # Detailed trade-by-trade comparison if counts match
    if len(v2_trades) == len(v2_1_trades) and len(v2_trades) > 0:
        print(f"\n🔬 Trade-by-Trade Analysis (first 10 trades):")
        mismatches = []
        
        for i in range(min(10, len(v2_trades))):
            v2_t = v2_trades[i]
            v2_1_t = v2_1_trades[i]
            
            # Check key fields
            fields_match = True
            field_diffs = []
            
            if v2_t['side'] != v2_1_t['side']:
                fields_match = False
                field_diffs.append(f"side: {v2_t['side']} vs {v2_1_t['side']}")
            
            if v2_t['fill_qty'] != v2_1_t['fill_qty']:
                fields_match = False
                field_diffs.append(f"qty: {v2_t['fill_qty']} vs {v2_1_t['fill_qty']}")
            
            if abs(v2_t['fill_price'] - v2_1_t['fill_price']) > 0.001:
                fields_match = False
                field_diffs.append(f"price: {v2_t['fill_price']:.3f} vs {v2_1_t['fill_price']:.3f}")
            
            if abs(v2_t['realized_pnl'] - v2_1_t['realized_pnl']) > 0.01:
                fields_match = False
                field_diffs.append(f"pnl: {v2_t['realized_pnl']:.2f} vs {v2_1_t['realized_pnl']:.2f}")
            
            if not fields_match:
                mismatches.append((i, field_diffs))
                print(f"  Trade {i+1}: ❌ MISMATCH - {', '.join(field_diffs)}")
            else:
                print(f"  Trade {i+1}: ✅ Match")
        
        if len(mismatches) > 0:
            print(f"\n  ⚠️  Found {len(mismatches)} mismatching trades in first 10")
        else:
            print(f"\n  ✅ All first 10 trades match perfectly")
        
        # Check for stop-loss triggers (there should be NONE with 50% threshold)
        stop_loss_count = sum(1 for t in v2_1_trades if t.get('stop_loss_triggered', False))
        if stop_loss_count > 0:
            print(f"\n  ❌ CRITICAL: {stop_loss_count} stop-loss triggers found (should be 0 with 50% threshold)!")
            differences.append(f"❌ Unexpected stop-loss triggers: {stop_loss_count}")
        else:
            print(f"\n  ✅ No stop-loss triggers (as expected)")
            differences.append(f"✅ No stop-loss triggers")
    
    # Overall validation result
    has_errors = any('❌' in d for d in differences)
    
    print(f"\n{'='*80}")
    if has_errors:
        print(f"❌ VALIDATION FAILED - V2.1 does NOT match V2")
        print(f"{'='*80}")
        return False
    else:
        print(f"✅ VALIDATION PASSED - V2.1 matches V2 perfectly")
        print(f"{'='*80}")
        return True


def main():
    print(f"\n{'='*80}")
    print(f"V2.1 VALIDATION TEST")
    print(f"{'='*80}")
    print(f"Testing: V2.1 with 50% stop-loss should match V2 exactly")
    print(f"Security: EMAAR UH Equity")
    print(f"Interval: 30 seconds")
    print(f"{'='*80}\n")
    
    # Configuration
    data_path = 'data/raw/TickData.xlsx'
    security = 'EMAAR UH Equity'
    interval_sec = 30
    stop_loss_threshold = 50.0  # 50% - should never trigger
    
    # Load base config
    v2_config = load_strategy_config('configs/v2_price_follow_qty_cooldown_config.json')
    
    # Create V2 config
    v2_run_config = {}
    for sec, cfg in v2_config.items():
        v2_run_config[sec] = cfg.copy()
        v2_run_config[sec]['refill_interval_sec'] = interval_sec
    
    # Create V2.1 config (same as V2 + stop-loss)
    v2_1_run_config = {}
    for sec, cfg in v2_config.items():
        v2_1_run_config[sec] = cfg.copy()
        v2_1_run_config[sec]['refill_interval_sec'] = interval_sec
        v2_1_run_config[sec]['stop_loss_threshold_pct'] = stop_loss_threshold
    
    # Run V2
    print(f"🔵 Running V2 baseline...")
    v2_handler = create_v2_price_follow_qty_cooldown_handler(config=v2_run_config)
    backtest_v2 = MarketMakingBacktest()
    v2_results = backtest_v2.run_streaming(
        file_path=data_path,
        handler=v2_handler,
        max_sheets=None,
        chunk_size=100000,
        sheet_names_filter=[security]
    )
    print(f"✅ V2 completed")
    
    # Run V2.1
    print(f"\n🟣 Running V2.1 with {stop_loss_threshold}% stop-loss...")
    v2_1_handler = create_v2_1_stop_loss_handler(config=v2_1_run_config)
    backtest_v2_1 = MarketMakingBacktest()
    v2_1_results = backtest_v2_1.run_streaming(
        file_path=data_path,
        handler=v2_1_handler,
        max_sheets=None,
        chunk_size=100000,
        sheet_names_filter=[security]
    )
    print(f"✅ V2.1 completed")
    
    # Compare results
    validation_passed = compare_results(v2_results, v2_1_results, security)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"FINAL RESULT")
    print(f"{'='*80}")
    if validation_passed:
        print(f"✅ V2.1 implementation is CORRECT")
        print(f"   With 50% stop-loss, V2.1 produces identical results to V2")
        print(f"   This confirms the stop-loss logic doesn't interfere when not triggered")
    else:
        print(f"❌ V2.1 implementation has ISSUES")
        print(f"   V2.1 should match V2 exactly with 50% stop-loss")
        print(f"   Review the differences above and fix the V2.1 strategy")
    print(f"{'='*80}\n")
    
    return 0 if validation_passed else 1


if __name__ == '__main__':
    sys.exit(main())
