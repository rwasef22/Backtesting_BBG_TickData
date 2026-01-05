# V2 Price Follow with Quantity Cooldown Strategy

## Overview

The **v2_price_follow_qty_cooldown** strategy combines aggressive price updates with conservative quantity management. Quote prices continuously track the market for competitiveness, while quantity refills are controlled via cooldown periods after executions.

## Strategy Name
`v2_price_follow_qty_cooldown` (Version 2.0)

---

## Core Characteristics

| Aspect | Behavior | Rationale |
|--------|----------|-----------|
| **Price Updates** | Continuous - always at best bid/ask | Maximize competitiveness and fill opportunities |
| **Quantity Refills** | Cooldown after ANY fill | Prevent aggressive reloading after executions |
| **Queue Position** | Reset on price changes | Join back of queue at new price level |
| **Market Presence** | Always present (if sufficient liquidity) | Capture all opportunities, even during cooldown |
| **Cooldown Trigger** | Any fill (partial or full) | Same cooldown duration regardless of fill size |

---

## Key Differences from v1_baseline

### v1_baseline (Sticky Quotes):
```
Time 10:00:00 - Market: 3.50 / 3.52
  → Place bid @ 3.50, start 180s timer
  
Time 10:01:00 - Market moves to: 3.51 / 3.53
  → Still quoting 3.50 (timer has 120s remaining)
  → OFF-MARKET QUOTE
  
Time 10:03:00 - Timer expires
  → Can update to 3.51
```

### v2_price_follow_qty_cooldown (Price Following):
```
Time 10:00:00 - Market: 3.50 / 3.52
  → Place bid: 65,000 @ 3.50
  
Time 10:01:00 - Market moves to: 3.51 / 3.53
  → Update bid to 3.51 immediately (65,000 @ 3.51)
  → ALWAYS AT MARKET
  → Reset queue position (join back with 65,000 @ 3.51)
  
Time 10:01:30 - Partial fill: 20,000 shares
  → START COOLDOWN (180s until 10:04:30)
  → Remaining: 45,000 shares
  
Time 10:02:00 - Market moves to: 3.52 / 3.54
  → Update bid to 3.52 (45,000 @ 3.52)
  → PRICE UPDATES, but QUANTITY STAYS REDUCED
  → Reset queue position (join back with 45,000 @ 3.52)
  
Time 10:04:30 - Cooldown expires
  → Refill quantity back to 65,000 @ current market
```

---

## Detailed Logic Flow

### 1. Quote Generation

**Every BID/ASK Market Update:**
```python
# Get current best bid/ask
best_bid = orderbook.get_best_bid()  # e.g., (3.50, 100000)
best_ask = orderbook.get_best_ask()  # e.g., (3.52, 80000)

# Check cooldown state
if is_in_cooldown(security, timestamp, 'bid'):
    # In cooldown: use remaining quantity only
    bid_size = active_orders[security]['bid']['our_remaining']
else:
    # Not in cooldown: use full configured size
    bid_size = config['quote_size_bid']

# Price ALWAYS follows market
bid_price = best_bid[0]  # 3.50

# Apply position limits
bid_size = min(bid_size, max_position - current_position)
bid_size = max(0, bid_size)

# Generate quote
quote = {'bid_price': 3.50, 'bid_size': bid_size}
```

### 2. Queue Position Management

**When Price Changes:**
```python
current_price = active_orders[security]['bid']['price']
new_price = best_bid[0]

if current_price != new_price:
    # Price changed - reset queue position
    ahead_qty = orderbook.bids.get(new_price, 0)
    
    active_orders[security]['bid'] = {
        'price': new_price,
        'ahead_qty': ahead_qty,      # All existing qty is ahead of us
        'our_remaining': bid_size     # Our new order size
    }
```

**When Price Unchanged:**
```python
# Price same - just update our_remaining (in case cooldown expired)
active_orders[security]['bid']['our_remaining'] = bid_size
```

### 3. Fill Processing

**On Market Trade:**
```python
# Check if trade hits our quote
if trade_price <= our_bid_price:
    # Consume ahead quantity first
    consumed_ahead = min(ahead_qty, trade_qty)
    ahead_qty -= consumed_ahead
    remaining = trade_qty - consumed_ahead
    
    # Then consume our order
    if remaining > 0 and our_remaining > 0:
        consumed_ours = min(our_remaining, remaining)
        our_remaining -= consumed_ours
        
        # Record fill
        record_fill(security, 'buy', trade_price, consumed_ours, timestamp)
        
        # START COOLDOWN
        last_fill_time[security]['bid'] = timestamp
```

### 4. Cooldown Logic

**Checking Cooldown State:**
```python
def is_in_cooldown(security, timestamp, side):
    last_fill = last_fill_time[security][side]
    
    if last_fill is None:
        return False  # No previous fill
    
    elapsed = (timestamp - last_fill).total_seconds()
    interval = config['refill_interval_sec']  # e.g., 180
    
    return elapsed < interval  # True if still in cooldown
```

**During Cooldown:**
- ✅ Price updates continue
- ✅ Can quote remaining unfilled quantity
- ❌ Cannot refill to full quote_size

**After Cooldown:**
- ✅ Quantity refills to full quote_size
- ✅ Price continues to follow market

---

## Complete Example Scenario

### Setup:
- Config: `quote_size_bid = 65000`, `refill_interval_sec = 180`
- Initial market: 3.50 / 3.52
- Queue at 3.50: 80,000 shares ahead of us

### Timeline:

**10:00:00** - Initial Quote
```
Market: 3.50 / 3.52
Action: Place bid 65,000 @ 3.50
Queue: 80,000 ahead, 65,000 ours
Cooldown: No (first quote)
```

**10:01:00** - Market Moves Up
```
Market: 3.51 / 3.53
Action: Update bid to 3.51 (price follows market)
Queue: Reset - join back with orderbook qty @ 3.51
  - ahead_qty = orderbook.bids[3.51] (e.g., 50,000)
  - our_remaining = 65,000
Cooldown: No
```

**10:01:30** - Partial Fill
```
Market Trade: 100,000 @ 3.51
Execution:
  - Consume 50,000 ahead
  - Consume 50,000 from remaining 50,000
  - We fill: 20,000 shares
Action: START COOLDOWN (until 10:04:30)
Queue: 30,000 ahead, 45,000 ours remaining
Position: +20,000
```

**10:02:00** - Market Moves During Cooldown
```
Market: 3.52 / 3.54
Action: Update bid to 3.52 (price follows)
Queue: Reset - join back @ 3.52
  - ahead_qty = orderbook.bids[3.52] (e.g., 70,000)
  - our_remaining = 45,000 (REDUCED, in cooldown)
Cooldown: YES (elapsed = 30s / 180s)
```

**10:03:00** - Still in Cooldown
```
Market: 3.52 / 3.54 (unchanged)
Action: No change (price same, still in cooldown)
Queue: 70,000 ahead, 45,000 ours
Cooldown: YES (elapsed = 90s / 180s)
```

**10:04:30** - Cooldown Expires
```
Market: 3.53 / 3.55 (moved during cooldown)
Action: Update to 3.53 AND refill quantity to 65,000
Queue: Reset @ 3.53
  - ahead_qty = orderbook.bids[3.53] (e.g., 60,000)
  - our_remaining = 65,000 (REFILLED)
Cooldown: NO (expired)
```

**10:05:00** - Another Fill
```
Market Trade: 150,000 @ 3.53
Execution: We fill 30,000 more
Action: START NEW COOLDOWN (until 10:08:00)
Queue: our_remaining = 35,000
Position: +50,000
```

---

## Trade-offs vs v1_baseline

### Advantages:
✅ **Always Competitive**: Quotes always at current market price
✅ **No Off-Market Quotes**: Never stale or away from market
✅ **Continuous Presence**: Always in market (even during cooldown)
✅ **Captures More Opportunities**: More trades due to price following

### Disadvantages:
❌ **Lower Queue Priority**: Reset queue position on every price change
❌ **Higher Adverse Selection**: Always present means more risk
❌ **More Quote Updates**: Computational overhead from continuous updates
❌ **Reduced Cooldown Benefit**: Can still trade during cooldown (with reduced size)

---

## Configuration

Uses same parameters as v1_baseline:

```json
{
  "EMAAR": {
    "quote_size": 65000,
    "refill_interval_sec": 180,
    "max_position": 130000,
    "max_notional": 1500000,
    "min_local_currency_before_quote": 13000
  }
}
```

### Parameter Meanings in v2:
- `quote_size`: Full quantity when NOT in cooldown
- `refill_interval_sec`: Cooldown duration after ANY fill
- `max_position`: Hard limit on inventory
- `min_local_currency_before_quote`: Liquidity threshold for quoting

---

## Usage

### Run Backtest:
```bash
python scripts/run_v2_price_follow_qty_cooldown.py
```

### Output Files:
```
output/v2_price_follow_qty_cooldown/
├── backtest_summary.csv              # Aggregate results
├── {security}_trades_timeseries.csv  # Per-security trades
├── {security}_inventory_pnl.png      # Visualization
└── run_log.txt                       # Execution log
```

### Programmatic Usage:
```python
from src.strategies.v2_price_follow_qty_cooldown import create_v2_price_follow_qty_cooldown_handler
from src.market_making_backtest import MarketMakingBacktest

config = load_strategy_config('configs/mm_config.json')
handler = create_v2_price_follow_qty_cooldown_handler(config)

backtest = MarketMakingBacktest()
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    only_trades=False
)
```

---

## Expected Performance Characteristics

### vs v1_baseline:

| Metric | v1 | v2 | Reasoning |
|--------|----|----|-----------|
| **Number of Trades** | Baseline | ⬆️ Higher | Always at market = more fills |
| **Average P&L per Trade** | Baseline | ⬇️ Lower | Less queue priority = worse prices |
| **Total P&L** | Baseline | ❓ Unknown | Depends on trade-off between volume and price |
| **Fill Rate** | Baseline | ⬆️ Higher | Continuous presence at best prices |
| **Adverse Selection** | Baseline | ⬆️ Higher | Always present when market moves |
| **Queue Priority** | ⬆️ Better | Baseline | v1 builds priority, v2 resets |

### Ideal Market Conditions for v2:
✅ Fast-moving markets (frequent price changes)
✅ High liquidity (deep orderbook)
✅ Mean-reverting moves (benefit from continuous presence)
✅ Low adverse selection cost

### Poor Conditions for v2:
❌ Directional moves (higher adverse selection)
❌ Thin orderbook (lose priority advantage)
❌ High information asymmetry (always present = always at risk)

---

## Next Steps

1. **Run Backtest**: Compare v2 results against v1_baseline
2. **Analyze Metrics**: 
   - Trade count
   - Fill rate
   - P&L per trade
   - Total P&L
3. **Tune Parameters**:
   - Adjust `refill_interval_sec` if needed
   - Optimize quote sizes
4. **Create v3**: Consider hybrid approaches based on findings

---

## Technical Notes

### Queue Simulation:
- When price changes, `ahead_qty` is set to current orderbook quantity at new price
- Assumes FIFO queue within each price level
- Simplified model: doesn't account for order cancellations or hidden liquidity

### Cooldown Implementation:
- Uses `last_fill_time` instead of `last_refill_time`
- Timer starts on ANY fill (partial or full)
- During cooldown, quotes with `our_remaining` quantity
- After cooldown, refills to full `quote_size`

### Edge Cases Handled:
1. **Complete Fill During Cooldown**: Quote nothing (our_remaining = 0)
2. **Position Limits**: Applied even during cooldown
3. **Liquidity Check**: Same threshold as v1_baseline
4. **Multiple Fills**: Each fill resets cooldown timer

---

## Conclusion

The v2_price_follow_qty_cooldown strategy prioritizes market competitiveness through continuous price updates while maintaining risk control via quantity refill cooldowns. It's designed for markets where being at the best price is critical, but reload discipline after executions prevents excessive risk accumulation.

Compare results against v1_baseline to determine which approach works better for your specific market conditions and risk tolerance.
