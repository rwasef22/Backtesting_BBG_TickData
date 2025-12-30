# Comprehensive Parameter Sweep Guide

## Overview

The `comprehensive_sweep.py` script performs parameter sweeps on both V1 and V2 strategies, comparing them across multiple investment metrics including:

- **Basic Metrics**: Total P&L, number of trades, trading volume
- **Risk Metrics**: Sharpe ratio, max drawdown, Calmar ratio
- **Performance Metrics**: Win rate, loss rate, profit factor, avg P&L per trade
- **Activity Metrics**: Trades per day, trading day coverage
- **Visualizations**: Cumulative P&L over time, per-security P&L breakdown

## Key Features

### 1. **Checkpoint System (Interruption-Safe)**
- Automatically saves progress after each completed run
- Can resume from checkpoint if interrupted (Ctrl+C, crash, etc.)
- Checkpoint file: `output/comprehensive_sweep/checkpoint.csv`
- Use `--fresh` flag to ignore checkpoint and start over

### 2. **Advanced Metrics**

#### Sharpe Ratio
- Measures risk-adjusted returns
- Formula: `(Mean Return - Risk-Free Rate) / Std Dev of Returns * √252`
- Higher is better (>1 is good, >2 is excellent)

#### Maximum Drawdown
- Largest peak-to-trough decline in cumulative P&L
- Shows worst-case loss scenario
- Expressed in both absolute (AED) and percentage terms

#### Calmar Ratio
- Annual return divided by maximum drawdown
- Balances return generation with risk control
- Higher is better

#### Win Rate & Loss Rate
- **Win Rate**: Percentage of trades with positive P&L
- **Loss Rate**: Percentage of trades with negative P&L
- Complementary metrics that sum to ~100% (excluding breakeven trades)

#### Profit Factor
- Ratio of gross profits to gross losses
- Value >1 means profitable overall
- Value >2 is considered very good

### 3. **Comprehensive Visualizations**

#### Main Comparison Plot (12 panels)
Creates 12 plots comparing V1 vs V2:
1. Total P&L
2. Total Trades
3. Sharpe Ratio
4. Max Drawdown %
5. Avg P&L per Trade
6. Win Rate
7. Calmar Ratio
8. Profit Factor
9. Trades per Day
10. **Risk-Return Scatter Plot** (with interval labels on each point)
11. Sharpe Ratio Trend Line
12. P&L Trend Line

#### Cumulative P&L by Strategy
- 2 subplots (one for V1, one for V2)
- Each subplot shows cumulative P&L over time
- Different colored line for each refill interval
- Allows visual comparison of strategy performance trajectories

#### Per-Security P&L Plots
- Individual plot for each strategy-interval combination
- Shows cumulative P&L for each security as a separate line
- Helps identify which securities perform best/worst
- 12 plots total (saved in `pnl_by_security_plots/` directory)

## Usage

### Quick Test (5 sheets, 3 intervals) - ~20 minutes
```bash
# Windows PowerShell
cd "c:\Ray\VS Code\tick-backtest-project"
& "C:/Ray/VS Code/tick-backtest-project/.venv/Scripts/python.exe" scripts/comprehensive_sweep.py --max-sheets 5 --intervals 30 60 120

# Linux/Mac
python scripts/comprehensive_sweep.py --max-sheets 5 --intervals 30 60 120
```

### Full Run (All securities, recommended intervals) - ~60-90 minutes
```bash
# Optimal intervals for production analysis
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Extended analysis with more granular intervals
python scripts/comprehensive_sweep.py --intervals 10 20 30 45 60 90 120 180 300 600
```

### Strategy-Specific Runs
```bash
# V1 only
python scripts/comprehensive_sweep.py --strategies v1 --intervals 60 120 180 300 600

# V2 only
python scripts/comprehensive_sweep.py --strategies v2 --intervals 10 30 60 90 120 180
```

### Fresh vs Resume Modes

**Resume from checkpoint (default):**
```bash
# If interrupted, just re-run the same command
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# It will automatically skip completed runs and continue
```

**Start fresh (ignore checkpoint):**
```bash
# Use --fresh flag to start from scratch
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600 --fresh

# This ignores any existing checkpoint and overwrites previous results
```

### Custom Configuration
```bash
python scripts/comprehensive_sweep.py \
  --v1-config configs/v1_baseline_config.json \
  --v2-config configs/v2_price_follow_qty_cooldown_config.json \
  --data data/raw/TickData.xlsx \
  --intervals 30 60 120 180 300 \
  --max-sheets 10 \
  --chunk-size 100000 \
  --output-dir output/my_custom_sweep \
  --fresh
```

## Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--v1-config` | `configs/v1_baseline_config.json` | V1 strategy configuration |
| `--v2-config` | `configs/v2_price_follow_qty_cooldown_config.json` | V2 strategy configuration |
| `--data` | `data/raw/TickData.xlsx` | Path to tick data Excel file |
| `--intervals` | `[30, 60, 120, 180, 300]` | Refill intervals to test (seconds) |
| `--max-sheets` | `None` (all sheets) | Limit number of sheets for testing |
| `--chunk-size` | `100000` | Rows per processing chunk |
| `--output-dir` | `output/comprehensive_sweep` | Output directory |
| `--strategies` | `['v1', 'v2']` | Which strategies to run |
| `--fresh` | `False` | Start fresh, ignoring checkpoint |

### Examples with Arguments

**Quick validation test:**
```bash
python scripts/comprehensive_sweep.py --max-sheets 3 --intervals 60 120 --strategies v1
```

**Full production run with fresh start:**
```bash
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600 --fresh
```

**Resume interrupted run:**
```bash
# Just run without --fresh flag
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600
```

**Custom output location:**
```bash
python scripts/comprehensive_sweep.py --intervals 30 60 120 --output-dir output/sweep_20250129
```

## Output Files

### Main Results

#### 1. `checkpoint.csv`
- Progress checkpoint for resuming interrupted runs
- Contains all completed metric calculations
- Automatically updated after each run completes
- Delete this file or use `--fresh` flag to start over

#### 2. `comprehensive_results.csv`
- All metrics for all runs
- Columns include: strategy, interval, P&L, trades, Sharpe, drawdown, win rate, **loss rate**, etc.
- One row per strategy-interval combination

#### 3. `comparison_table.csv`
- Side-by-side comparison of V1 vs V2 at each interval
- Shows differences (V2 - V1) for key metrics
- Includes win rate and **loss rate** columns
- Also displayed in terminal output with formatted table

#### 4. `comprehensive_comparison.png`
- 12-panel visualization comparing strategies
- High-resolution (150 DPI)
- Risk-return scatter plot includes **interval labels** on each point

#### 5. `cumulative_pnl_by_strategy.png` ⭐ NEW
- 2 subplots: V1 strategy (left) and V2 strategy (right)
- Each subplot shows cumulative P&L over time
- Different colored line for each refill interval
- Helps visualize strategy performance trajectories

#### 6. `per_security_summary.csv`
- Metrics for each security across all runs
- Columns: strategy, interval, security, trades, P&L, Sharpe, drawdown, win rate, etc.
- Enables per-security performance analysis

#### 7. `per_security_pnl_pivot.csv`
- Pivot table with securities as rows
- Columns are strategy-interval combinations
- Values show P&L for easy comparison

### Per-Interval Directories

For each strategy-interval combination (e.g., `v1_30s/`, `v2_120s/`):

#### `{SECURITY}_trades.csv`
Individual trade-level data for each security:
- `timestamp`: Trade execution time
- `side`: 'buy' or 'sell'
- `fill_price`: Execution price
- `fill_qty`: Quantity filled
- `realized_pnl`: P&L from this trade
- `position`: Position after trade
- `pnl`: Cumulative P&L

#### `per_security_summary.csv`
Summary metrics for all securities in this run:
- Security name
- Number of trades
- Total P&L
- Position
- Entry price

### Visualization Directory

#### `pnl_by_security_plots/` ⭐ NEW
Contains 12 plots (one per strategy-interval combo):
- Filename format: `{strategy}_{interval}s_pnl_by_security.png`
- Each plot shows cumulative P&L over time
- Different colored line for each security
- Helps identify best/worst performing securities

**Example files:**
- `v1_10s_pnl_by_security.png`
- `v1_30s_pnl_by_security.png`
- `v2_60s_pnl_by_security.png`
- `v2_300s_pnl_by_security.png`

## Recommended Workflows

### Workflow 1: Quick Exploration (15-30 minutes)
```bash
# Test with limited data to find promising intervals
python scripts/comprehensive_sweep.py \
  --max-sheets 5 \
  --intervals 30 60 120 180 300 600
```
**Best for:** Initial testing, parameter discovery, debugging

### Workflow 2: Full Production Run (60-90 minutes)
```bash
# Full dataset with optimal intervals
python scripts/comprehensive_sweep.py \
  --intervals 10 30 60 120 300 600 \
  --fresh
```
**Best for:** Final analysis, production results, publication

### Workflow 3: Resume After Interruption
```bash
# Simply re-run the same command - it will skip completed runs
python scripts/comprehensive_sweep.py \
  --intervals 10 30 60 120 300 600

# Progress is automatically loaded from checkpoint
# Output will show: "Found X completed runs from checkpoint"
```
**Best for:** Recovering from crashes, system interruptions

### Workflow 4: Fine-Tuning a Strategy
```bash
# Test V2 with narrower interval range
python scripts/comprehensive_sweep.py \
  --strategies v2 \
  --intervals 10 20 30 45 60 75 90 120 150 180 \
  --fresh
```
**Best for:** Optimizing specific strategy, detailed parameter search

### Workflow 5: Comparing Specific Intervals
```bash
# Focus on just a few key intervals
python scripts/comprehensive_sweep.py \
  --intervals 30 60 120 \
  --max-sheets 10 \
  --fresh
```
**Best for:** Quick comparisons, targeted analysis

### Workflow 6: Complete Fresh Restart
```bash
# Delete checkpoint and start over
cd "c:\Ray\VS Code\tick-backtest-project"
Remove-Item "output\comprehensive_sweep\checkpoint.csv" -Force

# Or use --fresh flag
python scripts/comprehensive_sweep.py \
  --intervals 10 30 60 120 300 600 \
  --fresh
```
**Best for:** Starting a new analysis, testing code changes

## Handling Interruptions

The script has robust checkpoint handling for interruptions:

### Automatic Checkpoint Behavior

**When a run completes:**
1. Results are saved to `checkpoint.csv`
2. Per-security files are written to disk
3. Progress is committed before moving to next run

**If interrupted (Ctrl+C, crash, power loss):**
1. All completed runs are preserved in checkpoint
2. Current run-in-progress data is lost
3. Next run will start from last checkpoint

### Resume Strategies

**Method 1: Simple Resume (Recommended)**
```bash
# Just re-run the exact same command
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Output will show:
# Found 7 completed runs from checkpoint
# [8/12] Running V2 - 120s
```

**Method 2: Fresh Start**
```bash
# Use --fresh flag to ignore checkpoint
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600 --fresh

# Output will show:
# Starting fresh sweep (checkpoint ignored)
# Found 0 completed runs from checkpoint
# [1/12] Running V1 - 10s
```

**Method 3: Manual Checkpoint Management**
```bash
# Check checkpoint status
cat output/comprehensive_sweep/checkpoint.csv

# Delete checkpoint to restart
Remove-Item output/comprehensive_sweep/checkpoint.csv

# Run sweep
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600
```

### Example Interruption Scenario

```bash
# Start sweep
$ python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Progress shown:
# [1/12] Running V1 - 10s ✓ Completed
# [2/12] Running V1 - 30s ✓ Completed  
# [3/12] Running V1 - 60s ✓ Completed
# [4/12] Running V1 - 120s ... (interrupted via Ctrl+C)

# Re-run same command
$ python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Automatically resumes:
# Found 3 completed runs from checkpoint
# [4/12] Running V1 - 120s (continues from here)
```

## Interpreting Results

### Comparison Table Key Metrics

The comparison table displays in terminal and is saved to CSV:

```
Interval (sec)  V1 P&L     V2 P&L     P&L Diff   V1 Trades  V2 Trades  V1 Sharpe  V2 Sharpe  V1 Max DD%  V2 Max DD%  V1 Win%  V2 Win%  V1 Loss%  V2 Loss%  V1 Calmar    V2 Calmar
10              1086775.6  1329497.7  242722.1   106826     269053     12.699     15.310     -2.100      -3.124      28.4     23.6     71.6      76.4      9.59e+07     7.89e+07
30              1044030.1  1219704.3  175674.2   132936     252238     11.179     13.869     -3.338      -2.670      28.0     23.7     72.0      76.3      5.80e+07     8.46e+07
```

**Key Columns:**
- **P&L Diff**: V2 P&L - V1 P&L (positive = V2 outperforms)
- **Trade Diff**: V2 typically has more trades (more aggressive)
- **Sharpe Ratio**: Risk-adjusted performance (>1 good, >2 excellent)
- **Max DD%**: Worst loss from peak (lower absolute value is better)
- **Win%/Loss%**: Percentage of profitable/losing trades
- **Calmar**: Return/risk ratio (higher is better)

### Visual Analysis

#### 1. Comprehensive Comparison Plot
- **Use for**: Overall strategy comparison across all metrics
- **Look for**: Consistent patterns across intervals
- **Risk-Return plot**: Upper-left quadrant is ideal (high return, low drawdown)

#### 2. Cumulative P&L by Strategy
- **Use for**: Understanding P&L trajectory over time
- **Look for**: 
  - Smooth upward trends (consistent profits)
  - Sharp drops (drawdown events)
  - Divergence between intervals
- **Compare**: Which interval maintains steady growth vs volatile swings

#### 3. Per-Security P&L Plots
- **Use for**: Identifying strong/weak securities
- **Look for**:
  - Securities with consistent upward trends
  - Problem securities with large drawdowns
  - Correlation patterns between securities
- **Action**: Consider excluding poor performers or adjusting position limits

### Best Configuration Selection

Consider these factors when choosing optimal parameters:

**1. Highest P&L** (Absolute Returns)
```
Best: V2 @ 10s = 1,329,497 AED
Pro: Maximum profit
Con: May have higher risk or drawdown
```

**2. Highest Sharpe Ratio** (Risk-Adjusted Returns) ⭐ RECOMMENDED
```
Best: V2 @ 10s = 15.31 Sharpe
Pro: Best return per unit of risk
Con: May not be absolute maximum P&L
```

**3. Lowest Drawdown** (Most Conservative)
```
Best: V1 @ 10s = -2.10% Max DD
Pro: Minimal worst-case loss
Con: May sacrifice returns
```

**4. Best Calmar Ratio** (Return/Risk Balance)
```
Best: V1 @ 10s = 95.9M Calmar
Pro: Best return relative to drawdown
Con: Can be skewed by very low drawdown
```

**5. Highest Win Rate** (Most Consistent)
```
Best: V1 @ 10s = 28.4% Win Rate
Pro: Higher proportion of winning trades
Con: Win size vs loss size matters more than frequency
```

**Recommended Selection Logic:**
1. Filter by acceptable drawdown level (e.g., Max DD < -5%)
2. Among acceptable risk profiles, choose highest Sharpe ratio
3. Verify with cumulative P&L plot for trajectory consistency
4. Check per-security breakdown for any problem areas

## Performance Tips

### Speed Optimization
- Use `--max-sheets` for testing (e.g., 2-5 sheets)
- Larger `--chunk-size` (e.g., 200000) can be faster but uses more memory
- Run fewer intervals initially to identify promising ranges

### Memory Management
- Default chunk size (100,000) works well for most systems
- If memory issues occur, reduce chunk size to 50,000

### Parallel Execution (Advanced)
You can run multiple sweeps in parallel if you have the resources:

Terminal 1:
```bash
python scripts/comprehensive_sweep.py --strategies v1 --output-dir output/sweep_v1
```

Terminal 2:
```bash
python scripts/comprehensive_sweep.py --strategies v2 --output-dir output/sweep_v2
```

Then manually compare the results.

## Example Output

### Terminal Output During Run
```
================================================================================
COMPREHENSIVE PARAMETER SWEEP: V1 vs V2
================================================================================
Strategies: V1, V2
Intervals: [10, 30, 60, 120, 300, 600]
Data: data/raw/TickData.xlsx
Max Sheets: All
Output: output/comprehensive_sweep
Mode: Resume from checkpoint
================================================================================

Found 0 completed runs from checkpoint

Loaded V1 config: 16 securities
Loaded V2 config: 16 securities

================================================================================
[1/12] Running V1 - 10s
================================================================================
Testing V1 - Interval: 10s (0.2m)
Processing chunk 1: 100000 rows for EMAAR UH Equity
  After chunk 1: 914 total trades
...
✓ Completed in 245.3 seconds
  ✓ Saved per-security results to v1_10s/

V1 @ 10s Summary:
  Trades: 106,826
  P&L: 1,086,775.61 AED
  Sharpe: 12.699
  Max DD: -2.10%
  Win Rate: 28.4%
  Loss Rate: 71.6%
```

### Final Comparison Table
```
========================================================================================================================
STRATEGY COMPARISON TABLE
========================================================================================================================
Interval (sec)    V1 P&L      V2 P&L   P&L Diff  V1 Trades  V2 Trades  V1 Sharpe  V2 Sharpe  V1 Max DD%  V2 Max DD%  
            10 1086775.61 1329497.72 242722.11     106826     269053      12.70      15.31       -2.10       -3.12
            30 1044030.09 1219704.30 175674.21     132936     252238      11.18      13.87       -3.34       -2.67
            60  832828.44 1133645.33 300816.89     146632     235822       9.11      12.59      -29.51       -2.60
           120  866532.01  916627.18  50095.17     153867     212420       9.29      10.76       -3.39       -3.84
           300  516694.37  660560.86 143866.49     138271     171725       6.01       8.37       -6.65       -7.34
           600  358882.87  380529.62  21646.75     111124     136637       4.00       5.63       -9.68      -10.72

V1 Win%  V2 Win%  V1 Loss%  V2 Loss%  V1 Calmar      V2 Calmar
  28.4     23.6      71.6      76.4   9.59e+07       7.89e+07
  28.0     23.7      72.0      76.3   5.80e+07       8.46e+07
  27.7     23.4      72.3      76.6   5.23e+06       8.09e+07
  27.7     23.1      72.3      76.9   4.73e+07       4.42e+07
  26.6     22.3      73.4      77.7   1.44e+07       1.67e+07
  26.1     22.1      73.9      77.9   6.87e+06       6.58e+06
========================================================================================================================

================================================================================
BEST CONFIGURATIONS
================================================================================

V1 Best by P&L:
  Interval: 10s (0.2m)
  P&L: 1,086,775.61 AED
  Sharpe: 12.699
  Max DD: -2.10%
  Win Rate: 28.4%

V1 Best by Sharpe:
  Interval: 10s (0.2m)
  P&L: 1,086,775.61 AED
  Sharpe: 12.699
  Max DD: -2.10%
  Win Rate: 28.4%

V2 Best by P&L:
  Interval: 10s (0.2m)
  P&L: 1,329,497.72 AED
  Sharpe: 15.310
  Max DD: -3.12%
  Win Rate: 23.6%

V2 Best by Sharpe:
  Interval: 10s (0.2m)
  P&L: 1,329,497.72 AED
  Sharpe: 15.310
  Max DD: -3.12%
  Win Rate: 23.6%

Generating cumulative P&L plots...
✓ Saved cumulative P&L plot: cumulative_pnl_by_strategy.png
✓ Saved 12 per-security P&L plots to pnl_by_security_plots/

================================================================================
SWEEP COMPLETE!
Results saved to: output/comprehensive_sweep
================================================================================
```

## Troubleshooting

### Script Gets Stuck
- Usually happens on large Excel files during initial load
- Be patient during first chunk of first sheet
- Progress speeds up after initial load

### Memory Errors
- Reduce `--chunk-size` to 50000
- Process fewer sheets initially with `--max-sheets`

### Config Not Found
- Ensure config files exist in `configs/` directory
- V2 config can be copy of V1 config if identical parameters

### Empty Results
- Check that data file path is correct
- Ensure securities in config match Excel sheet names
- Verify Excel file has data in expected format

## Next Steps

After running the sweep:

1. **Review `comparison_table.csv`** for numerical comparison
2. **Examine `comprehensive_comparison.png`** for visual insights
3. **Identify optimal interval** based on your priority (P&L, Sharpe, drawdown)
4. **Run detailed backtest** with optimal parameters using:
   ```bash
   python scripts/run_strategy.py --config configs/v1_baseline_config.json
   ```
5. **Analyze per-security results** in the interval-specific subdirectories
