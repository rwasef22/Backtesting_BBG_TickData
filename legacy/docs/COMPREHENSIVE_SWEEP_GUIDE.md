# Comprehensive Sweep Tool - Enhanced Guide

## Overview

The enhanced `comprehensive_sweep.py` script now provides flexible parameter sweeping with multiple execution modes, strategy selection, and automatic plot regeneration.

## Key Features

### 1. **Flexible Parameter Sweeping**

Choose which parameter to sweep:
- `interval` - Refill interval (seconds)
- `cooldown` - Minimum cooldown period (seconds)  
- `threshold` - Stop-loss threshold (percentage)

### 2. **Multiple Execution Modes**

- **Fresh Mode** (`--fresh`): Delete all existing results and start from scratch
- **Continue Mode** (`--continue`): Resume from checkpoint, skip completed runs (default)
- **Skip Existing** (`--skip-existing`): Load existing data but only run new strategies

### 3. **Strategy Selection**

Choose any combination of strategies:
- `v1` - Baseline market making
- `v2` - Price follow with quantity cooldown
- `v2_1` - V2 with stop-loss protection
- `v3` - Liquidity monitoring (abandoned)

### 4. **Automatic Plot Regeneration**

At the end of each sweep, automatically generates:
- Cumulative P&L by strategy
- P&L by security
- **Comprehensive comparison plot** (12-panel grid) with ALL data from CSV

## Usage Examples

### Example 1: Fresh V2 vs V2.1 Comparison
```bash
python scripts/comprehensive_sweep.py \
  --strategies v2 v2_1 \
  --fresh \
  --intervals 30 60 120 180 300
```

### Example 2: Continue Existing Sweep, Add V3
```bash
python scripts/comprehensive_sweep.py \
  --strategies v3 \
  --continue
```

### Example 3: Sweep Cooldown Parameter (V2 only)
```bash
python scripts/comprehensive_sweep.py \
  --strategies v2 \
  --sweep-param cooldown \
  --param-range 30 600 30
```

This sweeps cooldown from 30s to 600s in steps of 30s.

### Example 4: Sweep Stop-Loss Threshold (V2.1 only)
```bash
python scripts/comprehensive_sweep.py \
  --strategies v2_1 \
  --sweep-param threshold \
  --param-range 1 10 1
```

This tests stop-loss thresholds from 1% to 10% in 1% increments.

### Example 5: Quick Test with Limited Data
```bash
python scripts/comprehensive_sweep.py \
  --strategies v2 v2_1 \
  --intervals 30 60 \
  --max-sheets 3 \
  --fresh
```

### Example 6: Specific Securities Only
```bash
python scripts/comprehensive_sweep.py \
  --strategies v2 \
  --sheet-names "EMAAR UH Equity" "ADNOCGAS UH Equity" \
  --intervals 30 60 120
```

## Command Line Arguments

### Basic Configuration
- `--data PATH` - Path to TickData.xlsx (default: data/raw/TickData.xlsx)
- `--output-dir DIR` - Output directory (default: output/comprehensive_sweep)
- `--max-sheets N` - Limit number of securities (useful for testing)
- `--sheet-names NAME [NAME...]` - Process only specific securities
- `--chunk-size N` - Chunk size for streaming (default: 100000)

### Strategy Selection
- `--strategies {v1,v2,v2_1,v3} [...]` - Choose strategies to test

### Parameter Sweep
- `--sweep-param {interval,cooldown,threshold}` - Parameter to sweep (default: interval)
- `--intervals SEC [SEC...]` - Interval values (default: 30 60 120 180 300)
- `--param-range START END STEP` - Range for cooldown/threshold sweeps

### Execution Modes
- `--fresh` - Start fresh, delete all existing results
- `--continue` - Continue from checkpoint (default)
- `--skip-existing` - Skip strategies with existing results

## Output Structure

```
output/comprehensive_sweep/
├── checkpoint.csv                          # Progress tracking
├── comprehensive_results.csv               # Aggregated metrics
├── comprehensive_comparison.png            # 12-panel comparison plot
├── cumulative_pnl_by_strategy.png         # P&L trend plot
├── per_security_summary.csv               # Per-security metrics
├── per_security_pnl_pivot.csv             # Pivot table
├── comparison_table.csv                   # Strategy comparison table
├── v2_30s/                                # Per-strategy/param folders
│   ├── EMAAR_UH_Equity_trades.csv
│   ├── ADNOCGAS_UH_Equity_trades.csv
│   └── per_security_summary.csv
├── v2_60s/
├── v2_1_30s/
├── v2_1_60s/
└── ...
```

## Advanced Workflow

### Workflow 1: Compare V2 Variants
1. Run V2 baseline:
   ```bash
   python scripts/comprehensive_sweep.py --strategies v2 --fresh
   ```

2. Add V2.1 to comparison:
   ```bash
   python scripts/comprehensive_sweep.py --strategies v2_1 --continue
   ```

3. All plots automatically include both strategies.

### Workflow 2: Optimize Stop-Loss Threshold
1. Test range of thresholds for V2.1:
   ```bash
   python scripts/comprehensive_sweep.py \
     --strategies v2_1 \
     --sweep-param threshold \
     --param-range 2 10 2 \
     --fresh
   ```

2. Results show best threshold in "BEST CONFIGURATIONS" section.

### Workflow 3: Optimize Cooldown Period
1. Test cooldown values for V2:
   ```bash
   python scripts/comprehensive_sweep.py \
     --strategies v2 \
     --sweep-param cooldown \
     --param-range 30 300 30 \
     --fresh
   ```

## Checkpoint System

The script automatically saves progress after each configuration:
- **Interrupted?** Re-run the same command to resume
- **Want fresh start?** Use `--fresh` to delete checkpoint
- **Adding strategies?** Use `--continue` to keep existing data

## Plot Regeneration

### Automatic Regeneration
At the end of each sweep, all plots are regenerated from the CSV file, ensuring:
- All strategies included (even from previous runs)
- Consistent visualization
- Up-to-date comparisons

### Manual Regeneration
If you need to regenerate plots without running backtest:
```python
from pathlib import Path
from scripts.comprehensive_sweep import regenerate_comprehensive_plots

regenerate_comprehensive_plots(Path('output/comprehensive_sweep'))
```

## Performance Tips

1. **Use checkpoints**: Don't use `--fresh` unless you really need to start over
2. **Test first**: Run with `--max-sheets 3` to verify configuration
3. **Specific securities**: Use `--sheet-names` to focus on interesting securities
4. **Parallel strategies**: All strategies in `--strategies` run sequentially (safe for memory)

## Best Practices

1. **Always check existing results**:
   ```bash
   # View what's already completed
   head -20 output/comprehensive_sweep/checkpoint.csv
   ```

2. **Use descriptive output directories** for different experiments:
   ```bash
   python scripts/comprehensive_sweep.py \
     --strategies v2_1 \
     --sweep-param threshold \
     --output-dir output/v2_1_threshold_sweep
   ```

3. **Compare incremental changes**:
   - Run baseline with `--fresh`
   - Add variants with `--continue`
   - Plots show all strategies together

## Troubleshooting

### Issue: "Strategy already completed"
- **Cause**: Checkpoint has this strategy/param combination
- **Solution**: Use `--fresh` to start over, or choose different parameters

### Issue: Plots missing a strategy
- **Cause**: Old plot files from before strategy was added
- **Solution**: Plots are regenerated automatically at end of sweep

### Issue: Memory errors
- **Cause**: Too many securities loaded at once
- **Solution**: Use `--max-sheets` or `--sheet-names` to limit

### Issue: Want to re-run specific interval
- **Solution**: 
  1. Delete the row from `checkpoint.csv`
  2. Delete the strategy_XXXs folder
  3. Run with `--continue`

## Example Output

```
================================================================================
COMPREHENSIVE PARAMETER SWEEP
================================================================================
Strategies: V2, V2.1
Sweep Parameter: Interval (sec)
Values: [30, 60, 120, 180, 300]
Data: data/raw/TickData.xlsx
Max Sheets: All
Sheet Filter: None
Output: output/comprehensive_sweep
Execution Mode: Continue from checkpoint (default)
================================================================================

▶️  Continuing from checkpoint
   Loaded 7 existing results
   7 configurations already completed

🚀 [1/3] Running V2.1 - Interval (sec)=120
================================================================================
...
✅ SWEEP COMPLETE!
Results saved to: output/comprehensive_sweep
================================================================================
```

## Next Steps

After running a sweep:
1. Check `comprehensive_comparison.png` for visual comparison
2. Review `comparison_table.csv` for numerical metrics
3. Examine `BEST CONFIGURATIONS` output for optimal parameters
4. Drill into per-security results in strategy_XXXs folders
