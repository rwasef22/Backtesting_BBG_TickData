# Market Making Backtest - Strategy Summary

## Overview

This document summarizes all strategies in the tick-backtest framework, their performance characteristics, and recommendations for use.

## Strategy Performance Ranking

| Rank | Strategy | P&L (AED) | Sharpe | Status |
|------|----------|-----------|--------|--------|
| 1  | V2.1 Stop-Loss @ 5s | 1,408,864 | 14.96 | **BEST - RECOMMENDED** |
| 2 | V2 Price-Follow @ 5s | 1,319,148 | 14.19 | Active |
| 3 | V1 Baseline @ 180s | 697,542 | 12.70 | Reference |
| 4 | V3 Liquidity Monitor | ~400,000 | 8.50 | **ABANDONED** |

## Active Strategies

### V2.1: Stop-Loss Strategy  RECOMMENDED
**Status:** Active - **BEST PERFORMING**  
**Best Interval:** 5s (Sharpe: 14.96, P&L: 1,408,864 AED)

**Key Features:**
- All V2 features (price-following, cooldown after fills)
- **2% stop-loss protection** automatically exits losing positions
- +6.8% higher P&L than V2
- Lower maximum drawdown (-648k AED vs -664k AED)
- Better risk-adjusted returns

**Configuration:**
```json
{
  "quote_size": 65000,
  "refill_interval_sec": 5,
  "stop_loss_threshold_pct": 2.0
}
```

**Run Command:**
```bash
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss
```

### V2: Price Follow Qty Cooldown
**Status:** Active - Second best performer  
**Best Interval:** 5s (Sharpe: 14.19, P&L: 1,319,148 AED)

**Key Features:**
- Continuous price following (quotes at best bid/ask)
- Cooldown timer resets on fills (not quote placement)
- 2.5x more trades than V1
- Best for short intervals (5-10s)

**Run Command:**
```bash
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown
```

### V1: Baseline Strategy
**Status:** Active - Reference implementation  
**Best Interval:** 180s (Sharpe: 12.70, P&L: 697,542 AED)

**Key Features:**
- Time-based quote refresh (fixed interval)
- Conservative approach with longer cooldowns
- Fewer trades, higher profit per trade
- Good reference for new strategies

**Run Command:**
```bash
python scripts/run_parquet_backtest.py --strategy v1_baseline
```

## Abandoned Strategies

### V3: Liquidity Monitor
**Status:** ABANDONED (December 30, 2025)  
**Reason:** Poor performance - 70% lower P&L than V2

**Key Issues:**
- Only ~30% of V2's P&L
- 92-96% fewer trades (too restrictive)
- Higher drawdowns
- Lower Sharpe ratios

**Root Cause:** Continuous liquidity monitoring withdrew quotes too aggressively when orderbook depth fluctuated, missing profitable opportunities.

**Documentation:** See `output/v3_abandoned/V3_ABANDONMENT_REPORT.md`

## Detailed Comparison

### V2 vs V2.1 (Latest Sweep - Jan 2026)

| Metric | V2 @ 5s | V2.1 @ 5s | Difference |
|--------|---------|-----------|------------|
| **Total P&L** | 1,319,148 AED | 1,408,864 AED | +89,716 (+6.8%) |
| **Sharpe Ratio** | 14.19 | 14.96 | +0.77 (+5.4%) |
| **Max Drawdown** | -664,129 AED | -648,422 AED | +15,707 (-2.4%) |
| **Total Trades** | 283,309 | 283,781 | +472 |
| **Win Rate** | 23.55% | 23.64% | +0.09pp |

**Conclusion:** V2.1 is strictly better than V2 - higher returns, lower risk.

### All Strategies Compared

| Metric | V1 @ 180s | V2 @ 5s | V2.1 @ 5s | V3 @ 30s |
|--------|-----------|---------|-----------|----------|
| **P&L** | 697,542 | 1,319,148 | 1,408,864 | ~400,000 |
| **Sharpe** | 12.70 | 14.19 | 14.96 | 8.50 |
| **Trades** | 106,826 | 283,309 | 283,781 | ~12,000 |
| **Max DD** | -664k | -664k | -648k | ~-800k |

## Recommendations

### For Production Use
**Use V2.1 Stop-Loss @ 5s interval**
- Highest returns
- Best risk-adjusted performance
- Automatic loss protection
- Well-tested and documented

### For Development/Testing
**Use V1 Baseline**
- Simple, well-understood logic
- Good reference for comparing new strategies
- Easier to debug

### For Parameter Optimization
```bash
# Quick test (5 securities)
python scripts/fast_sweep.py --intervals 5 10 30 60 --max-sheets 5

# Full sweep
python scripts/fast_sweep.py --intervals 5 10 30 60
```

## Interval Recommendations by Strategy

| Strategy | Optimal | Acceptable | Avoid |
|----------|---------|------------|-------|
| V2.1 | 5s | 5-30s | >60s |
| V2 | 5s | 5-30s | >60s |
| V1 | 180s | 120-300s | <60s |

## Quick Reference Commands

```bash
# Best performer (V2.1)
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss

# Second best (V2)
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown

# Baseline (V1)
python scripts/run_parquet_backtest.py --strategy v1_baseline

# Compare V2 vs V2.1
python scripts/fast_sweep.py --intervals 5 10 30 60

# Compare all strategies
python scripts/compare_strategies.py --all
```

## Documentation Links

- [V2.1 Strategy Documentation](docs/strategies/v2_1_stop_loss/README.md)
- [V2 Strategy Documentation](docs/strategies/v2_price_follow_qty_cooldown/README.md)
- [V1 Strategy Documentation](docs/strategies/v1_baseline/README.md)
- [Scripts Reference](docs/SCRIPTS_REFERENCE.md)
- [Technical Documentation](STRATEGY_TECHNICAL_DOCUMENTATION.md)

## Version History

| Date | Version | Change |
|------|---------|--------|
| Jan 2026 | 2.1 | Added V2.1 stop-loss strategy (new best) |
| Dec 2025 | 2.0 | Added V2 price-follow strategy |
| Dec 2025 | 1.0 | Initial V1 baseline |
| Dec 2025 | 3.0 | V3 liquidity monitor (abandoned) |
