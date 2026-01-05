# Market-Making Backtest Framework

A flexible, modular framework for backtesting market-making strategies on historical tick data. Supports multiple strategy variations with clean separation, comparison tools, and comprehensive documentation.

## Features

- 📊 **Streaming Architecture**: Memory-efficient chunk-based processing of large datasets
- 🎯 **Multiple Strategies**: Modular design supports unlimited strategy variations
- 📈 **Realistic Simulation**: FIFO queue simulation for accurate fill modeling
- ⚙️ **Configurable**: JSON-based per-security parameter configuration
- 📉 **Comparison Tools**: Built-in utilities to compare strategy performance
- 📝 **Well Documented**: Technical and non-technical documentation for each strategy
- 🔍 **Position Management**: Sophisticated P&L tracking with weighted average entry prices

## Quick Start

### Installation

```bash
# Clone repository
cd tick-backtest-project

# Install dependencies (if using virtual environment)
pip install pandas openpyxl matplotlib
```

### Run a Backtest

```bash
# Sequential version (reference implementation)
python scripts/run_strategy.py --strategy v1_baseline

# Parallel version (3-8x faster) ⚡ NEW
python scripts/run_parallel_backtest.py --strategy v1_baseline

# Quick test with 5 securities
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5

# Convert to Parquet for maximum speed (one-time) 🚀 NEW
pip install pyarrow
python scripts/convert_excel_to_parquet.py

# Run with Parquet + parallel (8-15x faster) 🚀 FASTEST
python scripts/run_parquet_backtest.py --strategy v1_baseline

# Benchmark comparison
python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark
```

### Compare Strategies

```bash
# Compare two strategies
python scripts/compare_strategies.py v1_baseline v2_aggressive_refill

# Compare all strategies
python scripts/compare_strategies.py --all
```

## Project Structure

```
tick-backtest-project/
├── src/                           # Core framework code
│   ├── strategies/                # Strategy variations
│   │   ├── base_strategy.py       # Abstract base class
│   │   └── v1_baseline/           # Baseline implementation
│   │       ├── strategy.py        # Strategy logic
│   │       └── handler.py         # Data processor
│   ├── orderbook.py               # Best bid/ask state manager
│   ├── data_loader.py             # Excel streaming reader
│   ├── market_making_backtest.py  # Backtest orchestrator (sequential)
│   ├── parallel_backtest.py       # Parallel backtest engine ⚡ NEW
│   └── config_loader.py           # JSON config loader
│
├── scripts/                       # Executable scripts
│   ├── run_strategy.py            # Sequential strategy runner
│   ├── run_parallel_backtest.py   # Parallel strategy runner ⚡ NEW
│   ├── test_parallel_backtest.py  # Parallel tests ⚡ NEW
│   └── compare_strategies.py      # Strategy comparison tool
│
├── configs/                       # Strategy configurations
│   └── v1_baseline_config.json    # V1 parameters
│
├── docs/strategies/               # Strategy documentation
│   └── v1_baseline/
│       ├── TECHNICAL_DOCUMENTATION.md
│       ├── NON_TECHNICAL_EXPLANATION.md
│       └── README.md
│
├── output/                        # Results (gitignored)
│   ├── v1_baseline/               # Per-strategy results
│   └── comparison/                # Comparison outputs
│
├── data/raw/                      # Input data (gitignored)
│   └── TickData.xlsx
│
└── MULTI_STRATEGY_GUIDE.md       # Architecture guide
```

## Current Strategies

### V1 Baseline (Production Ready)

The reference implementation with proven performance:

- **P&L**: +697,122 AED on full dataset
- **Trades**: 142,917 executions
- **Coverage**: 100% trading days for most securities
- **Logic**: Time-based refill, position-aware sizing

**Files**: `src/strategies/v1_baseline/`, `docs/strategies/v1_baseline/`

See [V1 Baseline README](docs/strategies/v1_baseline/README.md) for details.

## Creating New Strategies

### 1. Inherit from Base Class

```python
from strategies.base_strategy import BaseMarketMakingStrategy

class V2MyStrategy(BaseMarketMakingStrategy):
    def generate_quotes(self, security, best_bid, best_ask):
        # Your quote logic
        pass
    
    def should_refill_side(self, security, timestamp, side):
        # Your refill logic
        pass
```

### 2. Create Handler

```python
from strategies.v2_my_strategy.strategy import V2MyStrategy

def create_v2_handler(config=None):
    strategy = V2MyStrategy(config=config)
    # ... handler logic ...
    return handler
```

### 3. Run and Compare

```bash
python scripts/run_strategy.py --strategy v2_my_strategy
python scripts/compare_strategies.py v1_baseline v2_my_strategy
```

See [Multi-Strategy Guide](MULTI_STRATEGY_GUIDE.md) for complete instructions.

## Configuration

Each strategy has a JSON config file with per-security parameters:

```json
{
  "ADNOCGAS": {
    "quote_size": 65000,
    "refill_interval_sec": 180,
    "max_position": 130000,
    "max_notional": 1500000,
    "min_local_currency_before_quote": 13000
  }
}
```

**Parameters**:
- `quote_size`: Shares to quote per side
- `refill_interval_sec`: Quote refresh interval
- `max_position`: Maximum inventory (shares)
- `max_notional`: Optional dollar cap
- `min_local_currency_before_quote`: Liquidity threshold (AED)

## Data Format

Expected Excel structure:

- **File**: `data/raw/TickData.xlsx`
- **Sheets**: Named `{SECURITY} UH Equity` or `{SECURITY} DH Equity`
- **Columns**: `Date`, `Time`, `Type`, `Price`, `Volume`
- **Types**: `bid`, `ask`, `trade`

The framework automatically:
- Streams data in chunks (100k rows default)
- Normalizes column names
- Combines date/time fields
- Handles missing values

## Key Features

### Memory Efficient Streaming

```python
# Processes 670k+ rows without loading entire file
for sheet_name, chunk_df in stream_sheets(file_path, chunk_size=100000):
    # Process chunk
    pass
```

### Realistic Fill Simulation

- **FIFO Queue**: Models realistic queue priority
- **Ahead Quantity**: Tracks liquidity ahead in queue
- **Partial Fills**: Simulates partial execution
- **Price Priority**: Respects price-time priority rules

### Position Management

- **Weighted Average Entry**: Accurate entry price tracking
- **Realized P&L**: Locks in P&L on position closes
- **Unrealized P&L**: Mark-to-market of open positions
- **Position Limits**: Hard caps prevent runaway risk

### Time Window Management

- **Opening Auction**: 9:30-10:00 (book updates only)
- **Silent Period**: 10:00-10:05 (skip entirely)
- **Closing Auction**: 14:45-15:00 (skip)
- **EOD Flatten**: >= 14:55 (force close all positions)

## Performance

**Typical Performance** (16 securities, 673k rows):
- **Processing Time**: 8-10 minutes
- **Memory Usage**: 500MB-1GB peak
- **Throughput**: 1,100-1,400 rows/second

**Optimization**:
- Chunk size adjustment: `--chunk-size 50000` (less memory) or `200000` (faster)
- Security limit: `--max-sheets 5` for quick testing

## Output Files

### Per-Security Trade Timeseries

`output/{strategy}/{security}_trades_timeseries.csv`:

```csv
timestamp,side,fill_price,fill_qty,realized_pnl,position,pnl
2025-01-15 10:05:23,buy,3.50,30000,0.0,30000,0.0
2025-01-15 10:08:41,sell,3.52,30000,600.0,0,600.0
```

### Backtest Summary

`output/{strategy}/backtest_summary.csv`:

```csv
security,trades,final_position,realized_pnl,rows_processed,market_dates,strategy_dates
ADNOCGAS,8947,0,43570.50,42156,136,136
ADCB,9823,0,52341.25,38947,128,127
```

### Strategy Comparison

`output/comparison/strategy_comparison.csv`:

```csv
strategy,total_trades,total_pnl,num_securities,avg_pnl_per_security,trading_day_coverage
v1_baseline,142917,697122.45,16,43570.15,98.5
v2_aggressive,156234,645283.12,16,40330.20,99.2
```

## Testing

### Quick Test (5 Securities)

```bash
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5
```

### Full Backtest

```bash
python scripts/run_strategy.py --strategy v1_baseline
```

### Validation

```bash
# Check for errors
python scripts/run_strategy.py --strategy v1_baseline > output/run.log 2>&1

# Compare to baseline
python scripts/compare_strategies.py v1_baseline v2_my_strategy
```

## Documentation

- **[Multi-Strategy Guide](MULTI_STRATEGY_GUIDE.md)**: Complete architecture documentation
- **[V1 Technical Docs](docs/strategies/v1_baseline/TECHNICAL_DOCUMENTATION.md)**: Developer reference
- **[V1 Non-Technical](docs/strategies/v1_baseline/NON_TECHNICAL_EXPLANATION.md)**: Business explanation
- **[V1 README](docs/strategies/v1_baseline/README.md)**: Strategy overview

## Git Workflow

```bash
# Create strategy branch
git checkout -b strategy/v2-aggressive-refill

# Develop strategy
# ... code changes ...

# Commit
git add src/strategies/v2_aggressive_refill/
git commit -m "Add V2 aggressive refill strategy"

# Tag stable version
git tag -a v2_aggressive_refill-v1.0 -m "First validated version"

# Merge to main
git checkout main
git merge strategy/v2-aggressive-refill
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'strategies.v2_xxx'`

**Solution**: Ensure `__init__.py` exists in strategy directory

### No Results

**Problem**: `Warning: No results found for v2_xxx`

**Solution**: Run strategy first: `python scripts/run_strategy.py --strategy v2_xxx`

### Memory Errors

**Problem**: `MemoryError` or system freezes

**Solution**: Reduce chunk size: `--chunk-size 50000`

## Requirements

- Python 3.7+
- pandas
- openpyxl (for Excel reading)
- matplotlib (for plots)

## License

[Add your license here]

## Contributing

1. Create strategy branch
2. Implement strategy inheriting from `BaseMarketMakingStrategy`
3. Document changes in `CHANGES_FROM_V1.md`
4. Run full backtest and compare to baseline
5. Submit pull request with results

## Contact

[Add contact information here]

## Acknowledgments

- Original strategy developed for UAE equities market
- Framework designed for academic and research purposes
- Tested on 16 securities with 142,917 executed trades
