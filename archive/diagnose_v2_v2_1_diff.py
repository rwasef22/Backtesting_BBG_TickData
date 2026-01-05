"""
Diagnose differences between V2 and V2.1 (50% threshold) trades
"""
import pandas as pd
from pathlib import Path

def main():
    print(f"\n{'='*80}")
    print(f"DIAGNOSTIC: V2 vs V2.1 Trade-by-Trade Analysis")
    print(f"{'='*80}\n")
    
    # Load data
    v2_df = pd.read_csv('output/comprehensive_sweep/v2_30s/EMAAR_trades.csv')
    v2_1_df = pd.read_csv('output/v2_1_validation/v2_1_threshold_50.0/EMAAR_trades.csv')
    
    print(f"V2 trades: {len(v2_df):,}")
    print(f"V2.1 trades: {len(v2_1_df):,}")
    print(f"Difference: {len(v2_1_df) - len(v2_df):,}\n")
    
    # Check first 20 trades
    print(f"{'='*80}")
    print(f"FIRST 20 TRADES COMPARISON")
    print(f"{'='*80}\n")
    
    for i in range(min(20, len(v2_df), len(v2_1_df))):
        v2_t = v2_df.iloc[i]
        v2_1_t = v2_1_df.iloc[i]
        
        matches = (
            v2_t['timestamp'] == v2_1_t['timestamp'] and
            v2_t['side'] == v2_1_t['side'] and
            abs(v2_t['fill_price'] - v2_1_t['fill_price']) < 0.001 and
            abs(v2_t['fill_qty'] - v2_1_t['fill_qty']) < 0.1
        )
        
        status = "✅" if matches else "❌"
        
        if not matches:
            print(f"Trade {i+1}: {status}")
            print(f"  V2:   {v2_t['timestamp']} {v2_t['side']:4s} {v2_t['fill_qty']:8.0f} @ {v2_t['fill_price']:.3f} PNL: {v2_t['realized_pnl']:10.2f}")
            print(f"  V2.1: {v2_1_t['timestamp']} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:8.0f} @ {v2_1_t['fill_price']:.3f} PNL: {v2_1_t['realized_pnl']:10.2f}")
    
    # Find where they diverge
    print(f"\n{'='*80}")
    print(f"FINDING DIVERGENCE POINT")
    print(f"{'='*80}\n")
    
    divergence_idx = None
    for i in range(min(len(v2_df), len(v2_1_df))):
        v2_t = v2_df.iloc[i]
        v2_1_t = v2_1_df.iloc[i]
        
        if (v2_t['timestamp'] != v2_1_t['timestamp'] or
            v2_t['side'] != v2_1_t['side'] or
            abs(v2_t['fill_qty'] - v2_1_t['fill_qty']) > 0.1):
            divergence_idx = i
            break
    
    if divergence_idx is not None:
        print(f"❌ Trades diverge at index {divergence_idx}")
        print(f"\nContext (trades {max(0, divergence_idx-2)} to {divergence_idx+2}):\n")
        
        for i in range(max(0, divergence_idx-2), min(divergence_idx+3, min(len(v2_df), len(v2_1_df)))):
            v2_t = v2_df.iloc[i]
            v2_1_t = v2_1_df.iloc[i]
            
            marker = " >>> " if i == divergence_idx else "     "
            print(f"{marker}Trade {i+1}:")
            print(f"     V2:   {v2_t['timestamp']} {v2_t['side']:4s} {v2_t['fill_qty']:8.0f} @ {v2_t['fill_price']:.3f}")
            print(f"     V2.1: {v2_1_t['timestamp']} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:8.0f} @ {v2_1_t['fill_price']:.3f}")
    else:
        print(f"✅ All overlapping trades match perfectly")
        print(f"   V2 has {len(v2_df) - len(v2_1_df)} extra trades after V2.1 ends")
    
    # Summary statistics comparison
    print(f"\n{'='*80}")
    print(f"STATISTICS COMPARISON")
    print(f"{'='*80}\n")
    
    v2_buy = (v2_df['side'] == 'buy').sum()
    v2_sell = (v2_df['side'] == 'sell').sum()
    v2_1_buy = (v2_1_df['side'] == 'buy').sum()
    v2_1_sell = (v2_1_df['side'] == 'sell').sum()
    
    print(f"Buy trades:  V2={v2_buy:,}  V2.1={v2_1_buy:,}  (diff: {v2_1_buy-v2_buy:+,})")
    print(f"Sell trades: V2={v2_sell:,}  V2.1={v2_1_sell:,}  (diff: {v2_1_sell-v2_sell:+,})")
    
    v2_total_pnl = v2_df['realized_pnl'].sum()
    v2_1_total_pnl = v2_1_df['realized_pnl'].sum()
    v2_avg_pnl = v2_df['realized_pnl'].mean()
    v2_1_avg_pnl = v2_1_df['realized_pnl'].mean()
    
    print(f"\nTotal P&L:   V2={v2_total_pnl:,.2f}  V2.1={v2_1_total_pnl:,.2f}  (diff: {v2_1_total_pnl-v2_total_pnl:+,.2f})")
    print(f"Avg P&L/trade: V2={v2_avg_pnl:.2f}  V2.1={v2_1_avg_pnl:.2f}  (diff: {v2_1_avg_pnl-v2_avg_pnl:+.2f})")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    import sys
    sys.exit(main())
