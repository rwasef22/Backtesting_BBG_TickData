# V2.1 Stop-Loss Strategy - Non-Technical Explanation

## What This Strategy Does

Imagine you're a market maker at a grocery store. You buy apples wholesale and sell them retail, making money on the difference. But sometimes, apple prices crash and you're stuck with inventory worth less than you paid.

**V2.1 is like having a rule: "If I'm losing more than 2% on my apple inventory, sell everything immediately to stop the bleeding."**

## The Problem V2.1 Solves

Without stop-loss protection:
- Bad trades can keep getting worse
- One big loss can wipe out many small wins
- Capital gets tied up in losing positions

With V2.1's stop-loss:
- Losses are capped at 2% per position
- Capital is freed to find better opportunities
- Small losses don't become big losses

## How It Works

### Step 1: Normal Trading
V2.1 works just like V2 most of the time:
- Offers to buy shares at the current best price buyers are paying
- Offers to sell shares at the current best price sellers are accepting
- Makes money when it buys low and sells high

### Step 2: The Stop-Loss Check
Every time there's a trade in the market, V2.1 asks:
> "Am I losing more than 2% on my current position?"

### Step 3: Emergency Exit
If the answer is yes:
1. Immediately sell (or buy back) the entire position
2. Accept the 2% loss
3. Start fresh with clean slate

## Real Example

### Without Stop-Loss (V2)
```
Day 1: Buy 65,000 shares at 3.50 AED
Day 1: Price drops to 3.40 AED (2.9% loss)
       → Keep holding, hoping for recovery
Day 2: Price drops to 3.30 AED (5.7% loss)
       → Still holding...
Day 3: Finally sell at 3.35 AED (4.3% loss)

Result: -9,750 AED loss (4.3% × 65,000 × 3.50)
```

### With Stop-Loss (V2.1)
```
Day 1: Buy 65,000 shares at 3.50 AED
Day 1: Price drops to 3.43 AED (2.0% loss)
       → STOP-LOSS TRIGGERS
       → Immediately sell at 3.43 AED

Result: -4,550 AED loss (2% × 65,000 × 3.50)
Savings: 5,200 AED saved vs holding
```

## Why 2%?

The 2% threshold is a balance:

**Too Tight (1%)**
- Gets triggered by normal market noise
- Sells positions that would have recovered
- Too much trading = higher costs

**Too Loose (5%)**
- Lets losses grow too large
- Defeats the purpose of stop-loss
- Big drawdowns still happen

**Just Right (2%)**
- Catches real problems, not noise
- Limits losses effectively
- Good balance of protection vs activity

## The Results

Comparing V2 (no stop-loss) vs V2.1 (with 2% stop-loss):

| What | V2 | V2.1 | Winner |
|------|-----|------|--------|
| Total Profit | 1,319,148 AED | 1,408,864 AED | V2.1 (+6.8%) |
| Worst Day | -664,129 AED | -648,422 AED | V2.1 (less bad) |
| Risk-Adjusted Returns | 14.19 | 14.96 | V2.1 (+5.4%) |

**V2.1 makes more money AND takes less risk.**

## Common Questions

### "Doesn't selling at a loss lock in losses?"
Yes, but small locked losses are better than large unlocked ones. The math shows V2.1 makes more money overall because it:
- Avoids catastrophic losses
- Frees capital to re-enter at better prices
- Keeps winning trades, cuts losing trades

### "What if the price recovers right after stop-loss?"
This happens sometimes. But more often, the price keeps falling. On average, cutting losses early works better.

### "Can I change the 2% threshold?"
Yes! You can set any percentage in the configuration. Lower = more protection, higher = less trading.

### "Does V2.1 stop-loss during auctions?"
No. Stop-loss only triggers during regular trading hours (10:00 AM - 2:45 PM).

## When to Use V2.1

✅ **Use V2.1 when:**
- You want automatic risk management
- You prefer smaller, consistent returns over big swings
- You're running the strategy unattended

⚠️ **Consider V2 when:**
- You have high conviction about recovery
- You're closely monitoring positions
- Markets are unusually volatile (stop-losses trigger too often)

## Summary

V2.1 is V2 with a safety net. It does everything V2 does, plus automatically sells positions when losses hit 2%. This simple rule:

- **Increases total profits** by 6.8%
- **Reduces worst losses** by 2.4%
- **Improves risk-adjusted returns** by 5.4%

It's currently the **best-performing strategy** in our backtest framework.

## Running V2.1

```bash
# Simple way
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss

# Compare with V2
python scripts/fast_sweep.py --intervals 5 10 30 60
```

## See Also

- [V2 Strategy Explanation](../v2_price_follow_qty_cooldown/NON_TECHNICAL_EXPLANATION.md) - The base strategy without stop-loss
- [Strategy Comparison](../../../STRATEGY_SUMMARY.md) - How all strategies compare
