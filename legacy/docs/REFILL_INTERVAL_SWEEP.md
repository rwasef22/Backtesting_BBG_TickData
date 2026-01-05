# Refill Interval Parameter Sweep

## Objective

Test the v1_baseline strategy with different `refill_interval_sec` values to find the optimal parameter that maximizes P&L while maintaining good risk characteristics.

## Methodology

### Parameters Tested

| Interval | Seconds | Minutes | Description |
|----------|---------|---------|-------------|
| 60s | 60 | 1 min | Very aggressive - frequent requotes |
| 120s | 120 | 2 min | Aggressive - more requotes |
| 180s | 180 | 3 min | **Baseline** - current default |
| 300s | 300 | 5 min | Conservative - longer sticking |
| 600s | 600 | 10 min | Very conservative - rare requotes |

### Strategy Configuration

- **Base Strategy**: v1_baseline (time-based refill)
- **All Other Parameters**: Unchanged from default config
- **Securities**: All 16 securities in dataset
- **Data**: Full historical dataset (~673k rows)

### Metrics Compared

1. **Total P&L**: Aggregate realized profit/loss across all securities
2. **Total Trades**: Number of executed trades
3. **Average P&L per Trade**: Total P&L / Total Trades
4. **Average P&L per Security**: Total P&L / Number of Securities
5. **Trading Day Coverage**: % of market days where strategy traded
6. **Total Volume**: Dollar value of all trades

## Hypothesis

**Shorter Intervals (60s, 120s)**:
- **Pros**: More quote updates → more trading opportunities → potentially more P&L
- **Cons**: Lower queue priority → worse fills → potentially worse P&L per trade
- **Expected**: High trade count, lower P&L per trade

**Baseline (180s)**:
- **Current Performance**: +697K AED, 142,917 trades
- **Balanced**: Good queue priority with reasonable update frequency

**Longer Intervals (300s, 600s)**:
- **Pros**: Better queue priority → better fills → potentially higher P&L per trade
- **Cons**: Fewer quote updates → fewer opportunities → potentially lower total P&L
- **Expected**: Lower trade count, higher P&L per trade

## Expected Trade-offs

### Frequency vs Quality Trade-off

```
High Frequency (60s)           Balanced (180s)           High Quality (600s)
    |                              |                           |
    v                              v                           v
More trades                   Good balance               Fewer trades
Lower per-trade profit        Proven results             Higher per-trade profit
Less queue priority           Moderate priority          Best queue priority
```

### Risk Considerations

- **Too Frequent (60s)**: May increase transaction costs, market impact
- **Too Infrequent (600s)**: May miss opportunities, lower coverage
- **Optimal**: Balance between opportunity capture and execution quality

## Running the Sweep

```bash
# Full dataset (all securities)
python scripts/sweep_refill_intervals.py --intervals 60 120 180 300 600

# Quick test (5 securities)
python scripts/sweep_refill_intervals.py --max-sheets 5 --intervals 60 120 180 300 600

# Custom intervals
python scripts/sweep_refill_intervals.py --intervals 30 90 180 360

# Custom output directory
python scripts/sweep_refill_intervals.py --output-dir output/my_sweep
```

## Output Files

### Directory Structure

```
output/parameter_sweep/
├── interval_60s/
│   ├── ADNOCGAS_trades.csv
│   ├── ADCB_trades.csv
│   └── summary.csv
├── interval_120s/
│   └── ...
├── interval_180s/
│   └── ...
├── interval_300s/
│   └── ...
├── interval_600s/
│   └── ...
├── interval_comparison.csv        # Aggregate comparison
└── interval_comparison.png        # Visualization
```

### Comparison CSV

| refill_interval_sec | total_trades | total_pnl | avg_pnl_per_trade | trading_day_coverage |
|---------------------|--------------|-----------|-------------------|----------------------|
| 60 | ? | ? | ? | ? |
| 120 | ? | ? | ? | ? |
| 180 | 142,917 | 697,122 | 4.88 | 98.5% |
| 300 | ? | ? | ? | ? |
| 600 | ? | ? | ? | ? |

## Visualization

The comparison plot includes 6 panels:

1. **Total P&L**: Bar chart showing aggregate P&L by interval
2. **Total Trades**: Bar chart showing trade count by interval
3. **Avg P&L per Trade**: Bar chart showing execution quality
4. **Trading Day Coverage**: Bar chart showing % of days traded
5. **P&L vs Trades**: Scatter plot showing relationship
6. **Avg P&L per Security**: Bar chart showing per-security performance

## Interpretation Guidelines

### Best Overall Interval

- **Highest Total P&L**: Maximizes absolute profit
- **Consider**: Total trades, coverage, risk

### Most Efficient Interval

- **Highest P&L per Trade**: Best execution quality
- **Consider**: May have fewer total trades

### Best Risk-Adjusted

- **Balance**: P&L, trades, and coverage
- **Avoid**: Extreme outliers in any metric

## Next Steps After Sweep

### 1. Identify Optimal Interval

```bash
# Review comparison
cat output/parameter_sweep/interval_comparison.csv

# View visualization
open output/parameter_sweep/interval_comparison.png
```

### 2. Update Configuration

If interval X is best, update `configs/v1_baseline_config.json`:

```json
{
  "ADNOCGAS": {
    ...
    "refill_interval_sec": X,  // Update from 180 to X
    ...
  }
}
```

### 3. Create New Strategy Variation

Consider creating `v2_optimized_refill`:

```bash
# Copy v1_baseline
cp -r src/strategies/v1_baseline src/strategies/v2_optimized_refill

# Update config
cp configs/v1_baseline_config.json configs/v2_optimized_refill_config.json
# Edit refill_interval_sec values

# Run and compare
python scripts/run_strategy.py --strategy v2_optimized_refill
python scripts/compare_strategies.py v1_baseline v2_optimized_refill
```

### 4. Test Per-Security Optimization

Different securities may have different optimal intervals:

```python
# Custom per-security intervals
{
  "ADNOCGAS": {"refill_interval_sec": 180},  # Baseline
  "EMAAR": {"refill_interval_sec": 120},     # More liquid
  "SPINNEYS": {"refill_interval_sec": 300}   # Less liquid
}
```

## Computational Requirements

- **Time per Interval**: ~5-8 minutes
- **Total Time (5 intervals)**: ~25-40 minutes
- **Memory**: ~500MB-1GB
- **Disk Space**: ~500MB for all results

## Validation Checks

After sweep completes:

1. **Sanity Check**: All intervals should produce trades
2. **Consistency**: Coverage should be similar across intervals
3. **Monotonicity**: Not expected - P&L may not increase/decrease monotonically
4. **Baseline Match**: 180s interval should match previous results (~697K AED)

## Statistical Significance

Note: This is a single backtest, not multiple runs. Results are deterministic but represent one market regime. Consider:

- **Market conditions**: Historical period may not repeat
- **Overfitting risk**: Optimal interval on this data may not generalize
- **Validation**: Test on different time periods if available

## Questions to Answer

1. **Is there a clear optimal interval?**
2. **How sensitive is P&L to refill interval?**
3. **Does higher frequency always mean more trades?**
4. **What's the trade-off curve (P&L vs trade count)?**
5. **Are results consistent across securities?**
6. **Should we use different intervals for different securities?**

## Expected Completion

The sweep is currently running and will complete after processing all 16 securities with 5 different interval values. Results will be available in:

- `output/parameter_sweep/interval_comparison.csv`
- `output/parameter_sweep/interval_comparison.png`

## References

- [V1 Baseline Documentation](docs/strategies/v1_baseline/README.md)
- [Multi-Strategy Guide](MULTI_STRATEGY_GUIDE.md)
- [Technical Documentation](docs/strategies/v1_baseline/TECHNICAL_DOCUMENTATION.md)
