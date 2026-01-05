# Market-Making Backtest Framework

A high-performance, modular framework for backtesting market-making strategies on historical tick data. Features parallel processing, Parquet data format support, and comprehensive strategy comparison tools.

##  Quick Start

### Installation

```bash
# Clone repository
cd tick-backtest-project

# Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install pandas openpyxl matplotlib pyarrow
```

### Run Your First Backtest (30 seconds)

```bash
# Convert Excel to Parquet (one-time, ~5 minutes)
python scripts/convert_excel_to_parquet.py

# Run fastest backtest (Parquet + Parallel)
python scripts/run_parquet_backtest.py --strategy v1_baseline

# Or quick test with 5 securities
python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5
```

##  Performance Comparison

| Method | Runtime | Speedup |
|--------|---------|---------|
| Excel Sequential | 8-10 min | 1x |
| Excel Parallel (4 cores) | 2-3 min | 3-4x |
| **Parquet Parallel (4 cores)** | **30-60 sec** | **8-15x**  |

##  Available Strategies

| Strategy | Description | Best P&L | Sharpe |
|----------|-------------|----------|--------|
| `v1_baseline` | Reference implementation, time-based refill | 697k AED | 12.7 |
| `v2_price_follow_qty_cooldown` | Aggressive price updates, cooldown after fills | 1.32M AED | 14.2 |
| **`v2_1_stop_loss`** | V2 + 2% stop-loss protection | **1.41M AED** | **15.0**  |
| `v3_liquidity_monitor` | Stricter liquidity requirements (abandoned) | 400k AED | 8.5 |

##  Project Structure

```
tick-backtest-project/
 src/                              # Core framework
    strategies/                   # Strategy implementations
       base_strategy.py          # Abstract base class
       v1_baseline/              # V1: Reference strategy
       v2_price_follow_qty_cooldown/  # V2: Best performer
       v2_1_stop_loss/           # V2.1: With stop-loss
    parallel_backtest.py          # Parallel execution engine
    parquet_loader.py             # Parquet data loading
    orderbook.py                  # Order book state

 scripts/                          # Executable scripts
    run_parquet_backtest.py       #  Fastest runner
    run_parallel_backtest.py      # Parallel (Excel)
    run_strategy.py               # Sequential (reference)
    fast_sweep.py                 #  V2 vs V2.1 parameter sweep
    comprehensive_sweep.py        # Full V1/V2 sweep
    compare_strategies.py         # Strategy comparison

 configs/                          # Per-security configurations
    v1_baseline_config.json
    v2_price_follow_qty_cooldown_config.json
    v2_1_stop_loss_config.json

 docs/                             # Documentation
    strategies/                   # Per-strategy docs

 output/                           # Results (gitignored)
    sweep_v2_v21/                 # Latest sweep results

 data/                             # Data files
     raw/TickData.xlsx             # Source data (gitignored)
     parquet/                      # Converted Parquet files
```

##  Scripts Reference

### Primary Scripts

#### `run_parquet_backtest.py` - Fastest Backtest Runner 
```bash
# Basic usage
python scripts/run_parquet_backtest.py --strategy v1_baseline

# With options
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss --workers 8 --max-sheets 5

# Options:
#   --strategy     Strategy name (required)
#   --workers      Number of parallel workers (default: CPU count)
#   --max-sheets   Limit securities for testing
#   --chunk-size   Rows per chunk (default: 100000)
```

#### `fast_sweep.py` - V2 vs V2.1 Parameter Sweep 
```bash
# Quick test (5 securities, 3 intervals) - ~5 minutes
python scripts/fast_sweep.py --max-sheets 5 --intervals 30 60 120

# Full production sweep - ~5-6 minutes
python scripts/fast_sweep.py --intervals 5 10 30 60

# Custom stop-loss threshold
python scripts/fast_sweep.py --intervals 5 10 30 60 --stop-loss 3.0

# Options:
#   --intervals    Refill intervals to test (seconds)
#   --max-sheets   Limit securities for testing
#   --stop-loss    Stop-loss percentage for V2.1 (default: 2.0)
#   --output-dir   Output directory (default: output/sweep_v2_v21)
```

#### `run_parallel_backtest.py` - Parallel Excel Runner
```bash
# Basic usage
python scripts/run_parallel_backtest.py --strategy v1_baseline

# Benchmark comparison (sequential vs parallel)
python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark

# Options:
#   --strategy     Strategy name (required)
#   --workers      Number of parallel workers
#   --max-sheets   Limit securities
#   --benchmark    Compare sequential vs parallel timing
```

#### `run_strategy.py` - Sequential Reference Runner
```bash
# Basic usage (sequential, slower but reference implementation)
python scripts/run_strategy.py --strategy v1_baseline

# Quick test
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5

# Options:
#   --strategy     Strategy name (required)
#   --config       Custom config file path
#   --max-sheets   Limit securities
#   --chunk-size   Rows per chunk
```

### Utility Scripts

#### `convert_excel_to_parquet.py` - Data Conversion
```bash
# One-time conversion (required for Parquet runners)
python scripts/convert_excel_to_parquet.py

# Force reconversion
python scripts/convert_excel_to_parquet.py --force

# Quick test conversion
python scripts/convert_excel_to_parquet.py --max-sheets 5
```

#### `compare_strategies.py` - Strategy Comparison
```bash
# Compare two strategies
python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown

# Compare all strategies
python scripts/compare_strategies.py --all
```

#### `comprehensive_sweep.py` - Full Parameter Sweep
```bash
# Full V1/V2 sweep with checkpointing
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Resume interrupted sweep (automatic)
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600

# Start fresh (ignore checkpoint)
python scripts/comprehensive_sweep.py --intervals 10 30 60 120 300 600 --fresh
```

##  Output Files

### Per-Security Trade Log
`output/{strategy}/{security}_trades.csv`:
```csv
timestamp,side,fill_price,fill_qty,realized_pnl,position,pnl
2025-01-15 10:05:23,buy,3.50,30000,0.0,30000,0.0
2025-01-15 10:08:41,sell,3.52,30000,600.0,0,600.0
```

### Backtest Summary
`output/{strategy}/backtest_summary.csv`:
```csv
security,trades,final_position,realized_pnl,rows_processed
ADNOCGAS,8947,0,43570.50,42156
```

### Sweep Results
`output/sweep_v2_v21/sweep_results.csv`:
```csv
strategy,interval_sec,total_trades,total_pnl,sharpe_ratio,max_drawdown,win_rate
v2,5,283309,1319147.87,14.19,-664128.95,23.55
v2_1,5,283781,1408863.92,14.96,-648421.94,23.64
```

##  Configuration

Each strategy uses a JSON config file with per-security parameters:

```json
{
  "ADNOCGAS": {
    "quote_size": 65000,
    "refill_interval_sec": 10,
    "max_position": 130000,
    "max_notional": 1500000,
    "min_local_currency_before_quote": 13000,
    "stop_loss_threshold_pct": 2.0
  }
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `quote_size` | int | Shares to quote per side |
| `refill_interval_sec` | int | Cooldown period after fills (seconds) |
| `max_position` | int | Maximum inventory (shares) |
| `max_notional` | int | Optional dollar cap (AED) |
| `min_local_currency_before_quote` | int | Minimum liquidity threshold (AED) |
| `stop_loss_threshold_pct` | float | Stop-loss trigger (%, V2.1 only) |

##  Creating New Strategies

### 1. Create Strategy Directory
```bash
mkdir src/strategies/v4_my_strategy
```

### 2. Implement Strategy Class
```python
# src/strategies/v4_my_strategy/strategy.py
from ..base_strategy import BaseMarketMakingStrategy

class V4MyStrategy(BaseMarketMakingStrategy):
    def generate_quotes(self, security, best_bid, best_ask, timestamp):
        # Return {bid_price, ask_price, bid_size, ask_size}
        pass
    
    def should_refill_side(self, security, timestamp, side):
        # Return True to place new quote
        pass
```

### 3. Create Handler
```python
# src/strategies/v4_my_strategy/handler.py
def create_v4_my_strategy_handler(config):
    strategy = V4MyStrategy(config)
    
    def handler(security, df, orderbook, state):
        # Process rows, return state
        return state
    
    return handler
```

### 4. Run and Compare
```bash
python scripts/run_parquet_backtest.py --strategy v4_my_strategy
python scripts/compare_strategies.py v2_1_stop_loss v4_my_strategy
```

##  Documentation

- [SCRIPTS_REFERENCE.md](docs/SCRIPTS_REFERENCE.md) - Detailed script documentation
- [STRATEGY_TECHNICAL_DOCUMENTATION.md](STRATEGY_TECHNICAL_DOCUMENTATION.md) - Deep technical reference
- [FILL_REFILL_LOGIC_EXPLAINED.md](FILL_REFILL_LOGIC_EXPLAINED.md) - Quote/fill mechanics
- [MULTI_STRATEGY_GUIDE.md](MULTI_STRATEGY_GUIDE.md) - Architecture guide
- [PARQUET_GUIDE.md](PARQUET_GUIDE.md) - Data format optimization
- [PARAMETER_SWEEP_GUIDE.md](PARAMETER_SWEEP_GUIDE.md) - Parameter optimization

##  Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'strategies.v2_xxx'
```
**Solution**: Ensure `__init__.py` exists in strategy directory

### Memory Errors
```
MemoryError or system freezes
```
**Solution**: Reduce chunk size: `--chunk-size 50000`

### No Parquet Files
```
FileNotFoundError: data/parquet/...
```
**Solution**: Run `python scripts/convert_excel_to_parquet.py`

### Push Rejected (Large Files)
```
remote: error: File exceeds GitHub's file size limit
```
**Solution**: Ensure `data/raw/TickData.xlsx` is in `.gitignore`

##  Latest Results (V2 vs V2.1 Sweep, Jan 2026)

| Strategy | Interval | Trades | P&L (AED) | Sharpe | Win Rate |
|----------|----------|--------|-----------|--------|----------|
| V2 | 5s | 283,309 | 1,319,148 | 14.19 | 23.6% |
| V2 | 10s | 277,212 | 1,273,433 | 13.92 | 23.6% |
| **V2.1** | **5s** | **283,781** | **1,408,864** | **14.96** | **23.6%**  |
| V2.1 | 10s | 277,624 | 1,365,516 | 14.80 | 23.7% |

**Key Finding**: V2.1 (with 2% stop-loss) consistently outperforms V2 across all intervals, with +89,716 AED higher P&L and better risk-adjusted returns.

##  License

[Add your license here]

##  Contributing

1. Create strategy branch: `git checkout -b strategy/v4-my-strategy`
2. Implement strategy inheriting from `BaseMarketMakingStrategy`
3. Add tests and documentation
4. Run full backtest and compare to baseline
5. Submit pull request with results
