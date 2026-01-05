"""
Compare V2 vs V2.1 (50% stop-loss) validation results
"""
import pandas as pd
from pathlib import Path

def main():
    print(f"\n{'='*80}")
    print(f"V2.1 VALIDATION: Comparing V2 vs V2.1 (50% stop-loss)")
    print(f"{'='*80}\n")
    
    # Paths
    v2_path = Path('output/comprehensive_sweep/v2_30s/EMAAR_trades.csv')
    v2_1_50_path = Path('output/v2_1_validation/v2_1_threshold_50.0/EMAAR_trades.csv')
    
    if not v2_path.exists():
        print(f"❌ V2 results not found: {v2_path}")
        return 1
    
    if not v2_1_50_path.exists():
        print(f"❌ V2.1 (50%) results not found: {v2_1_50_path}")
        print(f"   Run the validation sweep first:")
        print(f"   python scripts/comprehensive_sweep.py --strategies v2_1 --sweep-param threshold --param-range 50 50 1 --sheet-names 'EMAAR UH Equity' --output-dir output/v2_1_validation --fresh")
        return 1
    
    # Load data
    print(f"📂 Loading V2 baseline results...")
    v2_df = pd.read_csv(v2_path)
    
    print(f"📂 Loading V2.1 (50% stop-loss) results...")
    v2_1_df = pd.read_csv(v2_1_50_path)
    
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}\n")
    
    # Calculate metrics
    v2_trades = len(v2_df)
    v2_pnl = v2_df['realized_pnl'].sum()
    v2_position = v2_df['position'].iloc[-1] if len(v2_df) > 0 else 0
    
    v2_1_trades = len(v2_1_df)
    v2_1_pnl = v2_1_df['realized_pnl'].sum()
    v2_1_position = v2_1_df['position'].iloc[-1] if len(v2_1_df) > 0 else 0
    
    print(f"V2 Baseline:")
    print(f"   Trades:   {v2_trades:,}")
    print(f"   P&L:      {v2_pnl:,.2f} AED")
    print(f"   Position: {v2_position}\n")
    
    print(f"V2.1 with 50% Stop-Loss:")
    print(f"   Trades:   {v2_1_trades:,}")
    print(f"   P&L:      {v2_1_pnl:,.2f} AED")
    print(f"   Position: {v2_1_position}\n")
    
    # Compare
    print(f"{'='*80}")
    print(f"VALIDATION")
    print(f"{'='*80}\n")
    
    all_match = True
    
    # Trade count
    if v2_trades == v2_1_trades:
        print(f"✅ Trade Count: {v2_trades:,} (MATCH)")
    else:
        diff = v2_1_trades - v2_trades
        print(f"❌ Trade Count: V2={v2_trades:,}, V2.1={v2_1_trades:,} (diff: {diff:+,})")
        all_match = False
    
    # P&L
    pnl_diff = abs(v2_1_pnl - v2_pnl)
    if pnl_diff < 1.0:  # Allow <1 AED tolerance for rounding
        print(f"✅ P&L: {v2_pnl:,.2f} AED (MATCH)")
    else:
        diff_aed = v2_1_pnl - v2_pnl
        diff_pct = (diff_aed / v2_pnl * 100) if v2_pnl != 0 else 0
        print(f"❌ P&L: V2={v2_pnl:,.2f}, V2.1={v2_1_pnl:,.2f} (diff: {diff_aed:+,.2f} AED, {diff_pct:+.2f}%)")
        all_match = False
    
    # Position
    if v2_position == v2_1_position:
        print(f"✅ Final Position: {v2_position} (MATCH)")
    else:
        print(f"❌ Final Position: V2={v2_position}, V2.1={v2_1_position}")
        all_match = False
    
    # Final result
    print(f"\n{'='*80}")
    if all_match:
        print(f"✅✅✅ VALIDATION PASSED ✅✅✅")
        print(f"\nV2.1 with 50% stop-loss produces IDENTICAL results to V2")
        print(f"This confirms the V2.1 implementation is working correctly")
        print(f"The stop-loss logic doesn't interfere when threshold is high\n")
        return 0
    else:
        print(f"❌❌❌ VALIDATION FAILED ❌❌❌")
        print(f"\nV2.1 should match V2 exactly with 50% stop-loss")
        print(f"Differences indicate a bug in the V2.1 implementation")
        print(f"Review the V2.1 strategy and handler code\n")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
