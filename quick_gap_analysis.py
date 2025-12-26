import pandas as pd
from datetime import datetime

print("Analyzing ADNOCGAS trading gaps...")

# Read the backtest results
print("\n1. Reading backtest CSV...")
df = pd.read_csv('output/adnocgas_trades_timeseries.csv')
df['date'] = pd.to_datetime(df['timestamp']).dt.date
traded_dates = set(df['date'].unique())

print(f"   Strategy traded on: {len(traded_dates)} days")
print(f"   Date range: {min(traded_dates)} to {max(traded_dates)}")

# Calculate expected trading days (weekdays from first to last date)
from datetime import timedelta

first_date = min(traded_dates)
last_date = max(traded_dates)
all_dates = []
current = first_date
while current <= last_date:
    # Skip weekends (5=Saturday, 6=Sunday)
    if current.weekday() < 5:
        all_dates.append(current)
    current += timedelta(days=1)

print(f"\n2. Expected trading days (weekdays): {len(all_dates)}")
print(f"   From {first_date} to {last_date}")

# Find missing dates
missing_dates = [d for d in all_dates if d not in traded_dates]

print(f"\n3. Missing trading days: {len(missing_dates)}")
print(f"   Coverage: {len(traded_dates)/len(all_dates)*100:.1f}%")

if missing_dates:
    print(f"\n4. Sample missing dates (first 20):")
    for date in missing_dates[:20]:
        print(f"   {date} ({date.strftime('%A')})")
    
    if len(missing_dates) > 20:
        print(f"   ... and {len(missing_dates)-20} more")

# Group by month
from collections import defaultdict
monthly_coverage = defaultdict(lambda: {'expected': 0, 'actual': 0})

for date in all_dates:
    month_key = date.strftime('%Y-%m')
    monthly_coverage[month_key]['expected'] += 1
    if date in traded_dates:
        monthly_coverage[month_key]['actual'] += 1

print(f"\n5. Monthly breakdown:")
for month in sorted(monthly_coverage.keys()):
    stats = monthly_coverage[month]
    coverage = stats['actual'] / stats['expected'] * 100
    print(f"   {month}: {stats['actual']:2d}/{stats['expected']:2d} days ({coverage:5.1f}%)")

print(f"\n{'='*60}")
print(f"Key Findings:")
print(f"  - ADNOCGAS has {len(missing_dates)} missing weekday trading days")
print(f"  - This represents {len(missing_dates)/len(all_dates)*100:.1f}% of expected trading days")
print(f"  - Most likely reasons:")
print(f"    1. Market was closed on those days (holidays)")
print(f"    2. ADNOCGAS specifically didn't trade on those days")
print(f"    3. Insufficient liquidity on those days")
print(f"{'='*60}")

# Save to file
with open('output/adnocgas_missing_dates.txt', 'w') as f:
    f.write("ADNOCGAS Missing Trading Days Analysis\n")
    f.write("="*60 + "\n\n")
    f.write(f"Total weekdays in period: {len(all_dates)}\n")
    f.write(f"Days strategy traded: {len(traded_dates)}\n")
    f.write(f"Missing days: {len(missing_dates)}\n")
    f.write(f"Coverage: {len(traded_dates)/len(all_dates)*100:.1f}%\n\n")
    f.write("Missing dates:\n")
    for date in missing_dates:
        f.write(f"  {date} ({date.strftime('%A')})\n")
    f.write(f"\nMonthly breakdown:\n")
    for month in sorted(monthly_coverage.keys()):
        stats = monthly_coverage[month]
        coverage = stats['actual'] / stats['expected'] * 100
        f.write(f"  {month}: {stats['actual']:2d}/{stats['expected']:2d} days ({coverage:5.1f}%)\n")

print(f"\nResults saved to: output/adnocgas_missing_dates.txt")
