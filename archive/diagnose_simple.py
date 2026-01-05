"""
Simple diagnosis of V2 vs V2.1 differences
"""
import pandas as pd

v2_df = pd.read_csv('output/comprehensive_sweep/v2_30s/EMAAR_trades.csv')
v2_1_df = pd.read_csv('output/v2_1_validation/v2_1_threshold_50.0/EMAAR_trades.csv')

print(f"V2 trades: {len(v2_df):,}")
print(f"V2.1 trades: {len(v2_1_df):,}")
print(f"Difference: {len(v2_1_df) - len(v2_df):,}\n")

print("First 15 trades:")
for i in range(min(15, len(v2_df), len(v2_1_df))):
    v2_t = v2_df.iloc[i]
    v2_1_t = v2_1_df.iloc[i]
    
    match = (v2_t['timestamp'] == v2_1_t['timestamp'] and
             v2_t['side'] == v2_1_t['side'] and
             abs(v2_t['fill_price'] - v2_1_t['fill_price']) < 0.001 and
             v2_t['fill_qty'] == v2_1_t['fill_qty'])
    
    if match:
        print(f"{i+1:2d}. MATCH: {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:5.0f} @ {v2_t['fill_price']:.3f}")
    else:
        print(f"{i+1:2d}. DIFF:")
        print(f"    V2:   {v2_t['timestamp'][:19]} {v2_t['side']:4s} {v2_t['fill_qty']:5.0f} @ {v2_t['fill_price']:.3f}")
        print(f"    V2.1: {v2_1_t['timestamp'][:19]} {v2_1_t['side']:4s} {v2_1_t['fill_qty']:5.0f} @ {v2_1_t['fill_price']:.3f}")
