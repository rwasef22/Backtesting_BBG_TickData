"""
Direct CSV Comparison: V2 vs V2.1 (30s interval)

This compares the existing V2 and V2.1 results from the comprehensive sweep
without running new backtests.
"""
import pandas as pd
from pathlib import Path

def main():
    print(f"\n{'='*80}")
    print(f"V2 vs V2.1 COMPARISON (from existing results)")
    print(f"{'='*80}")
    print(f"Security: EMAAR")
    print(f"Interval: 30 seconds")
    print(f"{'='*80}\n")
    
    # Paths
    v2_path = Path('output/comprehensive_sweep/v2_30s/EMAAR_trades.csv')
    v2_1_path = Path('output/comprehensive_sweep/v2_1_30s/EMAAR_trades.csv')
    
    # Check files exist
    if not v2_path.exists():
        print(f"❌ V2 results not found: {v2_path}")
        return 1
    
    if not v2_1_path.exists():
        print(f"❌ V2.1 results not found: {v2_1_path}")
        print(f"   Note: V2.1 @ 30s has 2% stop-loss, not 50%")
        print(f"   To validate V2.1 properly, we need to run it with 50% stop-loss")
        return 1
    
    # Load data
    print(f"📂 Loading results...")
    v2_df = pd.read_csv(v2_path)
    v2_1_df = pd.read_csv(v2_1_path)
    
    print(f"✅ Loaded V2: {len(v2_df):,} trades")
    print(f"✅ Loaded V2.1: {len(v2_1_df):,} trades\n")
    
    # Calculate metrics
    print(f"{'='*80}")
    print(f"METRICS COMPARISON")
    print(f"{'='*80}\n")
    
    # V2 metrics
    v2_trades = len(v2_df)
    v2_pnl = v2_df['realized_pnl'].sum()
    v2_position = v2_df['position'].iloc[-1] if len(v2_df) > 0 else 0
    v2_volume = (v2_df['fill_price'] * v2_df['fill_qty']).sum()
    
    # V2.1 metrics
    v2_1_trades = len(v2_1_df)
    v2_1_pnl = v2_1_df['realized_pnl'].sum()
    v2_1_position = v2_1_df['position'].iloc[-1] if len(v2_1_df) > 0 else 0
    v2_1_volume = (v2_1_df['fill_price'] * v2_1_df['fill_qty']).sum()
    
    # Check for stop-loss triggers in V2.1
    v2_1_stop_loss_count = v2_1_df['stop_loss_triggered'].sum() if 'stop_loss_triggered' in v2_1_df.columns else 0
    
    print(f"📊 V2 (Baseline):")
    print(f"   Trades:     {v2_trades:,}")
    print(f"   P&L:        {v2_pnl:,.2f} AED")
    print(f"   Position:   {v2_position}")
    print(f"   Volume:     {v2_volume:,.0f} AED\n")
    
    print(f"📊 V2.1 (2% Stop-Loss):")
    print(f"   Trades:     {v2_1_trades:,}")
    print(f"   P&L:        {v2_1_pnl:,.2f} AED")
    print(f"   Position:   {v2_1_position}")
    print(f"   Volume:     {v2_1_volume:,.0f} AED")
    print(f"   Stop-Loss:  {v2_1_stop_loss_count:,} triggers\n")
    
    # Differences
    print(f"{'='*80}")
    print(f"DIFFERENCES")
    print(f"{'='*80}\n")
    
    trade_diff = v2_1_trades - v2_trades
    trade_pct = (trade_diff / v2_trades * 100) if v2_trades > 0 else 0
    print(f"Trades:     {trade_diff:+,} ({trade_pct:+.2f}%)")
    
    pnl_diff = v2_1_pnl - v2_pnl
    pnl_pct = (pnl_diff / v2_pnl * 100) if v2_pnl != 0 else 0
    print(f"P&L:        {pnl_diff:+,.2f} AED ({pnl_pct:+.2f}%)")
    
    pos_diff = v2_1_position - v2_position
    print(f"Position:   {pos_diff:+,}")
    
    vol_diff = v2_1_volume - v2_volume
    vol_pct = (vol_diff / v2_volume * 100) if v2_volume != 0 else 0
    print(f"Volume:     {vol_diff:+,.0f} AED ({vol_pct:+.2f}%)\n")
    
    # Analysis
    print(f"{'='*80}")
    print(f"ANALYSIS")
    print(f"{'='*80}\n")
    
    print(f"📝 Note: This comparison is between:")
    print(f"   - V2: No stop-loss")
    print(f"   - V2.1: 2% stop-loss threshold")
    print(f"\n💡 To validate V2.1 implementation correctness:")
    print(f"   We need to run V2.1 with 50% stop-loss (should match V2 exactly)")
    print(f"   Current 2% stop-loss is expected to show differences\n")
    
    if v2_1_stop_loss_count > 0:
        print(f"✅ V2.1 stop-loss IS active ({v2_1_stop_loss_count:,} triggers)")
        print(f"   This explains why P&L is lower than V2")
    else:
        print(f"⚠️  V2.1 stop-loss has 0 triggers")
        print(f"   Either the 2% threshold never triggered, or tracking is missing")
    
    print(f"\n{'='*80}\n")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
