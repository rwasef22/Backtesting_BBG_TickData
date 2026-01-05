# V2 Price-Follow Strategy - Non-Technical Explanation

## What Is Market Making?

Imagine you run a currency exchange booth at an airport. You buy dollars from travelers at one price (say $0.98) and sell them at another price ($1.02). The difference—4 cents per dollar—is your profit.

**Market making works the same way:**
- You offer to BUY shares at one price (the "bid")
- You offer to SELL shares at a slightly higher price (the "ask")
- When both trades complete, you pocket the difference

## How V2 Works

### The Price-Following Part

Traditional market makers (like V1) set their prices and stick with them. V2 is different—it **follows the market**.

Think of it like a shop that constantly updates its prices to match competitors:

```
10:00 - Best price in market is 3.50
        V2 offers to buy at 3.50

10:01 - Market moves, best price is now 3.52
        V2 immediately updates: buy at 3.52

10:02 - Market moves again to 3.55
        V2 updates again: buy at 3.55
```

**Why does this help?**
- Your prices are always competitive
- More customers choose you (more trades)
- You capture every market opportunity

### The Cooldown Part

After V2 makes a trade, it pauses briefly before making new offers. This is like a shopkeeper taking a moment to update their inventory after a sale.

```
10:00:00 - V2 is ready to trade
10:00:15 - Someone buys from V2
           V2 pauses for 5 seconds (cooldown)
10:00:20 - V2 is ready to trade again
```

**Why pause?**
- Prevents over-trading
- Gives time to assess the new position
- Keeps trading controlled

## V1 vs V2: A Day in the Life

### V1 Baseline (The Slow Trader)

```
9:00 AM  - V1 sets buy price at 3.50
           "I'll wait here for 3 minutes"

9:01 AM  - Market moves to 3.52
           V1 says "I'm still offering 3.50"
           Nobody wants to sell at 3.50 when market is 3.52

9:02 AM  - Market moves to 3.55
           V1 still offering 3.50
           Still no trades

9:03 AM  - V1's timer expires
           Now V1 updates to 3.55
           Finally competitive!
```

### V2 Price-Follow (The Quick Trader)

```
9:00 AM  - V2 sets buy price at 3.50
           Ready to trade immediately

9:01 AM  - Market moves to 3.52
           V2 immediately updates to 3.52
           Gets a trade!
           Pauses 5 seconds

9:01:05  - Ready again at market price 3.54
           Gets another trade!
```

## Why V2 Makes More Money

### More Trades
V2 trades about **2.5x more often** than V1:

| Strategy | Total Trades | 
|----------|--------------|
| V1 (180s) | 106,826 |
| V2 (5s) | 283,309 |

### Consistent Small Profits

Each trade makes a small profit. More trades = more profit:

```
V1: 106,826 trades × ~6.5 AED average = 697,542 AED
V2: 283,309 trades × ~4.7 AED average = 1,319,148 AED
```

Even though V2 makes less per trade, the higher volume wins.

## The Numbers

| What | V1 | V2 | Winner |
|------|-----|-----|--------|
| Total Profit | 697,542 AED | 1,319,148 AED | V2 (+89%) |
| Number of Trades | 106,826 | 283,309 | V2 (+165%) |
| Risk-Adjusted Returns | 12.70 | 14.19 | V2 (+12%) |

## When to Use V2

### ✅ Use V2 when:
- Markets are active and liquid
- You want more trading activity
- You're comfortable with higher trade volume

### ⚠️ Consider V1 when:
- Markets are slow/illiquid
- You want fewer, larger trades
- Transaction costs are high

### 🌟 Consider V2.1 when:
- You want V2's benefits PLUS automatic loss protection
- You want the best overall performance
- You prefer "set and forget" operation

## Common Questions

### "Why not always follow the market?"
V2 does always follow—but only when it's safe to trade. It still checks:
- Position limits (don't get too big)
- Liquidity (enough volume in market)
- Time windows (no trading during auctions)

### "What if the market moves against me?"
V2 doesn't have built-in protection for this. That's why V2.1 was created—it adds a "stop-loss" that automatically sells if losses get too big.

### "Is faster always better?"
For this market, yes. The 5-second interval beats longer ones:

| Interval | Profit |
|----------|--------|
| 5 seconds | 1,319,148 AED |
| 10 seconds | 1,273,433 AED |
| 30 seconds | 1,156,847 AED |
| 60 seconds | 1,042,563 AED |

### "Why is it called 'qty-cooldown'?"
"Qty" means quantity—the cooldown happens after we trade a quantity (get filled). The name distinguishes it from time-based cooldowns.

## Summary

V2 is like a shopkeeper who:
1. **Always matches competitor prices** (price-following)
2. **Takes a brief pause after each sale** (cooldown)
3. **Makes money through volume** (many small trades)

It makes **89% more money** than V1 by trading **165% more often** at always-competitive prices.

## Running V2

```bash
# Simple way
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown

# Compare with V1
python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown

# Compare V2 vs V2.1 (with stop-loss)
python scripts/fast_sweep.py --intervals 5 10 30 60
```

## See Also

- [V2.1 Stop-Loss](../v2_1_stop_loss/NON_TECHNICAL_EXPLANATION.md) - V2 with added protection
- [V1 Baseline](../v1_baseline/NON_TECHNICAL_EXPLANATION.md) - The reference strategy
- [Strategy Summary](../../../STRATEGY_SUMMARY.md) - All strategies compared
