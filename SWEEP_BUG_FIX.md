# Parameter Sweep Bug Fix

## Issue
The parameter sweep script ([sweep_refill_intervals.py](scripts/sweep_refill_intervals.py)) was producing 0 trades for all securities and all refill intervals.

## Root Cause
The `run_streaming()` call was missing the `only_trades=False` parameter:

```python
# BEFORE (broken):
results = backtest.run_streaming(
    file_path=data_path,
    handler=handler,
    max_sheets=max_sheets,
    chunk_size=chunk_size
)
```

When `only_trades` is not specified, it defaults to `True`, meaning the data loader only reads rows where `Type='TRADE'`. This excludes all BID and ASK updates.

**Why this breaks the strategy:**
- Market making requires maintaining an orderbook with current best bid/ask prices
- Without BID/ASK updates, the orderbook remains empty  
- With an empty orderbook, the strategy has no reference prices to quote against
- Result: 0 quotes placed = 0 trades executed

## Fix
Added `only_trades=False` to ensure BID/ASK updates are processed:

```python
# AFTER (fixed):
results = backtest.run_streaming(
    file_path=data_path,
    handler=handler,
    max_sheets=max_sheets,
    chunk_size=chunk_size,
    only_trades=False  # CRITICAL: Need bid/ask updates for orderbook
)
```

## Verification
After the fix, the sweep immediately started producing trades:
- **60s interval**: 135,630 trades, +888K AED P&L (first completed interval)
- Matches expected performance from baseline runs

## Lesson Learned
When creating new scripts that use `market_making_backtest.py`, always remember:
- **Passive strategy scanners** (scanning for opportunities): Use `only_trades=True`
- **Market making strategies** (need orderbook): Use `only_trades=False`

The working script ([scripts/run_mm_backtest.py](scripts/run_mm_backtest.py#L48)) had this correct. The new sweep script missed it during creation.
