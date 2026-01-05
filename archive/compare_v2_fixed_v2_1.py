"""
Compare V2 (with fix) vs V2.1 (50% threshold) - should be identical
"""
import pandas as pd

# Load results
v2_fixed = pd.read_csv('output/v2_fixed/v2_30s/EMAAR_trades.csv')
v2_1 = pd.read_csv('output/v2_1_validation/v2_1_threshold_50.0/EMAAR_trades.csv')

print("="*80)
print("V2 (FIXED) vs V2.1 (50% THRESHOLD) COMPARISON")
print("="*80)
print(f"\nV2 (fixed):        {len(v2_fixed):,} trades")
print(f"V2.1 (50% thresh): {len(v2_1):,} trades")
print(f"Difference:        {len(v2_1) - len(v2_fixed):,} trades")

# Check P&L
v2_pnl = v2_fixed['realized_pnl'].sum()
v2_1_pnl = v2_1['realized_pnl'].sum()
print(f"\nV2 (fixed) P&L:        {v2_pnl:,.2f} AED")
print(f"V2.1 (50% thresh) P&L: {v2_1_pnl:,.2f} AED")
print(f"Difference:            {v2_1_pnl - v2_pnl:,.2f} AED ({(v2_1_pnl - v2_pnl)/v2_pnl*100:+.2f}%)")

# Compare first 20 trades
print("\n" + "="*80)
print("FIRST 20 TRADES COMPARISON")
print("="*80 + "\n")

matches = 0
diffs = 0

for i in range(min(20, len(v2_fixed), len(v2_1))):
    v2_t = v2_fixed.iloc[i]
    v2_1_t = v2_1.iloc[i]
    
    match = (v2_t['timestamp'] == v2_1_t['timestamp'] and
             v2_t['side'] == v2_1_t['side'] and
             abs(v2_t['fill_price'] - v2_1_t['fill_price']) < 0.001 and
             v2_t['fill_qty'] == v2_1_t['fill_qty'])
    
    if match:
        matches += 1
        print(f"{i+1:2d}. MATCH: {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:5.0f} @ {v2_t['fill_price']:.3f}")
    else:
        diffs += 1
        print(f"{i+1:2d}. DIFF:")
        print(f"    V2:   {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:5.0f} @ {v2_t['fill_price']:.3f}")
        print(f"    V2.1: {v2_1_t['timestamp'][:19]} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:5.0f} @ {v2_1_t['fill_price']:.3f}")

print(f"\n{matches} matches, {diffs} differences in first 20 trades")

# Check if all trades match
if len(v2_fixed) == len(v2_1):
    all_match = True
    for i in range(len(v2_fixed)):
        v2_t = v2_fixed.iloc[i]
        v2_1_t = v2_1.iloc[i]
        
        if not (v2_t['timestamp'] == v2_1_t['timestamp'] and
                v2_t['side'] == v2_1_t['side'] and
                abs(v2_t['fill_price'] - v2_1_t['fill_price']) < 0.001 and
                v2_t['fill_qty'] == v2_1_t['fill_qty']):
            all_match = False
            break
    
    print("\n" + "="*80)
    if all_match:
        print("✅ VALIDATION PASSED: All trades match exactly!")
    else:
        print("❌ VALIDATION FAILED: Trade sequences differ")
        print(f"   First difference at trade #{i+1}")
    print("="*80)
else:
    print("\n" + "="*80)
    print("❌ VALIDATION FAILED: Different number of trades")
    print("="*80)
