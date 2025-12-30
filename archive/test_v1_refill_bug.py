"""Test if v1 refill timer is reset correctly after fills."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from datetime import datetime, timedelta
from src.market_making_strategy import MarketMakingStrategy

# Test with v1 strategy
config = {'TEST': {'refill_interval_sec': 180, 'quote_size': 50000, 'max_position': 1000000, 'min_local_currency_before_quote': 25000}}

print("="*80)
print("V1 REFILL TIMER TEST (After Fill)")
print("="*80)

strategy = MarketMakingStrategy(config=config)
strategy.initialize_security('TEST')

# Simulate timeline
t0 = datetime(2025, 1, 1, 10, 0, 0)

# Set initial refill time
print(f"\nt={0:4d}s: Set initial refill time for bid")
strategy.set_refill_time('TEST', 'bid', t0)
print(f"  last_refill_time['bid'] = {strategy.last_refill_time.get('TEST', {}).get('bid')}")

# Check should_refill immediately (should be False)
t1 = t0 + timedelta(seconds=1)
print(f"\nt={1:4d}s: Check should_refill_side (should be False - just quoted)")
should_refill = strategy.should_refill_side('TEST', t1, 'bid')
print(f"  should_refill_side('bid'): {should_refill}")

# Simulate a fill at t=30s
t2 = t0 + timedelta(seconds=30)
print(f"\nt={30:4d}s: Simulate fill of 10,000 shares")
strategy.active_orders['TEST'] = {
    'bid': {'price': 100, 'ahead_qty': 50000, 'our_remaining': 50000},
    'ask': {}
}
print(f"  Before fill: last_refill_time = {strategy.last_refill_time.get('TEST', {})}")
strategy._record_fill('TEST', 'buy', 100.0, 10000, t2)
print(f"  After fill: last_refill_time = {strategy.last_refill_time.get('TEST', {})}")

# Check immediately after fill (should it reset timer to 30s?)
t3 = t2 + timedelta(seconds=1)
print(f"\nt={31:4d}s: Check should_refill_side immediately after fill")
should_refill = strategy.should_refill_side('TEST', t3, 'bid')
print(f"  should_refill_side('bid'): {should_refill}")
print(f"  EXPECTED: False (timer should have been reset to t=30s)")

# Check at original refill time (t=180s from initial quote at t=0)
t4 = t0 + timedelta(seconds=181)
print(f"\nt={181:4d}s: Check at 181s from initial quote")
should_refill = strategy.should_refill_side('TEST', t4, 'bid')
print(f"  should_refill_side('bid'): {should_refill}")
print(f"  EXPECTED: True (original 180s expired)")

# Check at 180s from fill (t=210s total)
t5 = t2 + timedelta(seconds=181)
print(f"\nt={211:4d}s: Check at 181s from fill (should be 211s total)")
should_refill = strategy.should_refill_side('TEST', t5, 'bid')
print(f"  should_refill_side('bid'): {should_refill}")
print(f"  EXPECTED: True (180s from fill expired)")

print("\n" + "="*80)
print("INTERPRETATION:")
print("="*80)
print("If last_refill_time['bid'] is NOT updated after fill,")
print("then the refill timer was NOT reset by the fill.")
print("This means fills don't restart the cooldown period in v1!")
print("="*80)
