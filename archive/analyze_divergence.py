"""
Analyze the divergence between V2 and V2.1 trades in detail
"""
import pandas as pd

v2 = pd.read_csv('output/v2_fixed/v2_30s/EMAAR_trades.csv')
v2_1 = pd.read_csv('output/v2_1_validation_fixed/v2_1_threshold_50.0/EMAAR_trades.csv')

print("="*80)
print("DIVERGENCE ANALYSIS")
print("="*80)

print(f"\nV2:   {len(v2):,} trades, {v2['realized_pnl'].sum():,.2f} AED")
print(f"V2.1: {len(v2_1):,} trades, {v2_1['realized_pnl'].sum():,.2f} AED")
print(f"Diff: {len(v2_1)-len(v2):,} trades, {v2_1['realized_pnl'].sum()-v2['realized_pnl'].sum():,.2f} AED")

# Find first divergence
print("\n" + "="*80)
print("FINDING FIRST DIVERGENCE POINT")
print("="*80)

for i in range(min(len(v2), len(v2_1))):
    v2_t = v2.iloc[i]
    v2_1_t = v2_1.iloc[i]
    
    match = (v2_t['timestamp'] == v2_1_t['timestamp'] and
             v2_t['side'] == v2_1_t['side'] and
             abs(v2_t['fill_price'] - v2_1_t['fill_price']) < 0.001 and
             v2_t['fill_qty'] == v2_1_t['fill_qty'])
    
    if not match:
        print(f"\nFirst divergence at trade #{i+1}:")
        print(f"  V2:   {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:6.0f} @ {v2_t['fill_price']:.3f} -> pos={v2_t['position']:6.0f}")
        print(f"  V2.1: {v2_1_t['timestamp'][:19]} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:6.0f} @ {v2_1_t['fill_price']:.3f} -> pos={v2_1_t['position']:6.0f}")
        
        # Show 5 trades before and 5 after
        print("\nContext (5 trades before):")
        for j in range(max(0, i-5), i):
            v2_t = v2.iloc[j]
            v2_1_t = v2_1.iloc[j]
            print(f"  {j+1:3d}. V2:   {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:6.0f} @ {v2_t['fill_price']:.3f} -> pos={v2_t['position']:6.0f}")
            print(f"       V2.1: {v2_1_t['timestamp'][:19]} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:6.0f} @ {v2_1_t['fill_price']:.3f} -> pos={v2_1_t['position']:6.0f}")
        
        print("\nDivergence point:")
        print(f"  {i+1:3d}. V2:   {v2.iloc[i]['timestamp'][:19]} {v2.iloc[i]['side']:4s} {v2.iloc[i]['fill_qty']:6.0f} @ {v2.iloc[i]['fill_price']:.3f} -> pos={v2.iloc[i]['position']:6.0f}")
        print(f"       V2.1: {v2_1.iloc[i]['timestamp'][:19]} {v2_1.iloc[i]['side']:4s} {v2_1.iloc[i]['fill_qty']:6.0f} @ {v2_1.iloc[i]['fill_price']:.3f} -> pos={v2_1.iloc[i]['position']:6.0f}")
        
        print("\nAfter divergence (next 5):")
        for j in range(i+1, min(i+6, len(v2), len(v2_1))):
            v2_t = v2.iloc[j]
            v2_1_t = v2_1.iloc[j]
            print(f"  {j+1:3d}. V2:   {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:6.0f} @ {v2_t['fill_price']:.3f} -> pos={v2_t['position']:6.0f}")
            print(f"       V2.1: {v2_1_t['timestamp'][:19]} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:6.0f} @ {v2_1_t['fill_price']:.3f} -> pos={v2_1_t['position']:6.0f}")
        
        break

# Check if V2.1 has extra trades at same timestamp
print("\n" + "="*80)
print("EXTRA TRADES ANALYSIS")
print("="*80)

# Count trades by timestamp for the divergence area
v2_ts = v2[v2['timestamp'].str.startswith('2025-04-14 10:17:37')]
v2_1_ts = v2_1[v2_1['timestamp'].str.startswith('2025-04-14 10:17:37')]

print(f"\nTrades at 2025-04-14 10:17:37:")
print(f"  V2:   {len(v2_ts)} trades")
print(f"  V2.1: {len(v2_1_ts)} trades")
print(f"  Difference: {len(v2_1_ts) - len(v2_ts)} extra trade(s) in V2.1")

if len(v2_1_ts) > len(v2_ts):
    print("\nV2.1 has EXTRA trades at this timestamp. Showing all trades:")
    print("\nV2 trades:")
    for idx, t in v2_ts.iterrows():
        print(f"  {t['side']:4s} {t['fill_qty']:6.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")
    
    print("\nV2.1 trades:")
    for idx, t in v2_1_ts.iterrows():
        print(f"  {t['side']:4s} {t['fill_qty']:6.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")
