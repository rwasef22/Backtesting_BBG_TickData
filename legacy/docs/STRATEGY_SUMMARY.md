# Market Making Backtest - Strategy Summary

## Active Strategies

### V1: Baseline Strategy
**Status:** Active  
**Performance:** Good baseline with consistent results  
**Best Interval:** 10s (Sharpe: 11.92, P&L: 998,981 AED)

### V2: Price Follow Qty Cooldown
**Status:** Active - **BEST PERFORMING**  
**Performance:** Superior to V1 across all metrics  
**Best Interval:** 10s (Sharpe: 14.95, P&L: 1,242,332 AED)  
**Key Features:**
- Continuous price following
- Quantity cooldown mechanism
- Highest P&L and Sharpe ratios
- Lower drawdowns than V1

## Abandoned Strategies

### V3: Liquidity Monitor
**Status:** ABANDONED (December 30, 2025)  
**Reason:** Poor performance - 80-85% lower P&L than V1/V2  

**Key Issues:**
- Only 13-16% of V1's P&L across all intervals
- 92-96% fewer trades (too restrictive)
- Higher drawdowns (-20% to -23% vs -3% to -5%)
- Lower Sharpe ratios (3.7-4.0 vs 10-15)

**Root Cause:** Continuous liquidity monitoring withdrew quotes too aggressively when orderbook depth fluctuated, missing profitable market-making opportunities.

**Documentation:** See `output/v3_abandoned/V3_ABANDONMENT_REPORT.md` for detailed analysis.

## Strategy Comparison (Best Intervals)

| Metric | V1 @ 10s | V2 @ 10s | V3 @ 30s |
|--------|----------|----------|----------|
| **P&L** | 998,981 | 1,242,332 | 157,376 |
| **Sharpe** | 11.92 | 14.95 | 4.05 |
| **Max DD** | -2.30% | -3.40% | -20.95% |
| **Trades** | 106,826 | 269,053 | 11,155 |

**Winner:** V2 by a significant margin

## Recommendation

**Use V2 (Price Follow Qty Cooldown)** as the primary strategy for production deployment. It demonstrates:
- Highest absolute returns
- Best risk-adjusted returns (Sharpe)
- Manageable drawdowns
- Consistent performance across intervals

V1 remains valuable as a baseline for comparison and validation of new strategies.
