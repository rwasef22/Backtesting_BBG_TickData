import sys
sys.path.insert(0, '.')
import pandas as pd
from datetime import datetime

# Test timestamp comparison
t1 = pd.Timestamp('2025-05-14 10:00:00')
t2 = pd.Timestamp('2025-05-14 10:03:01')

print(f"t1: {t1} (type: {type(t1)})")
print(f"t2: {t2} (type: {type(t2)})")

elapsed = (t2 - t1).total_seconds()
print(f"Elapsed seconds: {elapsed}")
print(f"Should refill (180s interval): {elapsed >= 180}")

# Check if there's a timezone issue
print(f"\nt1 tz: {t1.tz}")
print(f"t2 tz: {t2.tz}")
