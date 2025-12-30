"""Check ADNOCGAS raw data around May 14, 14:55."""
import pandas as pd
from datetime import datetime, time

# Read ADNOCGAS sheet
print("Reading ADNOCGAS data...")
df = pd.read_excel('data/raw/TickData.xlsx', sheet_name='ADNOCGAS UH Equity', header=None, skiprows=4)
df.columns = ['timestamp', 'type', 'price', 'volume']

# Convert timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])

# Clean type column
df['type'] = df['type'].astype(str).str.lower().str.strip()

# Filter for May 14
may14 = df[df['timestamp'].dt.date == pd.Timestamp('2025-05-14').date()].copy()

print(f"\nTotal events on May 14: {len(may14)}")

# Get events around 14:55
around_eod = may14[
    (may14['timestamp'].dt.time >= time(14, 50, 0)) &
    (may14['timestamp'].dt.time <= time(15, 0, 0))
].sort_values('timestamp')

print(f"\nEvents between 14:50-15:00 on May 14:")
print(around_eod[['timestamp', 'type', 'price', 'volume']].to_string())

# Check for trades at/after 14:55
trades_at_eod = may14[
    (may14['type'] == 'trade') &
    (may14['timestamp'].dt.time >= time(14, 55, 0))
].sort_values('timestamp')

print(f"\n\nTrades at/after 14:55:00 on May 14:")
if len(trades_at_eod) > 0:
    print(trades_at_eod[['timestamp', 'type', 'price', 'volume']].to_string())
else:
    print("NO TRADES FOUND")
    
    # Check May 15 for first trade
    print("\n\nChecking May 15...")
    may15 = df[df['timestamp'].dt.date == pd.Timestamp('2025-05-15').date()].copy()
    first_may15_trades = may15[may15['type'] == 'trade'].head(3)
    print("\nFirst 3 trades on May 15:")
    print(first_may15_trades[['timestamp', 'type', 'price', 'volume']].to_string())

# Last few trades before 14:55
print(f"\n\nLast 5 trades before 14:55 on May 14:")
trades_before = may14[
    (may14['type'] == 'trade') &
    (may14['timestamp'].dt.time < time(14, 55, 0))
].tail(5)
print(trades_before[['timestamp', 'type', 'price', 'volume']].to_string())
