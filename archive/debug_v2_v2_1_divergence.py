"""
Debug why V2 and V2.1 generate different trades
Focus on the first divergence point at 10:17:37
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime
import pandas as pd
from strategies.v2_price_follow_qty_cooldown.handler import create_v2_price_follow_qty_cooldown_handler
from strategies.v2_1_stop_loss.handler import create_v2_1_stop_loss_handler
from orderbook import OrderBook
from data_loader import stream_sheets

# Load first chunk only
print("Loading data...")
sheet_name, df = next(stream_sheets('data/raw/TickData.xlsx', 
                                     sheet_names_filter=['EMAAR UH Equity'],
                                     chunk_size=100000))

# Preprocess (already has timestamp in 'Dates' column)
df = df.rename(columns={'Dates': 'timestamp', 'Type': 'type', 'Price': 'price', 'Size': 'volume'})
df['type'] = df['type'].str.lower()
df = df[['timestamp', 'type', 'price', 'volume']].copy()

print(f"Loaded {len(df):,} rows from {sheet_name}")

# Create handlers
v2_handler = create_v2_price_follow_qty_cooldown_handler()
v2_1_handler = create_v2_1_stop_loss_handler({'EMAAR': {'stop_loss_threshold_pct': 50.0}})

# Create separate orderbooks
v2_orderbook = OrderBook()
v2_1_orderbook = OrderBook()

v2_state = {}
v2_1_state = {}

print("\n" + "="*80)
print("RUNNING BOTH STRATEGIES IN PARALLEL")
print("="*80)

# Process row by row until divergence
trade_count_v2 = 0
trade_count_v2_1 = 0
diverged = False

for idx, row in df.iterrows():
    # Process in V2
    v2_state = v2_handler('EMAAR', pd.DataFrame([row]), v2_orderbook, v2_state)
    
    # Process in V2.1
    v2_1_state = v2_1_handler('EMAAR', pd.DataFrame([row]), v2_1_orderbook, v2_1_state)
    
    # Check for new trades
    new_v2_trades = len(v2_state.get('trades', [])) - trade_count_v2
    new_v2_1_trades = len(v2_1_state.get('trades', [])) - trade_count_v2_1
    
    # Show trades around the critical time
    if row['timestamp'] >= datetime(2025, 4, 14, 10, 17, 36) and row['timestamp'] <= datetime(2025, 4, 14, 10, 17, 38):
        if new_v2_trades > 0 or new_v2_1_trades > 0:
            print(f"\n[{row['timestamp']}] Market {row['type'].upper():5s} @ {row['price']:.3f} vol={row['volume']}")
            
            if new_v2_trades > 0:
                for t in v2_state['trades'][trade_count_v2:]:
                    print(f"  V2:   {t['side'].upper():4s} {t['fill_qty']:5.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")
            
            if new_v2_1_trades > 0:
                for t in v2_1_state['trades'][trade_count_v2_1:]:
                    print(f"  V2.1: {t['side'].upper():4s} {t['fill_qty']:5.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")
            
            # Check if positions diverged
            v2_pos = v2_state.get('position', 0)
            v2_1_pos = v2_1_state.get('position', 0)
            if v2_pos != v2_1_pos:
                print(f"  WARNING: POSITIONS DIVERGED: V2={v2_pos:,} vs V2.1={v2_1_pos:,}")
                diverged = True
    
    trade_count_v2 = len(v2_state.get('trades', []))
    trade_count_v2_1 = len(v2_1_state.get('trades', []))
    
    # Stop after we pass the critical time and have enough trades
    if row['timestamp'] > datetime(2025, 4, 14, 10, 17, 38) and trade_count_v2 >= 7:
        break

# Final comparison
print(f"\n{'='*80}")
print("FINAL STATE COMPARISON")
print(f"{'='*80}")
print(f"V2 trades:   {trade_count_v2}")
print(f"V2.1 trades: {trade_count_v2_1}")
print(f"Difference:  {trade_count_v2_1 - trade_count_v2}")

print(f"\nV2 position:   {v2_state.get('position', 0):,}")
print(f"V2.1 position: {v2_1_state.get('position', 0):,}")

print(f"\nV2 P&L:   {v2_state.get('pnl', 0):,.2f} AED")
print(f"V2.1 P&L: {v2_1_state.get('pnl', 0):,.2f} AED")

# Show all trades up to this point
print(f"\n{'='*80}")
print("ALL TRADES COMPARISON")
print(f"{'='*80}")

print("\nV2 TRADES:")
for i, t in enumerate(v2_state.get('trades', [])[:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:5.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")

print("\nV2.1 TRADES:")
for i, t in enumerate(v2_1_state.get('trades', [])[:10]):
    print(f"{i+1:2d}. {t['timestamp']} {t['side']:4s} {t['fill_qty']:5.0f} @ {t['fill_price']:.3f} -> pos={t['position']:6.0f}")
