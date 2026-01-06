# Closing Auction Strategy - Non-Technical Guide

## What Is This Strategy?

This is a **closing auction arbitrage strategy** - a trading approach that takes advantage of predictable price patterns around the market's closing auction.

Think of it like shopping at a store that has a daily clearance sale at closing time. Sometimes prices drop more than they should, and you can buy items that will be worth more tomorrow.

---

## The Simple Idea

### The Pattern We Exploit

Every trading day, the UAE stock market follows this pattern:

1. **During the day**: Stocks trade at various prices based on supply and demand
2. **Near closing (14:30-14:45)**: We calculate the "fair value" (VWAP) based on actual trades
3. **At the closing auction (14:55-15:00)**: A single closing price is determined
4. **Sometimes**: The closing price is significantly different from the fair value
5. **Next day**: Prices tend to move back toward fair value

### Our Approach

We place orders to buy below fair value and sell above fair value. When the closing price is extreme:
- **If it drops too low** → Our buy order fills → We profit when it recovers
- **If it jumps too high** → Our sell order fills → We profit when it falls back

---

## A Day in the Life of This Strategy

### Morning: Cleanup Time (10:00 - 14:30)
> "Did we buy anything yesterday? Let's sell it at a fair price."

If we entered a position at yesterday's closing auction, we spend today looking for a good exit price. We want to sell at or above the fair value we calculated yesterday.

**Safety Feature**: If our position is losing more than 2%, we cut our losses immediately.

### Afternoon: Calculate Fair Value (14:30 - 14:45)
> "What's a fair price for this stock right now?"

We calculate the **VWAP (Volume Weighted Average Price)** - essentially, the average price weighted by how much was traded at each price. This is our reference for what the stock is "worth."

### Pre-Auction: Place Our Orders (14:45)
> "Let's set our traps."

Based on the VWAP, we place two orders:
- **Buy order**: 0.5% below VWAP (we'll only buy if it's a bargain)
- **Sell order**: 0.5% above VWAP (we'll only sell if it's expensive)

### Closing Auction: Wait and See (14:55 - 15:00)
> "Did anyone bite?"

The market determines a single closing price. If this price crosses one of our orders, we get filled:
- Closing price ≤ our buy price → We bought!
- Closing price ≥ our sell price → We sold!

### Tomorrow: Take Profits
> "Mission accomplished."

We exit our position at fair value and pocket the difference.

---

## Real Example

Let's follow a trade in **EMAAR** stock:

### Day 1: Entry
1. **14:30-14:45**: We calculate VWAP = 10.00 AED
2. **14:45**: We place orders:
   - Buy at 9.95 AED (0.5% below VWAP)
   - Sell at 10.05 AED (0.5% above VWAP)
3. **15:00**: Closing auction price = 9.88 AED
4. **Result**: Our buy order at 9.95 fills at 9.88 AED (we got a better price!)
5. **We now own**: 100,000 shares at 9.88 AED

### Day 2: Exit
1. **10:00-14:45**: We look to sell at 10.00 AED (our VWAP reference)
2. **11:30**: Market trades at 10.00 AED
3. **Result**: We sell our shares at 10.00 AED

### Profit Calculation
- **Bought at**: 9.88 AED × 100,000 shares = 988,000 AED
- **Sold at**: 10.00 AED × 100,000 shares = 1,000,000 AED
- **Profit**: 12,000 AED (1.2% return)

---

## Why Does This Work?

### Market Microstructure
The closing auction is a unique trading mechanism where all orders are matched at a single price. This can cause:
- **Price overshoots**: Large orders can push the closing price away from fair value
- **Mean reversion**: Prices tend to return to fair value the next day

### Our Edge
- We're patient: We only trade when prices are favorable
- We're disciplined: We have strict entry and exit rules
- We're protected: Stop-losses limit our downside

---

## Risk Management

### 1. Position Size Limits
We don't bet the farm on any single trade. Each security has a maximum notional value (e.g., 1,000,000 AED), which determines how many shares we trade.

### 2. Stop-Loss Protection (2%)
If our position loses more than 2% of its value, we exit immediately. This prevents small losses from becoming catastrophic.

### 3. Auction Fill Limits (10%)
We don't assume we can fill orders larger than 10% of the total auction volume. This keeps our expectations realistic.

### 4. Daily Cleanup
Any position that isn't exited by end of day is flattened. We don't carry unexpected overnight risk.

---

## Key Parameters Explained

### VWAP Pre-Close Period (15-60 minutes)
How far back we look to calculate fair value.
- **15 minutes**: More responsive to recent price changes
- **60 minutes**: More stable, less affected by short-term noise

### Spread (0.5% - 2%)
How far from fair value we place our orders.
- **0.5%**: Aggressive - more trades, smaller profits per trade
- **2%**: Conservative - fewer trades, larger profits per trade

### Order Notional (in AED)
How much money we're willing to risk per trade.
- **1,000,000 AED**: Moderate position size
- **4,000,000 AED**: Large position size (for liquid stocks)

---

## What Could Go Wrong?

### 1. No Mean Reversion
Sometimes prices don't bounce back. If we buy at a "discount" but the stock keeps falling, we lose money.

**Mitigation**: Stop-loss at 2% limits maximum loss.

### 2. Liquidity Gaps
If trading volume is too low, we might not be able to exit at our target price.

**Mitigation**: Auction fill limits and realistic exit assumptions.

### 3. Market Disruptions
News events, market halts, or unusual volatility can invalidate our VWAP calculations.

**Mitigation**: Daily position cleanup ensures we don't carry unexpected risk.

### 4. Execution Costs
Commissions, fees, and slippage eat into profits.

**Note**: The backtest doesn't include these costs. Real profits would be 5-10 basis points lower.

---

## Performance Summary

Based on 193 trading days of historical data:

| Metric | Value |
|--------|-------|
| Total P&L | ~1,000,000 AED |
| Total Trades | ~10,000 |
| Win Rate | Varies by security |
| Average Trade | ~100 AED |

### Best Performers
- **FAB**: Consistent profits across all configurations
- **EMAAR**: Large, liquid stock with predictable patterns
- **EMIRATES**: Strong mean reversion characteristics

### Challenging Securities
- **EAND**: Inconsistent, often loses money
- **ALDAR**: Sensitive to position sizing

---

## Glossary

**VWAP (Volume Weighted Average Price)**
The average price of a stock, weighted by how much volume traded at each price level. Gives more importance to prices where more shares changed hands.

**Closing Auction**
A period at market close where all orders are collected and matched at a single price. Used to determine the official closing price.

**Mean Reversion**
The tendency of prices to return to their average (or "mean") value over time.

**Stop-Loss**
An automatic order to exit a position when losses reach a certain threshold.

**Notional Value**
The total value of a position in currency terms (shares × price).

**Tick Size**
The minimum price increment for a security. Varies by exchange and price level.

---

## Questions?

This strategy is designed to capture small, consistent profits from predictable market patterns while carefully managing risk. The key to success is patience, discipline, and realistic expectations about execution.
