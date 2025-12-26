"""Analyze the gap starting May 9th in detail"""
import pandas as pd
import openpyxl
from datetime import datetime
from collections import defaultdict

print("Analyzing EMAAR data to find the May 9th gap pattern...\n")

# First check what dates actually traded
df = pd.read_csv('output/emaar_trades_timeseries.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['date'] = df['timestamp'].dt.date

strategy_dates = sorted(df['date'].unique())
print(f"Strategy traded on {len(strategy_dates)} dates")
print(f"First trade date: {strategy_dates[0]}")
print(f"Last trade date: {strategy_dates[-1]}")
print()

# Find the gap
gap_start = None
for i in range(len(strategy_dates) - 1):
    days_diff = (strategy_dates[i+1] - strategy_dates[i]).days
    if days_diff > 5:  # More than a week gap
        print(f"GAP FOUND: {strategy_dates[i]} to {strategy_dates[i+1]} ({days_diff} days)")
        gap_start = strategy_dates[i]
        gap_end = strategy_dates[i+1]

# Now check Excel data during the gap period
print(f"\nChecking Excel data from {gap_start} to {gap_end}...")
wb = openpyxl.load_workbook('data/raw/TickData.xlsx', read_only=True)
ws = wb['EMAAR UH Equity']

date_stats = defaultdict(lambda: {'rows': 0, 'trades': 0, 'bids': 0, 'asks': 0, 
                                   'min_bid_price': float('inf'), 'max_bid_price': 0,
                                   'min_ask_price': float('inf'), 'max_ask_price': 0,
                                   'bid_volumes': [], 'ask_volumes': []})

for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        try:
            timestamp = row[0]
            if isinstance(timestamp, str):
                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            date_only = timestamp.date()
            
            # Only analyze dates in the gap
            if date_only < gap_start or date_only > gap_end:
                continue
            
            event_type = str(row[1]).lower() if row[1] else None
            price = float(row[2]) if row[2] is not None else None
            volume = float(row[3]) if row[3] is not None else None
            
            date_stats[date_only]['rows'] += 1
            
            if event_type == 'trade':
                date_stats[date_only]['trades'] += 1
            elif event_type == 'bid' and price:
                date_stats[date_only]['bids'] += 1
                date_stats[date_only]['min_bid_price'] = min(date_stats[date_only]['min_bid_price'], price)
                date_stats[date_only]['max_bid_price'] = max(date_stats[date_only]['max_bid_price'], price)
                if volume:
                    date_stats[date_only]['bid_volumes'].append(volume)
            elif event_type == 'ask' and price:
                date_stats[date_only]['asks'] += 1
                date_stats[date_only]['min_ask_price'] = min(date_stats[date_only]['min_ask_price'], price)
                date_stats[date_only]['max_ask_price'] = max(date_stats[date_only]['max_ask_price'], price)
                if volume:
                    date_stats[date_only]['ask_volumes'].append(volume)
        except:
            pass

# Show stats for first few gap dates
print(f"\nData statistics for first 10 dates in gap:")
gap_dates = sorted([d for d in date_stats.keys() if gap_start < d < gap_end])[:10]

for date in gap_dates:
    stats = date_stats[date]
    avg_bid_vol = sum(stats['bid_volumes']) / len(stats['bid_volumes']) if stats['bid_volumes'] else 0
    avg_ask_vol = sum(stats['ask_volumes']) / len(stats['ask_volumes']) if stats['ask_volumes'] else 0
    
    print(f"\n{date}:")
    print(f"  Total rows: {stats['rows']}")
    print(f"  Trades: {stats['trades']}, Bids: {stats['bids']}, Asks: {stats['asks']}")
    if stats['min_bid_price'] < float('inf'):
        print(f"  Bid prices: {stats['min_bid_price']:.2f} - {stats['max_bid_price']:.2f}")
        print(f"  Avg bid volume: {avg_bid_vol:.0f} shares")
    if stats['min_ask_price'] < float('inf'):
        print(f"  Ask prices: {stats['min_ask_price']:.2f} - {stats['max_ask_price']:.2f}")
        print(f"  Avg ask volume: {avg_ask_vol:.0f} shares")
    
    # Check if liquidity threshold would be met
    if stats['min_bid_price'] < float('inf') and avg_bid_vol > 0:
        bid_notional = stats['min_bid_price'] * avg_bid_vol
        print(f"  Best bid notional: {bid_notional:.0f} AED (threshold: 25,000)")
        if bid_notional < 25000:
            print(f"  ❌ BELOW THRESHOLD")
