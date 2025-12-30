"""Find where 3.76 price appears in ADNOCGAS May 14 data."""
import pandas as pd
from datetime import datetime, time

# Read ADNOCGAS data
print("Reading ADNOCGAS data...")
df = pd.read_excel('data/raw/TickData.xlsx', sheet_name='ADNOCGAS UH Equity', header=None, skiprows=4)
df.columns = ['timestamp', 'type', 'price', 'volume']
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])
df['type'] = df['type'].astype(str).str.lower().str.strip()

# Filter for May 14
may14 = df[df['timestamp'].dt.date == pd.Timestamp('2025-05-14').date()].copy()

# Find all events with price 3.76
price_376 = may14[may14['price'] == 3.76].sort_values('timestamp')

print(f"\nAll events with price 3.76 on May 14:")
print("=" * 80)
print(price_376[['timestamp', 'type', 'price', 'volume']].to_string())

# Check what's around 14:55
around_eod = may14[
    (may14['timestamp'].dt.time >= time(14, 54, 0)) &
    (may14['timestamp'].dt.time <= time(14, 56, 0))
].sort_values('timestamp')

print(f"\n\nAll events between 14:54-14:56:")
print("=" * 80)
print(around_eod[['timestamp', 'type', 'price', 'volume']].to_string())
