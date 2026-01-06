# Closing Strategy

## Overview

The Closing Strategy is a **closing auction arbitrage** strategy that exploits the relationship between pre-close VWAP and the closing auction price. It's fundamentally different from the market-making strategies (V1, V2, V2.1) as it trades at specific times rather than continuously.

**Type**: Closing Auction Arbitrage  
**Trading Frequency**: 1-2 trades per day per security  
**Holding Period**: Overnight (entry at close, exit next day)

## Quick Start

```bash
# Run full backtest
python scripts/run_closing_strategy.py

# Quick test with 5 securities
python scripts/run_closing_strategy.py --max-sheets 5

# Custom parameters
python scripts/run_closing_strategy.py --spread 0.3 --vwap-period 20
```

## Strategy Logic

### Phase 1: VWAP Calculation (e.g., 14:30 - 14:45)

During the pre-close period, calculate the Volume-Weighted Average Price (VWAP):

```
VWAP = Σ(Price × Volume) / Σ(Volume)
```

**Configuration**: `vwap_preclose_period_min` (default: 15 minutes before 14:45)

### Phase 2: Auction Order Placement (14:45)

At 14:45, place two orders for the closing auction:

| Order | Price Formula | Example (VWAP=100, spread=0.5%) |
|-------|---------------|----------------------------------|
| Buy | VWAP × (1 - spread) | 100 × 0.995 = 99.50 |
| Sell | VWAP × (1 + spread) | 100 × 1.005 = 100.50 |

Prices are rounded to the nearest tick size.

### Phase 3: Closing Auction Execution (14:55+)

The first trade at or after 14:55 is the closing price. Orders execute if:

- **Buy executes**: Closing price ≤ Buy order price
- **Sell executes**: Closing price ≥ Sell order price

### Phase 4: Next-Day Exit

If we entered at the auction, we place an exit order the next trading day:

- **Entry was Buy** → Place Sell order at VWAP price
- **Entry was Sell** → Place Buy order at VWAP price

Exit execution:
- When price crosses our order price
- Volume determines fill amount (partial fills supported)

## Example Trade

```
Day 1 (14:30-14:45):
  VWAP calculated = 3.50 AED
  
Day 1 (14:45):
  Buy order placed at: 3.50 × 0.995 = 3.4825 → rounded to 3.48
  Sell order placed at: 3.50 × 1.005 = 3.5175 → rounded to 3.52
  
Day 1 (14:55):
  Closing price = 3.45 AED
  3.45 ≤ 3.48 → BUY ORDER EXECUTES
  Entry: Buy 50,000 @ 3.45
  
Day 2 (10:00-14:45):
  Exit order: Sell 50,000 @ 3.50 (VWAP reference)
  Market trades at 3.52 with 60,000 volume
  3.52 ≥ 3.50 → EXIT EXECUTES
  Exit: Sell 50,000 @ 3.52
  
  P&L: (3.52 - 3.45) × 50,000 = 3,500 AED
```

## Configuration

### Per-Security Parameters

```json
{
  "ADNOCGAS": {
    "vwap_preclose_period_min": 15,
    "spread_vwap_pct": 0.5,
    "order_quantity": 65000,
    "tick_size": 0.01,
    "max_position": 130000
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vwap_preclose_period_min` | int | 15 | Minutes before 14:45 to calculate VWAP |
| `spread_vwap_pct` | float | 0.5 | Spread around VWAP (%) |
| `order_quantity` | int | 50000 | Quantity to trade |
| `tick_size` | float | 0.01 | Tick size for price rounding |
| `max_position` | int | 100000 | Maximum position limit |

### Command Line Overrides

```bash
# Override spread for all securities
python scripts/run_closing_strategy.py --spread 0.3

# Override VWAP period for all securities
python scripts/run_closing_strategy.py --vwap-period 20

# Both
python scripts/run_closing_strategy.py --spread 0.3 --vwap-period 20
```

## Output Files

```
output/closing_strategy/
├── {security}_trades.csv    # Per-security trade log
└── backtest_summary.csv     # Aggregate metrics
```

### Trade Log Format

```csv
timestamp,side,price,quantity,realized_pnl,trade_type,vwap_reference,security
2025-01-15 14:55:00,buy,3.45,50000,0.0,auction_entry,3.50,ADNOCGAS
2025-01-16 10:32:15,sell,3.52,50000,3500.0,vwap_exit,3.50,ADNOCGAS
```

### Summary Format

```csv
security,total_trades,auction_entries,vwap_exits,realized_pnl,final_position
ADNOCGAS,24,12,12,43570.50,0
```

## Key Differences from Market-Making

| Aspect | Market-Making (V1/V2/V2.1) | Closing Strategy |
|--------|---------------------------|------------------|
| Trading frequency | Continuous | Once per day |
| Trade trigger | Queue position | Price crossing |
| Holding period | Seconds to minutes | Overnight |
| Risk profile | Inventory risk | Gap risk |
| P&L source | Bid-ask spread | Mean reversion |

## Risk Considerations

### Overnight Gap Risk
Positions are held overnight, exposing to gap risk if news affects prices before exit.

### VWAP Calculation Quality
VWAP quality depends on pre-close volume. Low volume periods may produce unreliable VWAP.

### Execution Uncertainty
Exit orders may not execute if price doesn't cross the target, leading to extended holding periods.

## Parameter Tuning

### Spread (`spread_vwap_pct`)

| Value | Behavior |
|-------|----------|
| 0.25% | Tight - more executions, smaller edge |
| 0.50% | Default - balanced |
| 1.00% | Wide - fewer executions, larger edge |

### VWAP Period (`vwap_preclose_period_min`)

| Value | Behavior |
|-------|----------|
| 5 min | Short - more reactive to recent price |
| 15 min | Default - balanced |
| 30 min | Long - more stable, may miss momentum |

## Related Documentation

- [Scripts Reference](../../SCRIPTS_REFERENCE.md)
- [Market-Making Strategies](../v2_1_stop_loss/README.md)
