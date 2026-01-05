# V2.1 Stop-Loss Strategy

## Overview

V2.1 extends the V2 price-follow strategy with **stop-loss protection** that automatically exits positions when unrealized losses exceed a configurable threshold (default: 2% of position value).

**Status**: ⭐ **BEST PERFORMING** - Recommended for production use

## Quick Start

```bash
# Run V2.1 backtest
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss

# Compare V2 vs V2.1
python scripts/fast_sweep.py --intervals 5 10 30 60
```

## Performance Summary

| Metric | V2 | V2.1 | Improvement |
|--------|-----|------|-------------|
| Total P&L | 1,319,148 AED | 1,408,864 AED | +6.8% |
| Sharpe Ratio | 14.19 | 14.96 | +5.4% |
| Max Drawdown | -664,129 AED | -648,422 AED | -2.4% (better) |
| Win Rate | 23.55% | 23.64% | +0.09pp |

## Key Features

### 1. Stop-Loss Protection

When unrealized losses exceed the threshold, V2.1 immediately exits the position:

```python
unrealized_pnl = (current_price - entry_price) * position
loss_threshold = entry_price * position * (stop_loss_pct / 100)

if unrealized_pnl < -loss_threshold:
    # Exit position immediately
    flatten_position(security, current_price, timestamp)
```

### 2. All V2 Features Preserved

- **Price-following quotes**: Updates quotes to match current best bid/ask
- **Cooldown after fills**: Waits `refill_interval_sec` before requoting
- **FIFO queue simulation**: Realistic fill modeling
- **Position limits**: Respects `max_position` and `max_notional`
- **Liquidity checks**: Only quotes when sufficient market depth

### 3. Configurable Threshold

```json
{
  "ADNOCGAS": {
    "quote_size": 65000,
    "refill_interval_sec": 5,
    "max_position": 130000,
    "stop_loss_threshold_pct": 2.0
  }
}
```

## When Stop-Loss Triggers

### Example Scenario

1. **Entry**: Buy 65,000 shares @ 3.50 AED
   - Position value: 227,500 AED
   - Stop-loss threshold: 227,500 × 2% = 4,550 AED

2. **Price Drops**: Market falls to 3.43 AED
   - Unrealized P&L: (3.43 - 3.50) × 65,000 = -4,550 AED
   - **Stop-loss triggers!**

3. **Exit**: Sell 65,000 @ 3.43 AED
   - Realized loss: -4,550 AED
   - Position: 0

### Benefits of Stop-Loss

1. **Limits Maximum Loss**: No single position can lose more than 2% of its value
2. **Preserves Capital**: Cuts losers early, allows winners to run
3. **Reduces Drawdown**: Smaller peak-to-trough declines
4. **Improves Sharpe**: Better risk-adjusted returns

## Configuration

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quote_size` | int | 65000 | Shares to quote per side |
| `refill_interval_sec` | int | 5 | Cooldown after fills (seconds) |
| `max_position` | int | 130000 | Maximum inventory (shares) |
| `max_notional` | int | 1500000 | Max dollar exposure (AED) |
| `min_local_currency_before_quote` | int | 13000 | Minimum liquidity (AED) |
| `stop_loss_threshold_pct` | float | 2.0 | Stop-loss trigger (%) |

### Tuning Stop-Loss Threshold

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| 1.0% | Very tight, frequent exits | High volatility, risk-averse |
| 2.0% | Balanced (default) | Normal market conditions |
| 3.0% | Looser, fewer exits | Low volatility, higher conviction |
| 5.0% | Very loose | Long-term positions |

## Code Structure

```
src/strategies/v2_1_stop_loss/
├── __init__.py           # Exports
├── strategy.py           # V2_1StopLossStrategy class
└── handler.py            # create_v2_1_stop_loss_handler()
```

### Key Methods

```python
class V2_1StopLossStrategy(BaseMarketMakingStrategy):
    def check_stop_loss(self, security, current_price, timestamp):
        """Check and execute stop-loss if triggered."""
        
    def generate_quotes(self, security, best_bid, best_ask, timestamp):
        """Generate quote prices (inherits V2 logic)."""
        
    def should_refill_side(self, security, timestamp, side):
        """Check if cooldown expired (inherits V2 logic)."""
```

## Comparison with Other Strategies

### V1 Baseline vs V2.1

| Feature | V1 | V2.1 |
|---------|-----|------|
| Quote Logic | Time-based refill | Price-following + cooldown |
| Stop-Loss | None | 2% threshold |
| Refill Interval | 180s | 5s (configurable) |
| P&L | 697k AED | 1,409k AED |

### V2 vs V2.1

| Feature | V2 | V2.1 |
|---------|-----|------|
| Quote Logic | Price-following | Same |
| Stop-Loss | None | 2% threshold |
| Risk Control | Position limits only | Position limits + stop-loss |
| P&L | 1,319k AED | 1,409k AED |

## Running V2.1

### Single Backtest
```bash
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss
```

### Parameter Sweep
```bash
# Test different intervals
python scripts/fast_sweep.py --intervals 5 10 30 60

# Test different stop-loss thresholds
python scripts/fast_sweep.py --intervals 5 10 --stop-loss 1.0
python scripts/fast_sweep.py --intervals 5 10 --stop-loss 3.0
```

### Compare Strategies
```bash
python scripts/compare_strategies.py v2_price_follow_qty_cooldown v2_1_stop_loss
```

## Output Files

```
output/v2_1_stop_loss/
├── ADNOCGAS_trades.csv      # Per-security trades
├── EMAAR_trades.csv
├── ...
└── backtest_summary.csv     # Aggregate metrics
```

### Trade Log Format
```csv
timestamp,side,fill_price,fill_qty,realized_pnl,position,pnl
2025-01-15 10:05:23,buy,3.50,30000,0.0,30000,0.0
2025-01-15 10:08:41,sell,3.43,30000,-2100.0,0,-2100.0  # Stop-loss exit
```

## Best Practices

### 1. Start with Default 2% Stop-Loss
The 2% threshold is well-tested and provides good balance between risk control and trading activity.

### 2. Use Short Refill Intervals
V2.1 performs best with 5-10 second refill intervals, allowing quick position rebuilding after stop-losses.

### 3. Monitor Stop-Loss Frequency
Too many stop-losses may indicate:
- Threshold too tight (increase to 3%)
- Market too volatile for strategy
- Quote sizes too large

### 4. Combine with Position Limits
Stop-loss works together with `max_position` for layered risk control.

## FAQ

### Q: Does stop-loss trigger during auctions?
No, stop-loss only triggers during regular trading hours (10:00-14:45).

### Q: What price is used for stop-loss exit?
The current market trade price at the time of trigger.

### Q: Can I disable stop-loss?
Set `stop_loss_threshold_pct` to a very high value (e.g., 100.0).

### Q: Does stop-loss reset the refill timer?
Yes, the exit trade resets the cooldown timer like any other fill.

## Related Documentation

- [V2 Price-Follow Strategy](../v2_price_follow_qty_cooldown/README.md)
- [Fill/Refill Logic Explained](../../../FILL_REFILL_LOGIC_EXPLAINED.md)
- [Parameter Sweep Guide](../../../PARAMETER_SWEEP_GUIDE.md)
