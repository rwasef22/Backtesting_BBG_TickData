# Parallel Backtest - Quick Reference

## Files Created

1. **`src/parallel_backtest.py`**: Core parallel processing engine
2. **`scripts/run_parallel_backtest.py`**: Command-line interface for parallel runs

## Basic Usage

### Quick Start (Recommended)

```bash
# Run V1 baseline with automatic worker detection
python scripts/run_parallel_backtest.py --strategy v1_baseline

# Run V2 strategy
python scripts/run_parallel_backtest.py --strategy v2_price_follow_qty_cooldown
```

### Testing (Limited Securities)

```bash
# Test with 5 securities and 2 workers
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 5 --workers 2

# Quick smoke test
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 2 --workers 2
```

### Benchmark Comparison

```bash
# Compare sequential vs parallel performance
python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark

# Expected output:
# Sequential: 480.0s (8.0 min)
# Parallel:   120.0s (2.0 min)
# Speedup:    4.00x
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--strategy` | Strategy name (required) | - |
| `--workers` | Number of parallel processes | CPU count |
| `--max-sheets` | Limit securities (for testing) | All |
| `--config` | Config file path | `configs/{strategy}_config.json` |
| `--output-dir` | Output directory | `output/{strategy}_parallel` |
| `--chunk-size` | Rows per chunk | 100000 |
| `--benchmark` | Run sequential vs parallel comparison | False |
| `--only-trades` | Filter to trade events only | False |

## Examples

### Production Run

```bash
# Full dataset with 4 workers (typical for 4-core CPU)
python scripts/run_parallel_backtest.py \
  --strategy v1_baseline \
  --workers 4 \
  --output-dir output/v1_production_parallel
```

### Development Testing

```bash
# Quick iteration with subset
python scripts/run_parallel_backtest.py \
  --strategy v2_price_follow_qty_cooldown \
  --max-sheets 3 \
  --workers 2 \
  --output-dir output/test_parallel
```

### Custom Configuration

```bash
# Use custom config file
python scripts/run_parallel_backtest.py \
  --strategy v1_baseline \
  --config configs/custom_config.json \
  --output-dir output/custom_parallel
```

## Comparing Sequential vs Parallel Results

### Step 1: Run Both Versions

```bash
# Sequential version
python scripts/run_strategy.py \
  --strategy v1_baseline \
  --output-dir output/v1_sequential

# Parallel version
python scripts/run_parallel_backtest.py \
  --strategy v1_baseline \
  --output-dir output/v1_parallel
```

### Step 2: Compare Outputs

```bash
# Compare summary files
diff output/v1_sequential/backtest_summary.csv output/v1_parallel/backtest_summary.csv

# Or use Python
python -c "
import pandas as pd
seq = pd.read_csv('output/v1_sequential/backtest_summary.csv')
par = pd.read_csv('output/v1_parallel/backtest_summary.csv')
print('Differences:')
print(seq.compare(par))
"
```

### Step 3: Verify Trade Counts

Both versions should produce identical:
- Trade counts per security
- Final P&L per security
- Position states
- Market/strategy dates

## Performance Expectations

| CPU Cores | Workers | Expected Speedup | 8min → |
|-----------|---------|------------------|--------|
| 2         | 2       | 1.8x            | 4.4min |
| 4         | 4       | 3.5x            | 2.3min |
| 6         | 6       | 5.0x            | 1.6min |
| 8         | 8       | 6.5x            | 1.2min |

**Note**: Actual speedup depends on I/O speed and system load.

## Troubleshooting

### "openpyxl not installed"

```bash
pip install openpyxl
```

### "Handler function not found"

Ensure handler exists with proper naming:
- `create_{strategy}_handler` (e.g., `create_v1_baseline_handler`)
- Or generic `create_handler`

### Memory Issues

Reduce number of workers:
```bash
python scripts/run_parallel_backtest.py --strategy v1_baseline --workers 2
```

### Results Don't Match Sequential

1. Check for non-deterministic behavior in strategy
2. Verify all state is properly isolated
3. Compare detailed trade logs:
   ```bash
   diff output/v1_sequential/adnocgas_trades_timeseries.csv \
        output/v1_parallel/adnocgas_trades_timeseries.csv
   ```

## Architecture Notes

### How It Works

1. **Main Process**: Discovers securities from Excel, spawns workers
2. **Worker Processes**: Each processes 1+ securities independently
3. **Aggregation**: Main process collects results and writes files

### Why It's Fast

- **True Parallelism**: ProcessPoolExecutor bypasses Python GIL
- **Independent Securities**: No shared state = no locks/contention
- **Efficient I/O**: Each worker streams its own data

### Limitations

- **Memory**: Each worker needs ~500MB-1GB
- **I/O Contention**: All workers read same Excel file (consider Parquet conversion)
- **Overhead**: Process spawning adds ~5-10s startup time

## Integration with Existing Workflows

### Parameter Sweeps

For comprehensive sweeps, use sequential version:
```bash
# Sweeps already checkpoint progress - parallelism at interval level
python scripts/comprehensive_sweep.py
```

Or run multiple sweep instances in parallel terminals with different intervals.

### Strategy Comparison

Run each strategy in parallel, then compare:
```bash
# Terminal 1
python scripts/run_parallel_backtest.py --strategy v1_baseline \
  --output-dir output/v1_parallel

# Terminal 2
python scripts/run_parallel_backtest.py --strategy v2_price_follow_qty_cooldown \
  --output-dir output/v2_parallel

# Compare results
python scripts/compare_strategies.py \
  output/v1_parallel output/v2_parallel
```

## Next Steps

### Optimization Phase 2: Convert to Parquet

For maximum performance (10-20x total speedup):

```bash
# 1. Convert Excel to Parquet (one-time)
python scripts/convert_excel_to_parquet.py

# 2. Modify data_loader.py to read Parquet
# 3. Run parallel backtest
python scripts/run_parallel_backtest.py --strategy v1_baseline
```

See [PARALLELIZATION_GUIDE.md](../PARALLELIZATION_GUIDE.md) for implementation details.
