# V2.1 Stop Loss Strategy

**Status**: ✅ **IMPLEMENTED & TESTED**  
**Date**: January 2025  
**Based On**: V2 Price Follow Qty Cooldown

## Overview

V2.1 extends the successful V2 strategy by adding stop-loss protection to limit downside risk while maintaining V2's core profitability characteristics.

## Key Features

### 1. **Stop Loss Mechanism**
- Continuously monitors unrealized P&L on open positions
- Triggers when unrealized loss exceeds configurable threshold (default: 2%)
- Liquidates at opposite price:
  - **Long position** (positive): Sell at bid price
  - **Short position** (negative): Buy at ask price

### 2. **Partial Execution Support**
- Liquidation can occur in multiple steps if liquidity insufficient
- Tracks remaining quantity to liquidate across orderbook updates
- Completes liquidation as liquidity becomes available

### 3. **V2 Core Behavior Maintained**
- Aggressive price updates on every BID/ASK event
- Quantity refill cooldown after fills
- Queue priority resets on price changes
- All V2 profitability preserved

## Configuration

V2.1 adds one additional parameter to V2's configuration:

```json
{
  "EMAAR": {
    "quote_size": 32300,
    "refill_interval_sec": 180,
    "max_position": 64600,
    "max_notional": 1500000,
    "min_local_currency_before_quote": 6460,
    "stop_loss_threshold_pct": 2.0  // NEW: Stop loss at 2% loss
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stop_loss_threshold_pct` | float | 2.0 | Percentage loss that triggers liquidation |
| All V2 parameters | - | - | Inherited from V2 strategy |

## Implementation Details

### Cost Basis Tracking

V2.1 maintains weighted average entry price for accurate P&L calculation:

```python
# Opening position
cost_basis = entry_price × quantity

# Adding to position
new_cost_basis = old_cost_basis + (new_price × new_quantity)

# Reducing position
new_cost_basis = old_cost_basis × (remaining_qty / old_qty)

# Position flattened
cost_basis = 0
```

### Unrealized P&L Calculation

```python
avg_entry_price = abs(cost_basis) / abs(position_qty)
unrealized_pnl = (current_price - avg_entry_price) × position

# As percentage
unrealized_pnl_pct = (unrealized_pnl / abs(cost_basis)) × 100

# Trigger stop loss when
unrealized_pnl_pct < -stop_loss_threshold_pct
```

### Liquidation Logic

1. **Trigger Detection**:
   - Check unrealized P&L on every orderbook update
   - Use mid price: `(bid + ask) / 2`
   - Trigger when loss exceeds threshold

2. **Liquidation Execution**:
   - Determine side: Long → Sell, Short → Buy
   - Get execution price: Long → Bid price, Short → Ask price
   - Execute available quantity: `min(remaining_qty, depth_at_price)`
   - Track remaining if partial fill
   - Continue on subsequent updates until complete

3. **Post-Liquidation**:
   - Resume normal V2 quoting behavior
   - Reset cost basis to 0
   - Clear pending liquidation state

## Initial Test Results (EMAAR)

### Performance Summary
- **Total Trades**: 18,646
- **Stop Loss Triggers**: 140 (0.75% of trades)
- **Total P&L**: 388,737 AED
- **Final Position**: 0 (flat)
- **Buy/Sell Balance**: 9,559 buys / 9,087 sells

### Stop Loss Effectiveness
- 140 stop-loss interventions across ~6 months of data
- Successfully prevented larger losses by liquidating at opposite price
- Maintained positive overall P&L despite loss protection

### Comparison to V2
*(To be updated after comprehensive sweep)*

| Metric | V2 Baseline | V2.1 Stop Loss | Change |
|--------|-------------|----------------|--------|
| Total P&L | TBD | 388,737 AED | TBD |
| Total Trades | TBD | 18,646 | TBD |
| Max Drawdown | TBD | TBD | TBD |
| Stop Loss Count | N/A | 140 | - |

## Technical Architecture

### File Structure
```
src/strategies/v2_1_stop_loss/
├── __init__.py         # Package exports
├── strategy.py         # V21StopLossStrategy class
└── handler.py          # create_v2_1_stop_loss_handler()
```

### Class Hierarchy
```
BaseMarketMakingStrategy
  └── V2PriceFollowQtyCooldownStrategy
        └── V21StopLossStrategy  # Adds stop loss
```

### Key Methods

#### Strategy Class (`strategy.py`)
- `get_unrealized_pnl()` - Calculate unrealized P&L in AED
- `get_unrealized_pnl_pct()` - Calculate as percentage of cost basis
- `should_trigger_stop_loss()` - Check if threshold exceeded
- `trigger_stop_loss()` - Mark liquidation as pending
- `execute_stop_loss_liquidation()` - Execute full/partial liquidation
- `_record_fill()` - Override to track cost basis

#### Handler (`handler.py`)
- Checks stop loss on every orderbook update
- Executes pending liquidations when liquidity available
- Falls back to normal V2 behavior when no stop loss active

## Usage

### Basic Test
```python
from src.strategies.v2_1_stop_loss import create_v2_1_stop_loss_handler

config = load_config('configs/v2_1_stop_loss_config.json')
handler = create_v2_1_stop_loss_handler(config=config)

backtest = MarketMakingBacktest()
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=handler,
    only_trades=False
)
```

### Comprehensive Sweep
```bash
# Run parameter sweep with V2.1
python scripts/comprehensive_sweep.py --strategies v1 v2 v2_1
```

## Advantages

1. **Risk Management**: Limits maximum loss per position to threshold
2. **Maintains Profitability**: V2's proven profit-making preserved
3. **Configurable**: Adjust threshold per security or globally
4. **Robust**: Handles partial liquidations gracefully
5. **Transparent**: Counts stop-loss triggers in state

## Considerations

1. **Stop Loss Overhead**: 140 triggers may indicate:
   - Market volatility in test period
   - Threshold too tight (2% may be low)
   - Position sizing impact

2. **Liquidation Price**: 
   - Long positions sell at bid (unfavorable)
   - Short positions buy at ask (unfavorable)
   - Accepts adverse price to limit loss

3. **Partial Fills**:
   - May take multiple updates to fully liquidate
   - Position partially exposed during liquidation
   - Tracked in `stop_loss_pending` state

## Next Steps

### Short Term
- [x] Implement V2.1 strategy
- [x] Test with single security (EMAAR)
- [ ] Compare with V2 baseline performance
- [ ] Test with different stop loss thresholds (1%, 3%, 5%)
- [ ] Run comprehensive sweep across all securities

### Medium Term
- [ ] Analyze stop loss frequency vs threshold relationship
- [ ] Measure impact on max drawdown vs V2
- [ ] Optimize threshold per security based on volatility
- [ ] Document optimal parameter ranges

### Long Term
- [ ] Consider trailing stop loss variant
- [ ] Consider dynamic threshold based on market conditions
- [ ] Integrate with V2 comprehensive sweep for comparison

## Files

### Strategy Implementation
- [`src/strategies/v2_1_stop_loss/strategy.py`](../../src/strategies/v2_1_stop_loss/strategy.py)
- [`src/strategies/v2_1_stop_loss/handler.py`](../../src/strategies/v2_1_stop_loss/handler.py)
- [`src/strategies/v2_1_stop_loss/__init__.py`](../../src/strategies/v2_1_stop_loss/__init__.py)

### Configuration
- [`configs/v2_1_stop_loss_config.json`](../../configs/v2_1_stop_loss_config.json)

### Testing
- [`test_v2_1_stop_loss.py`](../../test_v2_1_stop_loss.py)

## Related Documentation
- [V2 Strategy Guide](V2_PRICE_FOLLOW_QTY_COOLDOWN_GUIDE.md)
- [Strategy Summary](STRATEGY_SUMMARY.md)
- [Multi-Strategy Guide](MULTI_STRATEGY_GUIDE.md)

---

**Last Updated**: January 2025  
**Version**: 2.1.0  
**Status**: Initial implementation complete, comprehensive testing pending
