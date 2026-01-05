# EOD Position Flattening Limitation

## Overview

The V2 strategy (and all derived strategies like V2.1) have a limitation in their End-of-Day (EOD) position flattening logic that can result in positions carrying overnight.

## Expected Behavior

**Goal**: All positions should be closed to 0 at end of trading day (14:55) to avoid overnight risk.

## Actual Behavior

**Implementation**: EOD flatten logic in [handler.py](../../src/strategies/v2_price_follow_qty_cooldown/handler.py) lines 82-108:

```python
# At 14:55, if position != 0:
if event_type == 'trade':
    # Use this trade price to flatten immediately
    strategy.flatten_position(security, price, timestamp)
else:
    # Not a trade - set pending_flatten and wait for next trade
    state['pending_flatten'] = {...}
    # Wait for trade event to execute flatten
```

**Problem**: If there are **no TRADE events** at or after 14:55 on a given trading day, the position is never flattened.

## Impact Analysis

From full backtest of 16 securities (V2 @ 30s refill):

| Security | Days with Non-Zero EOD | Positions |
|----------|------------------------|-----------|
| EMAAR | 1 | +500 |
| EMIRATES | 1 | +3,400 |
| PARKIN | 1 | -1,446 |
| SALIK | 1 | -209 |
| TALABAT | 3 | +20,791, +25,000, -57,702 |
| **Total** | **7 occurrences** | **across 5 securities** |

**Frequency**: Very rare - only 7 instances across thousands of trading days
**Magnitude**: Ranges from small (209 shares) to significant (57,702 shares)

## Why This Happens

1. **Low liquidity near close**: Some securities stop trading before 14:55
2. **Closing auction gap**: Trading pauses during 14:45-14:55 closing auction
3. **No reopening**: Some days have no trades after closing auction ends at 14:55

## Implications

### ✅ **Minimal Impact**
- Rare occurrence (7 days out of thousands)
- Most days flatten correctly
- Strategy continues trading normally next day with carried position

### ⚠️ **Risks**
- Overnight gap risk (price changes between close and next open)
- Position limits may be breached if position carried overnight
- P&L attribution affected (overnight vs intraday)
- May violate risk management rules requiring flat book EOD

## Workarounds

### Option 1: Force Flatten at Last Available Price
```python
# At 14:55, flatten immediately using last known price
if strategy.position[security] != 0:
    # Use best bid/ask or last trade price
    flatten_price = orderbook.last_trade['price'] if orderbook.last_trade else \
                    (best_bid[0] if best_bid else best_ask[0])
    strategy.flatten_position(security, flatten_price, timestamp)
```

**Pros**: Guarantees flat position
**Cons**: May use stale price, no real trade execution

### Option 2: Check for Stale Data at Day End
```python
# After processing all data for a day, force flatten if needed
if strategy.position[security] != 0:
    # Log warning and flatten at last available price
    print(f"WARNING: {security} ending day with position {position}")
    strategy.flatten_position(security, last_price, end_of_day_time)
```

**Pros**: Catches all cases, logs for review
**Cons**: Still using assumed price

### Option 3: Accept Limitation and Monitor
- Document the behavior (this file)
- Monitor positions that carry overnight
- Manually review these cases
- Consider in P&L analysis

**Pros**: Simple, no code changes, realistic (reflects actual market conditions)
**Cons**: Positions may carry overnight

## Current Status

**Decision**: Option 3 - Accept and document

**Rationale**:
1. Very rare occurrence (7 out of ~5,000+ trading days across 16 securities)
2. Reflects realistic market conditions (can't trade if no liquidity)
3. Using stale prices for forced flatten creates artificial fills
4. Easier to handle edge cases in post-processing than create fake trades

## Monitoring

To check for non-flat EOD positions:

```bash
python check_v2_trading_windows.py
```

This will report all days ending with non-zero positions across all securities.

## Related Files

- [V2 Handler](../../src/strategies/v2_price_follow_qty_cooldown/handler.py) - EOD flatten logic
- [V2.1 Handler](../../src/strategies/v2_1_stop_loss/handler.py) - Inherits same limitation
- [Base Strategy](../../src/strategies/base_strategy.py) - `flatten_position()` method

## Recommendation for Production

If deploying this strategy in production:

1. **Add EOD position monitoring** - Alert if position not flat at 15:00
2. **Manual intervention protocol** - Define process for manually closing positions if needed
3. **Consider market-on-close orders** - Use actual MOC orders instead of waiting for trades
4. **Risk limits** - Include overnight position limits in risk framework

---

**Last Updated**: December 31, 2025
**Affects**: V2, V2.1 (all strategies using this EOD flatten logic)
**Severity**: Low (rare, small positions)
**Status**: Documented, accepted limitation
