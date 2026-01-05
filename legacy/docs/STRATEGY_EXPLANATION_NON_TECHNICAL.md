# Market-Making Strategy - Non-Technical Explanation

## What is This Strategy?

This is an automated market-making trading strategy that acts like a digital liquidity provider in financial markets. Think of it as an automated trader that continuously offers to both **buy** and **sell** securities, profiting from the difference between the two prices (the "spread").

---

## Core Concept: What is Market-Making?

Imagine you run a currency exchange booth at an airport:
- You offer to **buy** dollars at 3.65 AED per dollar
- You offer to **sell** dollars at 3.67 AED per dollar
- When someone trades with you, you make 0.02 AED per dollar

This strategy does the same thing electronically in stock markets, continuously posting buy and sell prices and collecting small profits from the spread.

---

## How the Strategy Works

### 1. **Quoting Both Sides**

The strategy looks at the current market prices:
- **Best Bid** (highest price someone wants to buy at)
- **Best Ask** (lowest price someone wants to sell at)

Then it joins these queues by placing its own orders:
- **Places a BUY order** at the best bid price
- **Places a SELL order** at the best ask price

**Example:**
- Market shows: Best Bid = 3.50, Best Ask = 3.52
- Strategy joins: Bids 3.50 to buy 65,000 shares, Asks 3.52 to sell 65,000 shares

### 2. **Making Money from the Spread**

When both sides execute:
- Buys at 3.50 (spends 227,500 AED)
- Sells at 3.52 (receives 228,800 AED)
- **Profit: 1,300 AED** (roughly 0.57% return)

This happens repeatedly throughout the day, accumulating many small profits.

### 3. **Position Limits (Risk Control)**

The strategy doesn't keep buying or selling indefinitely. It has limits:

**Max Position Limit:** Each security has a maximum inventory (e.g., 130,000 shares)
- If already holding +130,000 shares (long), won't buy more
- If already short -130,000 shares, won't sell more

This prevents building up dangerous one-sided positions.

**Max Notional Limit:** Also limits based on dollar value (1.5M AED)
- Prevents over-exposure in high-priced stocks
- Automatically adjusts position limits based on current prices

### 4. **The "Stickiness" Timer (Refill Interval)**

This is critical to the strategy's success.

**Problem:** If quotes update every second, they never stay in the queue long enough to get filled.

**Solution:** Once the strategy places a quote, it **"sticks"** at that price for 180 seconds (3 minutes)
- Even if the market moves, the quote stays at the original price
- This gives time to accumulate queue priority
- Market orders that come in can execute against our resting quotes

**Analogy:** Like standing in a coffee shop line - if you keep jumping to different lines, you never get served. But if you stay in one line, you eventually reach the front.

### 5. **Liquidity Check (Safety Gate)**

Before placing quotes, the strategy checks if there's enough liquidity ahead:

**Minimum Liquidity Requirement:** Each security requires a certain amount (e.g., 13,000 AED) already at that price level

**Why?** This prevents:
- Being "the only one" at a price (first in line = highest risk)
- Getting picked off by informed traders
- Providing liquidity when there's no natural flow

**Example for ADNOCGAS:**
- If only 2,000 AED worth ahead at best bid → DON'T quote
- If 50,000 AED worth ahead at best bid → Safe to quote

---

## Trading Schedule (Time Windows)

The strategy is **selective** about when it trades:

### Active Trading Hours:
**10:05 AM - 2:45 PM** - Normal market-making operations

### Blocked Periods:

1. **Opening Auction (9:30 - 10:00 AM)**
   - Market is unstable during opening
   - Prices can jump dramatically
   - Strategy stays out to avoid getting caught

2. **Silent Period (10:00 - 10:05 AM)**
   - 5-minute buffer after opening
   - Lets market settle down
   - No trading activity

3. **Closing Auction (2:45 - 3:00 PM)**
   - Similar volatility at market close
   - Strategy exits before the chaos

4. **End-of-Day Flatten (2:55 PM)**
   - **Forces all positions to zero**
   - Sells any long positions
   - Buys back any short positions
   - **No overnight risk** - starts fresh every day

---

## Queue Simulation (How Fills Happen)

The strategy simulates realistic order execution:

### Queue Priority System:

When placing a quote at best bid/ask, the strategy tracks:
1. **Quantity ahead** in queue (other orders placed before ours)
2. **Our quantity** (our order size)

### Execution Logic:

When a market trade occurs:
1. First, consume the "ahead quantity" (others get filled first)
2. Then, if trade is large enough, our order gets filled
3. Update our remaining quantity

**Example:**
- We place 65,000 bid at 3.50
- There's 80,000 ahead of us
- Market sell order of 120,000 comes in
  - First 80,000 fills others → removes queue ahead
  - Next 40,000 fills us → we buy 40,000 shares
  - Our remaining: 25,000 still in queue

This creates realistic partial fills, not instantaneous all-or-nothing execution.

---

## Risk Management Features

### 1. **Symmetric Two-Sided Quoting**
- Always quotes both bid and ask when possible
- Reduces directional risk
- Captures spread from both directions

### 2. **Position Limits**
- Hard caps on long/short exposure
- Automatically stops quoting when limits reached
- Prevents runaway positions

### 3. **Daily Reset**
- Flattens everything at end of day
- No overnight gap risk
- Fresh start each trading day

### 4. **Liquidity Requirements**
- Won't quote if not enough volume ahead
- Avoids being isolated at price levels
- Reduces adverse selection risk

### 5. **Auction Avoidance**
- Skips volatile opening/closing periods
- Reduces price shock risk
- Focuses on stable mid-day trading

---

## Performance Metrics

The strategy tracks several key metrics:

### Per-Trade Level:
- **Side** (buy or sell)
- **Fill Price** (execution price)
- **Fill Quantity** (shares traded)
- **Realized P&L** (profit/loss from closing positions)
- **Position** (current inventory after trade)
- **Cumulative P&L** (total profit so far)

### Daily Level:
- **Trading Days** (days strategy executed trades)
- **Coverage** (% of market days we traded)
- **Total Trades** (volume of activity)

### Overall Performance:
- **Total P&L** (accumulated profits)
- **Win Rate** (% of profitable securities)
- **Total Volume** (AED traded)

---

## Real Results from the Backtest

### Overall Performance (136 trading days):
- **Total Trades**: 142,917
- **Total Volume**: 1.76 Billion AED (~$480M USD)
- **Total Profit**: 697,123 AED (~$190K USD)
- **Trading Coverage**: 100% (traded every available day)

### Top Performers:
1. **EMAAR**: +312,211 AED (11,903 trades)
2. **ADNOCGAS**: +171,213 AED (6,529 trades)
3. **TALABAT**: +119,067 AED (5,686 trades)

### Key Success Factors:
- High-frequency trading (1,050 trades per day on average)
- Capturing small spreads repeatedly
- Maintaining market presence across all securities
- Effective risk management (no catastrophic losses)

---

## Why This Strategy Works

### 1. **Market Inefficiency**
- There's always a spread between bid and ask
- Strategy captures this spread repeatedly
- Small profits add up over thousands of trades

### 2. **Queue Priority**
- By "sticking" at prices for 180 seconds
- Accumulates queue position
- Gets filled by natural market flow

### 3. **Risk Control**
- Position limits prevent large losses
- Daily flattening eliminates overnight risk
- Liquidity checks avoid dangerous situations

### 4. **Consistency**
- 100% coverage means no missed opportunities
- Operates systematically without emotion
- Executes the same logic every day

---

## Key Takeaways

1. **Market-making is about volume, not home runs**
   - Many small wins, not one big score
   - Consistency is more valuable than occasional large profits

2. **The "stickiness" timer was the breakthrough**
   - Previous version requoted too often
   - Quotes never stayed long enough to get filled
   - 180-second cooldown allowed natural fills

3. **Risk management is paramount**
   - Position limits prevent disasters
   - Daily flattening eliminates overnight risk
   - Auction avoidance reduces volatility exposure

4. **Technology enables scale**
   - Processes 100,000 rows per second
   - Monitors 16 securities simultaneously
   - Executes 1,000+ trades per day automatically

5. **Data quality matters**
   - Understanding that data was "best bid/ask updates" not "full orderbook"
   - This insight fixed 55% → 100% coverage issue
   - Technical details have massive impact on results

---

## Conclusion

This market-making strategy is essentially an automated liquidity provider that:
- Continuously offers to buy and sell at current market prices
- Profits from the bid-ask spread
- Manages risk through position limits and daily resets
- Operates systematically across multiple securities
- Generates consistent returns through high-frequency small profits

The strategy's success comes from combining classical market-making principles with modern technology, allowing it to operate at scale while maintaining strict risk controls.
