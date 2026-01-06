"""
Calculate median auction volume and recommended order notional for each security.

This script:
1. Loads parquet data for each security
2. Filters for trades between 14:55 and 15:00 (closing auction)
3. Calculates daily auction volume (sum per day)
4. Computes median daily volume and price
5. Recommends order_notional as 20% of median daily auction notional
"""

import pandas as pd
import os
import json

parquet_dir = 'data/parquet'
results = []

for f in os.listdir(parquet_dir):
    if f.endswith('.parquet'):
        security = f.replace('.parquet', '')
        df = pd.read_parquet(os.path.join(parquet_dir, f))
        
        # Filter for trades between 14:55 and 15:00
        auction_trades = df[(df['type'] == 'TRADE') & 
                           (df['timestamp'].dt.time >= pd.Timestamp('14:55:00').time()) &
                           (df['timestamp'].dt.time < pd.Timestamp('15:00:00').time())].copy()
        
        if len(auction_trades) == 0:
            print(f"WARNING: No auction trades found for {security}")
            continue
        
        # Calculate daily auction volume (sum of volume per day)
        auction_trades['date'] = auction_trades['timestamp'].dt.date
        daily_volume = auction_trades.groupby('date').agg({
            'volume': 'sum',
            'price': 'mean'  # Average price for the day
        }).reset_index()
        
        # Calculate median daily volume and median price
        median_volume = daily_volume['volume'].median()
        median_price = daily_volume['price'].median()
        
        # Calculate notional (volume * price) and 20% of it
        median_notional = median_volume * median_price
        order_notional = int(median_notional * 0.20)
        
        results.append({
            'security': security,
            'median_auction_volume': int(median_volume),
            'median_price': round(median_price, 2),
            'median_notional': int(median_notional),
            'order_notional_20pct': order_notional
        })

# Sort and display
results_df = pd.DataFrame(results).sort_values('security')
print("Median Auction Analysis:")
print("=" * 80)
print(results_df.to_string(index=False))
print()

# Generate config update
print("\nRecommended order_notional values (20% of median auction notional):")
print("-" * 60)
config_values = {}
for r in sorted(results, key=lambda x: x['security']):
    config_values[r['security']] = r['order_notional_20pct']
    print(f"  {r['security']:12s}: {r['order_notional_20pct']:>10,} AED")

# Output as JSON for easy copy
print("\nJSON format for config:")
print(json.dumps(config_values, indent=2))
