# Tick Backtest Project - AI Coding Agent Instructions

## Project Overview

This is a **market-making strategy backtesting framework** for simulating trading strategies on historical tick data. It uses a **streaming architecture** to process 670k+ row Excel datasets efficiently via chunked processing (100k rows/chunk). The framework supports multiple strategy variations with clean separation, realistic FIFO queue fill simulation, and comprehensive performance comparison tools.

## Architecture Pattern

**Streaming Processor with Pluggable Strategy Handler**

```
Excel Data → stream_sheets() → Chunks → Handler → OrderBook + Strategy → Results
                ↓                ↓          ↓            ↓
           data_loader.py    backtest    handler.py   strategy.py
```

### Key Components

1. **Base Strategy** (`src/strategies/base_strategy.py`): Abstract class defining `generate_quotes()` and `should_refill_side()` - ALL strategies inherit from this
2. **Strategy Implementation** (`src/strategies/{version}/strategy.py`): Concrete strategy logic
3. **Handler** (`src/strategies/{version}/handler.py`): Bridges strategy with backtest framework, processes chunks, manages state
4. **OrderBook** (`src/orderbook.py`): Minimal top-of-book tracker (best bid/ask only)
5. **Backtest Orchestrator** (`src/market_making_backtest.py`): Runs `stream_sheets()` and calls handlers chunk-by-chunk

### Critical State Management

Strategies maintain per-security state across chunks:
- `position`: Current inventory (shares)
- `entry_price`: Weighted average entry price
- `pnl`: Realized profit/loss
- `last_refill_time[side]`: Per-side quote timestamps (bid/ask independent)
- `active_orders[side]`: Current quote details with `ahead_qty`, `our_remaining`
- `quote_prices[side]`: Current quoted prices

**Why this matters**: State persists across 100k row chunks. Handler must sync strategy state to handler state dict each iteration.

## Data Format & Optimization ⚡

### Default Format: Apache Parquet

All backtest scripts now use **Parquet as the default data format** with automatic conversion:

**Benefits:**
- **5-10x faster I/O** than Excel (openpyxl parsing is slow)
- **50% smaller files** with columnar compression
- **True parallel reads** (no sheet locking like Excel)
- **Combined with parallelization**: 8-15x total speedup vs sequential Excel

**Auto-Conversion:**
```python
# All scripts automatically check/convert on first run
from src.parquet_utils import ensure_parquet_data
parquet_dir = ensure_parquet_data(excel_path, validate_data=True)
```

**Data Validation:**
Automatic validation checks before each run:
1. **Security Coverage**: All Excel securities present in Parquet
2. **Date Range Matching**: Start/end dates match exactly (no tolerance)
3. **Data Integrity**: Files readable, valid structure

If validation fails, user is prompted to auto-reconvert.

**Manual Operations:**
```bash
# One-time conversion (if needed)
python scripts/convert_excel_to_parquet.py

# Validate existing Parquet data
python scripts/validate_parquet_data.py

# Force reconversion
python scripts/convert_excel_to_parquet.py --force
```

**Files:**
- Utility: `src/parquet_utils.py` - Centralized Parquet management
- Output: `data/parquet/{security}.parquet` - Per-security files
- Compression: Snappy (default) for speed

**Fallback:** Scripts automatically fall back to Excel if Parquet issues detected.

## Running Backtests

### Primary Commands

**Sequential (Original)**:
```bash
# Run single strategy (generic interface)
python scripts/run_strategy.py --strategy v1_baseline

# Quick test on 5 securities
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5
```

**Parallel (3-8x Faster)** ✅ NEW:
```bash
# Run with auto-detected CPU count
python scripts/run_parallel_backtest.py --strategy v1_baseline

# Use 4 workers for testing
python scripts/run_parallel_backtest.py --strategy v1_baseline --workers 4 --max-sheets 5

# Benchmark comparison (sequential vs parallel)
python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark
```

**Parquet + Parallel (8-15x Faster)** ⚡ FASTEST:
```bash
# One-time setup: Convert Excel to Parquet
pip install pyarrow
python scripts/convert_excel_to_parquet.py

# Run with Parquet for maximum speed
python scripts/run_parquet_backtest.py --strategy v1_baseline

# Quick test (30-60 seconds vs 8-10 minutes sequential)
python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5
```

**Strategy Comparison**:
```bash
# Compare two strategies
python scripts/compare_strategies.py v1_baseline v2_price_follow_qty_cooldown

# Parameter sweep (checkpoint-safe)
python scripts/comprehensive_sweep.py
```

### Output Structure

```
output/
├── v1_baseline/                    # Per-strategy results
│   ├── {security}_trades_timeseries.csv  # Per-security trade log
│   └── backtest_summary.csv        # Aggregate metrics
├── v2_price_follow_qty_cooldown/
└── comparison/                     # Cross-strategy comparisons
```

## Creating New Strategies

### Required Steps

1. **Create strategy directory**: `src/strategies/v{N}_{name}/`
2. **Implement strategy class**: Inherit from `BaseMarketMakingStrategy`, implement:
   - `generate_quotes(security, best_bid, best_ask) -> dict` - Return `{bid_price, ask_price, bid_size, ask_size}`
   - `should_refill_side(security, timestamp, side) -> bool` - Return True to place new quote
3. **Create handler**: Factory function `create_v{N}_handler(config)` that returns a closure processing `(security, df, orderbook, state)`
4. **Add config**: `configs/v{N}_{name}_config.json` with per-security params (see below)
5. **Run**: `python scripts/run_strategy.py --strategy v{N}_{name}`

### Critical Handler Pattern

Handler must be a **closure** that captures the strategy instance:

```python
def create_v1_handler(config):
    strategy = V1BaselineStrategy(config=config)
    
    def v1_handler(security, df, orderbook, state):
        strategy.initialize_security(security)
        # Process each row, call strategy methods
        for row in df.itertuples():
            # 1. Apply to orderbook
            # 2. Check should_refill_side()
            # 3. Generate quotes
            # 4. Check liquidity
            # 5. Simulate fills
            # 6. Update state
        return state
    
    return v1_handler
```

## Configuration Format

Per-security parameters in JSON (`configs/{strategy}_config.json`):

```json
{
  "ADNOCGAS": {
    "quote_size": 65000,                         // Base quote size (shares)
    "refill_interval_sec": 180,                  // Quote refresh interval
    "max_position": 130000,                      // Max inventory (shares)
    "max_notional": 1500000,                     // Optional dollar cap (AED)
    "min_local_currency_before_quote": 13000     // Liquidity threshold (AED)
  }
}
```

## Trading Rules & Windows

**STRICT REQUIREMENTS** (enforced in handlers):

- **Trading hours**: 10:00:00 - 14:44:59 ONLY
- **Skip**: 9:30-10:00 (opening auction), 14:45+ (closing auction)
- **EOD Flatten**: Position flattened at 14:55:00 using next trade price
- **Daily Reset**: OrderBook cleared on date changes

## Fill Simulation Logic

**FIFO Queue Model** (realistic market-making):

1. **Quote Placement**: Track `ahead_qty` (liquidity ahead in queue at our price)
2. **Trade Processing**: 
   - If trade at our quote price: `ahead_qty -= trade_volume`
   - If `ahead_qty <= 0`: We get filled for `min(our_remaining, abs(ahead_qty))`
   - Update position, record trade, calculate P&L
3. **Partial Fills**: Supported - `our_remaining` tracks unfilled portion

See [`FILL_REFILL_LOGIC_EXPLAINED.md`](../FILL_REFILL_LOGIC_EXPLAINED.md) for detailed walkthrough.

## Performance Metrics

**Standard outputs** (`backtest_summary.csv` columns):
- `realized_pnl`, `trades`, `market_dates`, `strategy_dates`

**Advanced metrics** (in sweeps):
- **Sharpe Ratio**: Risk-adjusted returns (>1 good, >2 excellent)
- **Max Drawdown**: Peak-to-trough decline (percent)
- **Calmar Ratio**: Return / Max Drawdown
- **Win Rate**: Percentage profitable trades
- **Profit Factor**: Gross profits / Gross losses

## Common Pitfalls

1. **Handler returns None**: Handler must return state dict or `state = handler(...) or state`
2. **State not synced**: Update handler state from strategy state after each chunk
3. **OrderBook pollution**: Clear orderbook on date changes to prevent cross-day contamination
4. **EOD flatten missing**: Must check `is_eod_close_time()` and call `flatten_position()`
5. **Liquidity check skipped**: Calculate `price * ahead_qty >= min_local_currency_before_quote` before placing quote
6. **Handler naming**: Must be `create_v{N}_{name}_handler` or `create_handler` for auto-discovery

## Data Format

**Input**: `data/raw/TickData.xlsx`
- **Sheets**: Named `{SECURITY} UH Equity` or `{SECURITY} DH Equity`
- **Header row**: Row 3 (index 3 in code)
- **Columns**: `Date`, `Time`, `Type`, `Price`, `Volume`
- **Types**: `bid`, `ask`, `trade` (case-insensitive)

**Preprocessing**: `preprocess_chunk_df()` combines Date+Time → timestamp, normalizes columns

## Strategy Status (Jan 2026)

- **V1 Baseline**: Reference implementation, proven (P&L: +697k AED @ 180s)
- **V2 Price Follow Qty Cooldown**: BEST PERFORMING (P&L: +1.24M AED @ 10s, Sharpe 14.95)
- **V2.1 Stop Loss**: V2 variant with stop-loss protection
- **V3 Liquidity Monitor**: ABANDONED (poor performance, too restrictive)

## Key Files for Context

- [`MULTI_STRATEGY_GUIDE.md`](../MULTI_STRATEGY_GUIDE.md): Complete architecture guide
- [`FILL_REFILL_LOGIC_EXPLAINED.md`](../FILL_REFILL_LOGIC_EXPLAINED.md): Detailed quote/fill mechanics
- [`PARAMETER_SWEEP_GUIDE.md`](../PARAMETER_SWEEP_GUIDE.md): How to run parameter optimization
- [`STRATEGY_TECHNICAL_DOCUMENTATION.md`](../STRATEGY_TECHNICAL_DOCUMENTATION.md): Deep technical details

## Testing & Validation

**No formal unit tests**. Validation approach:
1. Run with `--max-sheets 5` for quick validation
2. Compare against V1 baseline using `compare_strategies.py`
3. Check `backtest_summary.csv` for reasonable P&L, trade counts
4. Use `scripts/strategy_trace_testing_eventbyevent.py` for event-level debugging

## Module Import Pattern

Handlers need parent directory in path:

```python
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from strategies.base_strategy import BaseMarketMakingStrategy
```

This is the established pattern - don't refactor to package imports.

## Data Format Optimization ⚡ NEW

### Excel to Parquet Conversion

**One-time conversion** for 5-10x I/O speedup:

```bash
# Install PyArrow
pip install pyarrow

# Convert Excel to per-security Parquet files
python scripts/convert_excel_to_parquet.py

# Verify conversion
# Creates data/parquet/{security}.parquet files
# ~50% smaller with faster read times
```

**Benefits**:
- **5-10x faster I/O** than Excel (openpyxl parsing is slow)
- **True parallel reads** (no sheet locking like Excel)
- **50% smaller files** with columnar compression
- **Native pandas integration** with optimized C++ engine
- **Combined with parallelization**: 8-15x total speedup vs sequential Excel

**Usage**:
```bash
# Run with Parquet instead of Excel
python scripts/run_parquet_backtest.py --strategy v1_baseline

# All parallel options supported
python scripts/run_parquet_backtest.py --strategy v1_baseline --workers 8 --max-sheets 5
```

**Performance Comparison**:
- Excel Sequential: 8-10 minutes
- Excel Parallel (4 cores): 2-3 minutes (3-4x)
- Parquet Parallel (4 cores): 30-60 seconds (8-15x) ⚡

See [`PARQUET_GUIDE.md`](../PARQUET_GUIDE.md) for complete conversion guide.

## Performance & Parallelization

### Current Bottlenecks

**Sequential Processing (Original)**: The architecture processes securities one-by-one sequentially:
1. `stream_sheets()` yields (sheet_name, chunk) as generator
2. Main loop processes each security's chunks serially
3. Typical runtime: ~8-10 minutes for 673k rows across 16 securities

### Parallelization Opportunities

**HIGH IMPACT: Per-Security Parallelization** ✅ RECOMMENDED
- Securities are fully independent (separate orderbooks, state, configs)
- Can process multiple securities in parallel using `ProcessPoolExecutor`
- Expected speedup: Near-linear with CPU cores (4-8x on modern hardware)
- Implementation pattern:
  ```python
  from concurrent.futures import ProcessPoolExecutor
  
  def process_single_security(sheet_name, file_path, config, chunk_size):
      # Load data for just this security
      # Run handler for all chunks
      # Return results
      pass
  
  with ProcessPoolExecutor(max_workers=cpu_count()) as executor:
      futures = [executor.submit(process_single_security, sheet, ...) 
                 for sheet in sheets]
      results = [f.result() for f in futures]
  ```

**MEDIUM IMPACT: Excel I/O Optimization**
- Current: `openpyxl` read_only mode with streaming
- Alternative: Pre-convert Excel to Parquet/CSV partitioned by security
- Benefit: Faster I/O, easier parallelization, no Excel parsing overhead

**LOW IMPACT: Within-Security Parallelization** ⚠️ NOT RECOMMENDED
- Chunks within a security have state dependencies (orderbook, position)
- Would require complex state merging/synchronization
- Overhead likely exceeds benefits

### Optimization Quick Wins

1. **Pre-filter data**: Use `only_trades=True` if strategy doesn't need bid/ask updates
2. **Adjust chunk size**: Test 50k-200k rows (current: 100k)
3. **Reduce I/O**: Set `write_csv=False` during testing
4. **Profile first**: Add timing to identify actual bottlenecks before optimizing

### Parallel Sweep Pattern

For parameter sweeps, run strategy variations in parallel:
```bash
# Terminal 1: V1 strategies
python scripts/comprehensive_sweep.py --strategies v1 --output-dir output/sweep_v1

# Terminal 2: V2 strategies  
python scripts/comprehensive_sweep.py --strategies v2 --output-dir output/sweep_v2
```

Each run is independent - manually merge results afterward.
