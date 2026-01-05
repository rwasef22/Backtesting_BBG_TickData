# Scripts Reference Guide

Complete documentation for all executable scripts in the tick-backtest-project.

## Table of Contents
1. [Primary Backtest Scripts](#primary-backtest-scripts)
2. [Parameter Sweep Scripts](#parameter-sweep-scripts)
3. [Data Management Scripts](#data-management-scripts)
4. [Analysis & Comparison Scripts](#analysis--comparison-scripts)
5. [Script Selection Guide](#script-selection-guide)

---

## Primary Backtest Scripts

### `run_parquet_backtest.py` ⭐ RECOMMENDED

**Purpose**: Fastest backtest runner using Parquet data format + parallel processing.

**Performance**: 8-15x faster than Excel sequential (30-60 seconds for full dataset)

**Prerequisites**: 
- Run `convert_excel_to_parquet.py` once to create Parquet files
- Install `pyarrow`: `pip install pyarrow`

**Usage**:
```bash
# Basic usage
python scripts/run_parquet_backtest.py --strategy v1_baseline

# All available strategies
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss
python scripts/run_parquet_backtest.py --strategy v3_liquidity_monitor

# Custom worker count (default: CPU count)
python scripts/run_parquet_backtest.py --strategy v1_baseline --workers 4

# Quick test with limited securities
python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5

# Custom chunk size (default: 100000)
python scripts/run_parquet_backtest.py --strategy v1_baseline --chunk-size 50000

# Custom output directory
python scripts/run_parquet_backtest.py --strategy v1_baseline --output-dir my_output
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--strategy` | Yes | - | Strategy name (e.g., `v1_baseline`, `v2_1_stop_loss`) |
| `--workers` | No | CPU count | Number of parallel workers |
| `--max-sheets` | No | All | Limit number of securities |
| `--chunk-size` | No | 100000 | Rows per processing chunk |
| `--parquet-dir` | No | `data/parquet` | Parquet files directory |
| `--output-dir` | No | `output/{strategy}` | Output directory |

**Output**:
- `output/{strategy}/{security}_trades.csv` - Per-security trade log
- `output/{strategy}/backtest_summary.csv` - Aggregate metrics
- Console summary with P&L, trades, processing time

---

### `run_parallel_backtest.py`

**Purpose**: Parallel backtest runner using original Excel data format.

**Performance**: 3-4x faster than sequential (2-3 minutes for full dataset)

**When to Use**: When you want to verify results against Excel directly without Parquet conversion.

**Usage**:
```bash
# Basic usage
python scripts/run_parallel_backtest.py --strategy v1_baseline

# Benchmark mode (compare sequential vs parallel)
python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark

# Custom workers
python scripts/run_parallel_backtest.py --strategy v1_baseline --workers 8

# Quick test
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 5
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--strategy` | Yes | - | Strategy name |
| `--workers` | No | CPU count | Number of parallel workers |
| `--max-sheets` | No | All | Limit number of securities |
| `--benchmark` | No | False | Run sequential comparison |
| `--data` | No | `data/raw/TickData.xlsx` | Excel data file |

**Benchmark Output**:
```
================================================================================
BENCHMARK RESULTS
================================================================================
Sequential: 485.3 seconds
Parallel (4 workers): 142.1 seconds
Speedup: 3.42x
```

---

### `run_strategy.py`

**Purpose**: Sequential reference implementation for backtesting.

**Performance**: 8-10 minutes for full dataset (slowest but most debuggable)

**When to Use**: 
- Debugging strategy issues
- Verifying results against parallel implementations
- Simple testing without parallelization complexity

**Usage**:
```bash
# Basic usage
python scripts/run_strategy.py --strategy v1_baseline

# Custom config file
python scripts/run_strategy.py --strategy v1_baseline --config configs/custom_config.json

# Quick test
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5

# Custom chunk size
python scripts/run_strategy.py --strategy v1_baseline --chunk-size 50000
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--strategy` | Yes | - | Strategy name |
| `--config` | No | Auto-detected | Config file path |
| `--max-sheets` | No | All | Limit number of securities |
| `--chunk-size` | No | 100000 | Rows per chunk |
| `--data` | No | `data/raw/TickData.xlsx` | Excel data file |

---

## Parameter Sweep Scripts

### `fast_sweep.py` ⭐ RECOMMENDED

**Purpose**: Compare V2 vs V2.1 strategies across multiple refill intervals. Fast execution using Parquet + parallel processing.

**Performance**: ~1.5 minutes per scenario, 5-6 minutes for 8 scenarios (4 intervals × 2 strategies)

**Key Features**:
- Compares V2 (price-follow) vs V2.1 (price-follow + stop-loss)
- Tests multiple refill intervals in parallel
- Generates comparison table and cumulative P&L plots
- Saves per-security trade CSVs for detailed analysis

**Usage**:
```bash
# Quick test (5 securities, 3 intervals) - ~2-3 minutes
python scripts/fast_sweep.py --max-sheets 5 --intervals 30 60 120

# Full production sweep - ~5-6 minutes
python scripts/fast_sweep.py --intervals 5 10 30 60

# Extended interval range
python scripts/fast_sweep.py --intervals 5 10 20 30 45 60 90 120

# Custom stop-loss threshold
python scripts/fast_sweep.py --intervals 5 10 30 60 --stop-loss 3.0

# Custom output directory
python scripts/fast_sweep.py --intervals 5 10 30 60 --output-dir output/my_sweep
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--intervals` | No | `[5, 10, 30, 60]` | Refill intervals to test (seconds) |
| `--max-sheets` | No | All | Limit number of securities |
| `--stop-loss` | No | 2.0 | Stop-loss percentage for V2.1 |
| `--output-dir` | No | `output/sweep_v2_v21` | Output directory |

**Output**:
```
output/sweep_v2_v21/
├── sweep_results.csv              # All metrics for all scenarios
├── comparison_table.txt           # Formatted comparison table
├── cumulative_pnl_by_strategy.png # P&L visualization
├── v2_5s/                         # Per-scenario trade data
│   └── {security}_trades.csv
├── v2_10s/
├── v2_1_5s/
├── v2_1_10s/
└── ...
```

**Sample Output**:
```
========================================
FAST V2 vs V2.1 SWEEP RESULTS
========================================

Strategy    Interval  Trades      P&L (AED)     Sharpe   Max DD (AED)  Win Rate
----------  --------  ----------  ------------  -------  ------------  --------
V2          5s        283,309     1,319,147.87  14.19    -664,128.95   23.55%
V2          10s       277,212     1,273,433.17  13.92    -702,571.70   23.57%
V2.1        5s        283,781     1,408,863.92  14.96    -648,421.94   23.64%  ⭐
V2.1        10s       277,624     1,365,515.77  14.80    -684,887.52   23.66%

BEST CONFIGURATION: V2.1 @ 5s
  P&L: 1,408,863.92 AED
  Sharpe: 14.96
  Trades: 283,781
```

---

### `comprehensive_sweep.py`

**Purpose**: Full parameter sweep comparing V1 and V2 strategies with checkpoint support.

**Performance**: 60-90 minutes for full sweep (6 intervals × 2 strategies)

**Key Features**:
- Compares V1 baseline vs V2 price-follow
- Checkpoint system for interrupted runs
- Extended metrics: Sharpe, drawdown, Calmar ratio, win/loss rate
- 12-panel visualization comparing all metrics

**Usage**:
```bash
# Full sweep with recommended intervals
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Quick test
python scripts/comprehensive_sweep.py --intervals 30 60 120 --max-sheets 5

# Resume interrupted sweep (automatic)
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Start fresh (ignore checkpoint)
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600 --fresh

# Single strategy only
python scripts/comprehensive_sweep.py --strategies v1 --intervals 30 60 120 180

# Custom output
python scripts/comprehensive_sweep.py --intervals 30 60 120 --output-dir output/my_sweep
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--intervals` | No | `[30,60,120,180,300]` | Refill intervals (seconds) |
| `--strategies` | No | `['v1', 'v2']` | Strategies to run |
| `--max-sheets` | No | All | Limit securities |
| `--fresh` | No | False | Ignore checkpoint |
| `--output-dir` | No | `output/comprehensive_sweep` | Output directory |

**Output**:
```
output/comprehensive_sweep/
├── comprehensive_results.csv      # All metrics
├── comparison_table.csv           # Side-by-side comparison
├── comprehensive_comparison.png   # 12-panel visualization
├── cumulative_pnl_by_strategy.png # P&L trajectory
├── checkpoint.csv                 # Resume checkpoint
├── v1_30s/                        # Per-scenario results
├── v2_30s/
└── ...
```

---

## Data Management Scripts

### `convert_excel_to_parquet.py`

**Purpose**: One-time conversion of Excel tick data to Parquet format for faster I/O.

**Performance**: ~5 minutes for 16 securities, 50% file size reduction

**Usage**:
```bash
# Full conversion
python scripts/convert_excel_to_parquet.py

# Force reconversion (overwrite existing)
python scripts/convert_excel_to_parquet.py --force

# Quick test
python scripts/convert_excel_to_parquet.py --max-sheets 5

# Custom output directory
python scripts/convert_excel_to_parquet.py --output data/my_parquet
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--data` | No | `data/raw/TickData.xlsx` | Source Excel file |
| `--output` | No | `data/parquet` | Output directory |
| `--max-sheets` | No | All | Limit securities |
| `--force` | No | False | Overwrite existing files |

**Output**:
```
data/parquet/
├── adcb.parquet       (~8 MB)
├── adib.parquet       (~12 MB)
├── adnocgas.parquet   (~15 MB)
└── ...                (16 files total, ~50 MB)
```

---

### `validate_parquet_data.py`

**Purpose**: Validate that Parquet files match Excel source data.

**Usage**:
```bash
# Validate all Parquet files
python scripts/validate_parquet_data.py

# Validate specific files
python scripts/validate_parquet_data.py --securities ADNOCGAS EMAAR
```

**Validation Checks**:
1. All Excel securities present in Parquet
2. Date range matches exactly
3. Row counts match
4. Data integrity (no corruption)

---

## Analysis & Comparison Scripts

### `compare_strategies.py`

**Purpose**: Compare performance of two or more strategies from existing output.

**Prerequisites**: Run backtests first to generate output files.

**Usage**:
```bash
# Compare two strategies
python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown

# Compare multiple strategies
python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown v2_1_stop_loss

# Compare all strategies in output/
python scripts/compare_strategies.py --all

# Custom output
python scripts/compare_strategies.py v1_baseline v2_1_stop_loss --output comparison.csv --plot comparison.png
```

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| strategies | Yes* | - | Strategy names to compare |
| `--all` | No | False | Compare all strategies |
| `--output` | No | `comparison.csv` | Output CSV file |
| `--plot` | No | `comparison.png` | Output plot file |

**Output**:
```
================================================================================
STRATEGY COMPARISON
================================================================================
Strategy                       Trades      P&L (AED)    Sharpe
-----------------------------  ----------  -----------  ------
v1_baseline                    106,826     697,542.31   12.70
v2_price_follow_qty_cooldown   283,309     1,319,147    14.19
v2_1_stop_loss                 283,781     1,408,864    14.96  ⭐
```

---

## Script Selection Guide

### Which Script Should I Use?

| Scenario | Recommended Script | Reason |
|----------|-------------------|--------|
| **First time running backtest** | `run_parquet_backtest.py` | Fastest, requires Parquet conversion |
| **Quick test (5 min)** | `run_parquet_backtest.py --max-sheets 5` | Fast iteration |
| **Compare V2 vs V2.1** | `fast_sweep.py` | Purpose-built for this comparison |
| **Full V1/V2 parameter sweep** | `comprehensive_sweep.py` | Handles checkpointing |
| **Debugging strategy** | `run_strategy.py` | Sequential, easier to debug |
| **Verify Parquet results** | `run_parallel_backtest.py` | Uses original Excel |
| **One-time data setup** | `convert_excel_to_parquet.py` | Required for Parquet runners |

### Performance Expectations

| Script | Full Dataset | 5 Securities |
|--------|-------------|--------------|
| `run_strategy.py` | 8-10 min | 2-3 min |
| `run_parallel_backtest.py` | 2-3 min | 30-45 sec |
| `run_parquet_backtest.py` | 30-60 sec | 10-15 sec |
| `fast_sweep.py` (8 scenarios) | 5-6 min | 2-3 min |
| `comprehensive_sweep.py` (12 scenarios) | 60-90 min | 15-20 min |

### Typical Workflows

**Development Workflow**:
```bash
# 1. Convert data once
python scripts/convert_excel_to_parquet.py

# 2. Quick test during development
python scripts/run_parquet_backtest.py --strategy my_strategy --max-sheets 5

# 3. Full validation
python scripts/run_parquet_backtest.py --strategy my_strategy

# 4. Compare to baseline
python scripts/compare_strategies.py v2_1_stop_loss my_strategy
```

**Parameter Optimization Workflow**:
```bash
# 1. Quick sweep to identify promising intervals
python scripts/fast_sweep.py --max-sheets 5 --intervals 5 10 20 30 60 120

# 2. Full sweep on promising intervals
python scripts/fast_sweep.py --intervals 5 10 30 60

# 3. Analyze results
# Check output/sweep_v2_v21/sweep_results.csv
# Check output/sweep_v2_v21/cumulative_pnl_by_strategy.png
```

**Production Run Workflow**:
```bash
# 1. Full V2.1 backtest with best configuration
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss

# 2. Verify results
python scripts/compare_strategies.py v1_baseline v2_1_stop_loss

# 3. Generate reports
# Outputs are in output/v2_1_stop_loss/
```

---

## Exit Codes

All scripts return:
- `0`: Success
- `1`: Error (check console output for details)

## Common Issues

### "ModuleNotFoundError: No module named 'pyarrow'"
```bash
pip install pyarrow
```

### "FileNotFoundError: data/parquet/..."
```bash
python scripts/convert_excel_to_parquet.py
```

### "KeyError: 'SECURITY_NAME'"
Check that security name in config matches Excel sheet name (without "UH Equity" suffix).

### "MemoryError"
Reduce chunk size:
```bash
python scripts/run_parquet_backtest.py --strategy v1_baseline --chunk-size 50000
```
