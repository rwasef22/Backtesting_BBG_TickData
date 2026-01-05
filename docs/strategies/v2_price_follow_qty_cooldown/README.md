# V2 Price-Follow Qty-Cooldown Strategy

## Overview

V2 is an aggressive market-making strategy that **follows price movements** and uses **cooldown periods after fills** instead of fixed time-based quote updates.

**Status**: Second-best performer (after V2.1 which adds stop-loss)

## Quick Start

```bash
# Run V2 backtest
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown

# Compare V2 vs V2.1
python scripts/fast_sweep.py --intervals 5 10 30 60
```

## Performance Summary

| Metric | V1 Baseline | V2 Price-Follow |
|--------|-------------|-----------------|
| Total P&L | 697,542 AED | 1,319,148 AED (+89%) |
| Sharpe Ratio | 12.70 | 14.19 (+12%) |
| Trades | 106,826 | 283,309 (+165%) |
| Best Interval | 180s | 5s |

## Key Features

### 1. Price-Following Quotes

V2 updates quotes to match the current best bid/ask whenever the cooldown expires:

```
Time 10:00:00: Best bid = 3.50 → Quote at 3.50
Time 10:00:30: Best bid = 3.52 → Update quote to 3.52 (if cooldown expired)
Time 10:01:00: Best bid = 3.48 → Update quote to 3.48
```

**Benefit**: Quotes stay competitive with market movements.

### 2. Cooldown After Fills

After getting filled, V2 waits `refill_interval_sec` before placing new quotes:

```
10:00:00: Quote 65k @ 3.50
10:00:45: Filled 30k @ 3.50 → Start cooldown
10:00:45 - 10:00:50: No new quotes (5s cooldown)
10:00:50: Cooldown expires → New quote at current price
```

**Benefit**: Prevents over-trading immediately after fills.

### 3. Short Refill Intervals

V2 performs best with 5-10 second intervals (vs V1's 180s):

| Interval | Trades | P&L |
|----------|--------|-----|
| 5s | 283,309 | 1,319,148 AED |
| 10s | 277,212 | 1,273,433 AED |
| 30s | 262,150 | 1,156,847 AED |
| 60s | 243,892 | 1,042,563 AED |

## Configuration

### Standard Config
```json
{
  "ADNOCGAS": {
    "quote_size": 65000,
    "refill_interval_sec": 5,
    "max_position": 130000,
    "max_notional": 1500000,
    "min_local_currency_before_quote": 13000
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quote_size` | int | 65000 | Shares to quote per side |
| `refill_interval_sec` | int | 5 | Cooldown after fills (seconds) |
| `max_position` | int | 130000 | Maximum inventory (shares) |
| `max_notional` | int | 1500000 | Max dollar exposure (AED) |
| `min_local_currency_before_quote` | int | 13000 | Minimum liquidity (AED) |

## Comparison with V1

| Feature | V1 Baseline | V2 Price-Follow |
|---------|-------------|-----------------|
| Quote Price | Fixed at entry | Follows market |
| Refill Trigger | Time only | Time after fill |
| Optimal Interval | 180s | 5s |
| Trading Frequency | Low | High |
| Profit per Trade | Higher | Lower (but more trades) |

### Why V2 Outperforms V1

1. **More Trading Opportunities**
   - V2 trades 165% more often
   - Captures many small profits

2. **Competitive Pricing**
   - Quotes stay at best bid/ask
   - Higher fill probability

3. **Faster Capital Turnover**
   - Short cooldowns = more round trips
   - Capital works harder

## Code Structure

```
src/strategies/v2_price_follow_qty_cooldown/
├── __init__.py
├── strategy.py       # V2PriceFollowQtyCooldownStrategy
└── handler.py        # create_v2_price_follow_qty_cooldown_handler()
```

## Running V2

### Single Backtest
```bash
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown
```

### Parameter Sweep
```bash
# Test different intervals
python scripts/comprehensive_sweep.py --strategies v2 --intervals 5 10 30 60 120
```

### Compare Strategies
```bash
python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown
```

## Limitations

1. **No Stop-Loss**: V2 holds losing positions (fixed in V2.1)
2. **Higher Trading Costs**: More trades = more commissions in live trading
3. **Requires Liquid Markets**: Short intervals need active markets

## Upgrading to V2.1

V2.1 adds stop-loss protection to V2. Consider upgrading if you want:
- Automatic loss limiting (2% default)
- Better risk-adjusted returns (Sharpe +5.4%)
- Lower maximum drawdown

```bash
# Run V2.1 instead
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss
```

## Related Documentation

- [V2.1 Stop-Loss Strategy](../v2_1_stop_loss/README.md) - Enhanced version
- [V1 Baseline Strategy](../v1_baseline/README.md) - Reference implementation
- [Parameter Sweep Guide](../../../PARAMETER_SWEEP_GUIDE.md)
