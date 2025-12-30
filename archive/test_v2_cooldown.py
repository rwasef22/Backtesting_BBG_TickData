"""Debug script to trace v2 cooldown behavior with different intervals."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from datetime import datetime, timedelta
from src.strategies.v2_price_follow_qty_cooldown.strategy import V2PriceFollowQtyCooldownStrategy

# Test with two different intervals
configs = {
    'TEST1_60s': {'refill_interval_sec': 60, 'quote_size': 50000, 'max_position': 1000000, 'min_local_currency_before_quote': 25000},
    'TEST2_600s': {'refill_interval_sec': 600, 'quote_size': 50000, 'max_position': 1000000, 'min_local_currency_before_quote': 25000}
}

print("="*80)
print("V2 COOLDOWN BEHAVIOR TEST")
print("="*80)

for test_name, config in configs.items():
    print(f"\n{test_name}: refill_interval_sec = {config['refill_interval_sec']}s")
    print("-"*80)
    
    strategy = V2PriceFollowQtyCooldownStrategy(config={'TEST': config})
    strategy.initialize_security('TEST')
    
    # Simulate timeline
    t0 = datetime(2025, 1, 1, 10, 0, 0)
    
    # Initial quote (no fills yet)
    print(f"\nt={0:4d}s: Initial state (no fills)")
    in_cooldown = strategy.is_in_cooldown('TEST', t0, 'bid')
    quote_size = strategy.get_quote_size('TEST', t0, 'bid')
    print(f"  is_in_cooldown: {in_cooldown}")
    print(f"  get_quote_size: {quote_size}")
    
    # Simulate a fill
    print(f"\nt={0:4d}s: Simulate fill of 10,000 shares")
    strategy.active_orders['TEST'] = {
        'bid': {'price': 100, 'ahead_qty': 50000, 'our_remaining': 50000},
        'ask': {}
    }
    print(f"  Before fill: last_fill_time = {strategy.last_fill_time.get('TEST', {}).get('bid')}")
    strategy._record_fill('TEST', 'buy', 100.0, 10000, t0)
    print(f"  After fill: last_fill_time = {strategy.last_fill_time.get('TEST', {}).get('bid')}")
    print(f"  Filled 10,000 shares")
    
    # Check immediately after fill
    t1 = t0 + timedelta(seconds=1)
    print(f"\nt={1:4d}s: Check 1 second after fill")
    in_cooldown = strategy.is_in_cooldown('TEST', t1, 'bid')
    # Update remaining
    strategy.active_orders['TEST']['bid']['our_remaining'] = 40000
    quote_size = strategy.get_quote_size('TEST', t1, 'bid')
    print(f"  is_in_cooldown: {in_cooldown}")
    print(f"  get_quote_size: {quote_size} (should be 40,000 if in cooldown)")
    
    # Check at half the interval
    t2 = t0 + timedelta(seconds=config['refill_interval_sec'] // 2)
    print(f"\nt={config['refill_interval_sec']//2:4d}s: Check at half interval")
    in_cooldown = strategy.is_in_cooldown('TEST', t2, 'bid')
    quote_size = strategy.get_quote_size('TEST', t2, 'bid')
    print(f"  is_in_cooldown: {in_cooldown}")
    print(f"  get_quote_size: {quote_size} (should be 40,000 if still in cooldown)")
    
    # Check right before interval expires
    t3 = t0 + timedelta(seconds=config['refill_interval_sec'] - 1)
    print(f"\nt={config['refill_interval_sec']-1:4d}s: Check 1s before cooldown expires")
    in_cooldown = strategy.is_in_cooldown('TEST', t3, 'bid')
    quote_size = strategy.get_quote_size('TEST', t3, 'bid')
    print(f"  is_in_cooldown: {in_cooldown}")
    print(f"  get_quote_size: {quote_size}")
    
    # Check after interval expires
    t4 = t0 + timedelta(seconds=config['refill_interval_sec'] + 1)
    print(f"\nt={config['refill_interval_sec']+1:4d}s: Check after cooldown expires")
    in_cooldown = strategy.is_in_cooldown('TEST', t4, 'bid')
    quote_size = strategy.get_quote_size('TEST', t4, 'bid')
    print(f"  is_in_cooldown: {in_cooldown}")
    print(f"  get_quote_size: {quote_size} (should be 50,000 - back to full size)")
    
    print()

print("="*80)
print("TEST COMPLETE")
print("="*80)
print("\nExpected difference:")
print("- TEST1 (60s): Should show cooldown=False after 61 seconds")
print("- TEST2 (600s): Should show cooldown=True even at 599 seconds")
