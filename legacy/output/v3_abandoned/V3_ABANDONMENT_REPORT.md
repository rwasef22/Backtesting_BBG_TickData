# V3 Liquidity Monitor Strategy - Abandonment Report

**Date:** December 30, 2025  
**Status:** ABANDONED  
**Reason:** Poor Performance Compared to V1 and V2

---

## Executive Summary

The V3 Liquidity Monitor strategy was developed to extend V2 with continuous orderbook depth monitoring. After comprehensive testing across 6 intervals (10s, 30s, 60s, 120s, 300s, 600s) on all 16 securities, V3 was **abandoned due to significantly inferior performance** compared to both V1 (Baseline) and V2 (Price Follow Qty Cooldown) strategies.

---

## Performance Comparison

### Best Configuration (30s Interval)

| Metric | V1 | V2 | V3 | V3 vs V1 | V3 vs V2 |
|--------|----|----|----|---------:|----------:|
| **Total P&L** | 967,934 AED | 1,119,660 AED | 157,376 AED | **-84%** | **-86%** |
| **Sharpe Ratio** | 11.98 | 13.62 | 4.05 | **-66%** | **-70%** |
| **Max Drawdown** | -3.65% | -2.91% | -20.95% | **+474%** | **+620%** |
| **Total Trades** | 132,936 | 252,238 | 11,155 | **-92%** | **-96%** |
| **Win Rate** | 28.0% | 23.7% | 26.1% | -7% | +10% |

### Full Interval Comparison

| Interval | V1 P&L | V2 P&L | V3 P&L | V3 Performance |
|----------|-------:|-------:|-------:|----------------|
| 10s | 998,981 | 1,242,332 | 147,951 | **-85% vs V1** |
| 30s | 967,934 | 1,119,660 | 157,376 | **-84% vs V1** |
| 60s | 737,547 | 1,016,197 | 149,649 | **-80% vs V1** |
| 120s | 776,390 | 797,757 | 148,877 | **-81% vs V1** |
| 300s | 437,534 | 524,575 | 148,635 | **-66% vs V1** |
| 600s | 271,929 | 303,405 | 151,510 | **-44% vs V1** |

---

## Key Problems Identified

### 1. **Massive P&L Underperformance**
- V3 generated only **13-16% of V1's P&L** across all intervals
- Even at V1's worst interval (600s), V3 underperformed by 44%
- Consistent ~150k AED P&L regardless of interval suggests overly conservative trading

### 2. **Severely Reduced Trading Activity**
- V3 executed **92-96% fewer trades** than V1/V2
- Average ~11,000 trades vs 100k-250k for V1/V2
- Liquidity monitoring was too restrictive, missing profitable opportunities

### 3. **Higher Risk Profile**
- Max drawdown of **-20% to -23%** vs V1/V2's typical -3% to -5%
- Fewer trades concentrated risk rather than diversifying it
- Lower Sharpe ratios (3.7-4.0 vs 10-15 for V1/V2)

### 4. **Inconsistent with Strategy Goal**
- Goal: Improve upon V2 by monitoring depth continuously
- Result: Withdrew quotes too aggressively, missing market-making opportunities
- The liquidity threshold check proved counterproductive

---

## Technical Analysis

### V3 Strategy Logic (What Failed)

```python
def should_activate_quote(self, side: str, orderbook, ahead_qty: float) -> bool:
    """Check if quote should be active based on liquidity at our price."""
    
    # Get current best bid/ask
    best_bid = orderbook.get_best_bid()
    best_ask = orderbook.get_best_ask()
    
    # Check liquidity at the price where we'd quote
    qty_at_level, local_value = self.check_liquidity_at_price(
        orderbook, 
        best_bid if side == 'bid' else best_ask,
        ahead_qty
    )
    
    # PROBLEM: This threshold was too high, causing excessive quote withdrawal
    return local_value >= self.min_local_currency_before_quote
```

**Root Cause:**
- The `min_local_currency_before_quote` threshold (6,460 AED for EMAAR) was met too infrequently
- V3 withdrew quotes when depth fell below threshold, but depth fluctuates constantly
- By the time depth returned, price had moved and opportunity was lost
- V2's simpler "check once at quote generation" approach proved superior

### Performance Timeline (EMAAR @ 30s)

| Strategy | Trades | Final P&L | Sharpe |
|----------|-------:|----------:|-------:|
| V3 Test (initial) | 234 | 48,821 | 4.35 |
| V3 Full Sweep | 11,155 | 157,376 | 4.05 |

Even the initial positive test on EMAAR didn't translate to strong overall performance.

---

## Conclusion

**V3 is abandoned** in favor of continuing with V1 and V2 strategies. The continuous liquidity monitoring approach:

1. ✗ Reduced trading frequency by >90%
2. ✗ Decreased P&L by 80-85%
3. ✗ Increased drawdowns by 5-7x
4. ✗ Lowered risk-adjusted returns (Sharpe ratio)

**V2 remains the best performing strategy** with strong P&L, excellent Sharpe ratios, and manageable drawdowns.

---

## Files Preserved

All V3 test results and analysis have been preserved in this folder:

- `emaar_trades_timeseries.csv` - Original EMAAR 30s test trades
- `v3_comprehensive_analysis.png` - Initial test analysis
- `v3_cumulative_pnl_detailed.png` - Detailed P&L visualization
- Comprehensive sweep results available in `../comprehensive_sweep/`

---

## Recommendations

1. **Continue with V2** as the primary strategy
2. **Use V1 as baseline** for comparison
3. **Do not revisit V3** without fundamental redesign of liquidity monitoring logic
4. Future enhancements should focus on:
   - V2 parameter optimization
   - Alternative cooldown mechanisms
   - Multi-level quoting strategies
   - NOT continuous liquidity monitoring

---

**Report Generated:** December 30, 2025  
**Decision:** Strategy V3 is permanently retired from production consideration
