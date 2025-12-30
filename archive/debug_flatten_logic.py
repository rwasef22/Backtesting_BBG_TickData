"""Debug the EOD flatten logic to see exactly what events are processed."""
import pandas as pd
from datetime import datetime, time

# Read ADNOCGAS data
print("Reading ADNOCGAS data...")
df = pd.read_excel('data/raw/TickData.xlsx', sheet_name='ADNOCGAS UH Equity', header=None, skiprows=4)
df.columns = ['timestamp', 'type', 'price', 'volume']
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])
df['type'] = df['type'].astype(str).str.lower().str.strip()

# Filter for May 14 around 14:55
may14 = df[df['timestamp'].dt.date == pd.Timestamp('2025-05-14').date()].copy()
eod_events = may14[may14['timestamp'].dt.time >= time(14, 54, 55)].sort_values('timestamp')

print(f"\nEvents at/after 14:54:55 on May 14:")
print("=" * 80)

# Simulate the handler logic
closed_at_eod = False
pending_flatten = None
position = 130000  # From the CSV, there's a position at this time

for idx, row in eod_events.iterrows():
    timestamp = row['timestamp']
    event_type = row['type']
    price = row['price']
    volume = row['volume']
    
    print(f"\nEvent: {timestamp} | Type: {event_type:5s} | Price: {price:.2f} | Volume: {volume}")
    
    # Check if EOD time (>= 14:55:00)
    is_eod_time = timestamp.time() >= time(14, 55, 0)
    
    print(f"  is_eod_time={is_eod_time}, closed_at_eod={closed_at_eod}, pending_flatten={pending_flatten is not None}")
    
    # 1) EOD flatten at/after 14:55
    if is_eod_time and not closed_at_eod:
        if position != 0:
            print(f"  --> EOD condition met! Position={position}")
            if event_type == 'trade':
                print(f"  --> Current event IS a trade, flatten NOW at price {price:.2f}")
                print(f"  --> FLATTEN EXECUTED at {timestamp} with price {price:.2f}")
                closed_at_eod = True
                break
            else:
                print(f"  --> Current event is NOT a trade ({event_type}), marking pending_flatten")
                pending_flatten = {
                    'position': position,
                    'timestamp': timestamp,
                    'trigger_price': price  # Store what price triggered this
                }
                closed_at_eod = True
                print(f"  --> Marked pending_flatten, will wait for trade")
                continue
    
    # 2) Execute pending flatten when we see a trade
    if pending_flatten is not None:
        print(f"  --> Pending flatten active")
        if event_type == 'trade':
            print(f"  --> Found trade! Flatten at price {price:.2f}")
            print(f"  --> FLATTEN EXECUTED at {timestamp} with price {price:.2f}")
            pending_flatten = None
            break
        else:
            print(f"  --> Not a trade ({event_type}), continuing to skip...")
            continue
    
    print(f"  --> Normal processing (no EOD action)")
    
    # Only show first 20 events
    if eod_events.index.get_loc(idx) >= 20:
        print("\n... stopping at 20 events for brevity ...")
        break

print("\n" + "=" * 80)
if pending_flatten:
    print(f"WARNING: pending_flatten still active at end! Trigger price was {pending_flatten['trigger_price']:.2f}")
