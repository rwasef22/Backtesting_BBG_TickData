# V1 Baseline Strategy

## Overview

V1 Baseline is the original market-making strategy implementation. It serves as the reference implementation against which all other strategy variations are compared.

## Key Characteristics

- **Quote Style**: Join the market (quote at best bid/ask)
- **Refill Logic**: Time-based (every 180 seconds)
- **Position Management**: Position-aware sizing with hard limits
- **Liquidity Check**: Independent bid/ask side validation (13,000 AED threshold)
- **Fill Simulation**: FIFO queue simulation for realistic execution
- **Time Windows**: Skip opening auction, silent period, and closing auction

## Performance Summary

Based on full backtest (all 16 securities):

- **Total Trades**: 142,917
- **Total Volume**: 1.76 billion AED
- **Realized P&L**: +697,122 AED
- **Trading Day Coverage**: 100% for most securities (e.g., ADNOCGAS 136/136 days)
- **Average P&L per Security**: +43,570 AED

## Configuration

Default parameters (see `configs/v1_baseline_config.json`):

| Security | Quote Size | Refill Interval | Max Position | Max Notional | Liquidity Threshold |
|----------|-----------|----------------|--------------|--------------|-------------------|
| ADNOCGAS | 65,000 | 180s | 130,000 | 1,500,000 AED | 13,000 AED |
| *(others)* | 50,000-65,000 | 180s | 100,000-200,000 | varies | 13,000-25,000 AED |

## Strategy Logic

### Quote Generation

```python
def generate_quotes(self, security, best_bid, best_ask):
    # Quote at current best bid/ask
    bid_price = best_bid[0] if best_bid else None
    ask_price = best_ask[0] if best_ask else None
    
    # Size adjusted for position limits
    bid_size = min(base_size, max_pos - current_pos)
    ask_size = min(base_size, max_pos + current_pos)
```

**Key Points**:
- Joins the market (no skew)
- Position-aware sizing prevents limit violations
- Supports max_notional cap for dynamic limits

### Refill Logic

```python
def should_refill_side(self, security, timestamp, side):
    elapsed = (timestamp - last_refill_time[side]).total_seconds()
    return elapsed >= refill_interval_sec
```

**Key Points**:
- Simple time-based trigger
- 180-second default cooldown
- Allows quotes to "stick" and accumulate queue priority

## Strengths

1. **Proven Performance**: +697K AED realized P&L on full dataset
2. **High Coverage**: Trades on virtually all available days
3. **Simple Logic**: Easy to understand and maintain
4. **Conservative**: Position limits prevent runaway risk
5. **Realistic Fills**: Queue simulation models actual execution

## Limitations

1. **Static Refill**: Doesn't adapt to market conditions
2. **No Skew**: Doesn't adjust for inventory
3. **Passive Joining**: Always joins market, never improves prices
4. **No Spread Filter**: Quotes in tight markets (less profit per fill)

## Use Cases

- **Baseline Comparison**: Reference for evaluating other strategies
- **Conservative Trading**: Stable, predictable behavior
- **Full Day Coverage**: Captures most trading opportunities
- **Low Maintenance**: Minimal parameter tuning required

## Files

- Strategy: `src/strategies/v1_baseline/strategy.py`
- Handler: `src/strategies/v1_baseline/handler.py`
- Config: `configs/v1_baseline_config.json`
- Technical Docs: `docs/strategies/v1_baseline/TECHNICAL_DOCUMENTATION.md`
- Non-Technical: `docs/strategies/v1_baseline/NON_TECHNICAL_EXPLANATION.md`

## Running V1 Baseline

```bash
# Full backtest
python scripts/run_strategy.py --strategy v1_baseline

# Quick test (5 securities)
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5

# Custom config
python scripts/run_strategy.py --strategy v1_baseline --config configs/custom_v1.json
```

## Comparing to Other Strategies

```bash
# Compare V1 to V2
python scripts/compare_strategies.py v1_baseline v2_aggressive_refill

# Compare all strategies
python scripts/compare_strategies.py --all
```

## Modification Examples

See `TECHNICAL_DOCUMENTATION.md` for detailed modification guide, including:

- Changing quote sizing logic
- Adjusting refill intervals
- Adding spread constraints
- Implementing inventory penalties
- Modifying time windows
- Adding custom metrics

## Version History

- **v1.0** (Initial): Original implementation
- **v1.1** (Current): Fixed per-side independent liquidity checks

## Status

✅ **Production Ready** - Validated on full dataset with consistent positive P&L
