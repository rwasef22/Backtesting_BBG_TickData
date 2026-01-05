# Tick Backtest Project - AI Coding Agent Instructions

## Project Overview

This is a **market-making strategy backtesting framework** for simulating trading strategies on historical tick data. It uses a **streaming architecture** to process 670k+ row Excel datasets efficiently via chunked processing (100k rows/chunk). The framework supports multiple strategy variations with clean separation, realistic FIFO queue fill simulation, and comprehensive performance comparison tools.

## Architecture Pattern

**Streaming Processor with Pluggable Strategy Handler**

```
Excel/Parquet Data  Parallel Workers  Handler  OrderBook + Strategy  Results
                                                      
                  parallel_backtest.py  handler.py   strategy.py
```

### Key Components

1. **Base Strategy** (`src/strategies/base_strategy.py`): Abstract class defining `generate_quotes()` and `should_refill_side()` - ALL strategies inherit from this
2. **Strategy Implementation** (`src/strategies/{version}/strategy.py`): Concrete strategy logic
3. **Handler** (`src/strategies/{version}/handler.py`): Bridges strategy with backtest framework, processes chunks, manages state
4. **OrderBook** (`src/orderbook.py`): Minimal top-of-book tracker (best bid/ask only)
5. **Parallel Backtest** (`src/parallel_backtest.py`): Parallel execution engine using ProcessPoolExecutor

### Critical State Management

Strategies maintain per-security state across chunks:
- `position`: Current inventory (shares)
- `entry_price`: Weighted average entry price
- `pnl`: Realized profit/loss
- `last_refill_time[side]`: Per-side quote timestamps (bid/ask independent)
- `active_orders[side]`: Current quote details with `ahead_qty`, `our_remaining`
- `quote_prices[side]`: Current quoted prices

## Strategy Status (Current as of Jan 2026)

| Strategy | Status | P&L | Sharpe | Best Interval |
|----------|--------|-----|--------|---------------|
| `v1_baseline` | Reference | 697k AED | 12.7 | 180s |
| `v2_price_follow_qty_cooldown` | Good | 1.32M AED | 14.2 | 5s |
| **`v2_1_stop_loss`** | **BEST**  | **1.41M AED** | **15.0** | **5s** |
| `v3_liquidity_monitor` | ABANDONED | 400k AED | 8.5 | - |

### V2.1 Stop-Loss Strategy (RECOMMENDED)

The best-performing strategy extends V2 with 2% stop-loss protection:
- Automatically exits positions when unrealized losses exceed 2%
- +6.8% higher P&L than V2
- Better risk-adjusted returns (Sharpe 14.96 vs 14.19)
- Lower maximum drawdown

## Data Format & Optimization

### Default: Apache Parquet (8-15x faster)

```bash
# One-time conversion
python scripts/convert_excel_to_parquet.py

# All backtest scripts then use Parquet automatically
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss
```

**Performance:**
| Method | Runtime | Speedup |
|--------|---------|---------|
| Excel Sequential | 8-10 min | 1x |
| Excel Parallel | 2-3 min | 3-4x |
| **Parquet Parallel** | **30-60 sec** | **8-15x**  |

## Running Backtests

### Primary Commands

**Fastest (Parquet + Parallel)**  RECOMMENDED:
```bash
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss --max-sheets 5  # Quick test
```

**V2 vs V2.1 Parameter Sweep**:
```bash
python scripts/fast_sweep.py --intervals 5 10 30 60  # Full sweep
python scripts/fast_sweep.py --max-sheets 5 --intervals 30 60  # Quick test
```

**Parallel (Excel)**:
```bash
python scripts/run_parallel_backtest.py --strategy v1_baseline
python scripts/run_parallel_backtest.py --strategy v1_baseline --benchmark
```

**Sequential (Reference)**:
```bash
python scripts/run_strategy.py --strategy v1_baseline
```

### Strategy Comparison

```bash
python scripts/compare_strategies.py v1_baseline v2_1_stop_loss
python scripts/compare_strategies.py --all
```

## Creating New Strategies

### Required Steps

1. **Create strategy directory**: `src/strategies/v{N}_{name}/`
2. **Implement strategy class**: Inherit from `BaseMarketMakingStrategy`, implement:
   - `generate_quotes(security, best_bid, best_ask, timestamp) -> dict`
   - `should_refill_side(security, timestamp, side) -> bool`
3. **Create handler**: Factory function `create_v{N}_{name}_handler(config)` returning closure
4. **Add config**: `configs/v{N}_{name}_config.json`
5. **Run**: `python scripts/run_parquet_backtest.py --strategy v{N}_{name}`

### Handler Pattern (Critical)

Handler must be a **closure** capturing the strategy instance:

```python
def create_v4_my_strategy_handler(config):
    strategy = V4MyStrategy(config=config)
    
    def handler(security, df, orderbook, state):
        strategy.initialize_security(security)
        for row in df.itertuples():
            # 1. Time window checks
            # 2. Stop-loss check (if applicable)
            # 3. Orderbook update
            # 4. Quote generation
            # 5. Trade processing
            # 6. EOD flatten
        return state
    
    return handler
```

## Configuration Format

Per-security parameters in JSON:

```json
{
  "ADNOCGAS": {
    "quote_size": 65000,
    "refill_interval_sec": 5,
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
| `refill_interval_sec` | int | Cooldown after fills (seconds) |
| `max_position` | int | Maximum inventory (shares) |
| `max_notional` | int | Optional dollar cap (AED) |
| `min_local_currency_before_quote` | int | Liquidity threshold (AED) |
| `stop_loss_threshold_pct` | float | Stop-loss trigger (%, V2.1 only) |

## Trading Rules & Windows

**STRICT REQUIREMENTS** (enforced in handlers):

- **Trading hours**: 10:00:00 - 14:44:59 ONLY
- **Skip**: 9:30-10:00 (opening auction), 14:45+ (closing auction)
- **EOD Flatten**: Position flattened at 14:55:00 using next trade price
- **Daily Reset**: OrderBook cleared on date changes

## Fill Simulation Logic

**FIFO Queue Model**:

1. **Quote Placement**: Track `ahead_qty` (liquidity ahead in queue at our price)
2. **Trade Processing**:
   - If trade at our quote price: `ahead_qty -= trade_volume`
   - If `ahead_qty <= 0`: We get filled for `min(our_remaining, abs(ahead_qty))`
3. **Partial Fills**: Supported - `our_remaining` tracks unfilled portion

## Output Structure

```
output/
 v2_1_stop_loss/                 # Per-strategy results
    {security}_trades.csv       # Per-security trade log
    backtest_summary.csv        # Aggregate metrics
 sweep_v2_v21/                   # Sweep results
    sweep_results.csv
    cumulative_pnl_by_strategy.png
    v2_5s/, v2_1_5s/, etc.
 comparison/
```

## Key Scripts Reference

| Script | Purpose | Example |
|--------|---------|---------|
| `run_parquet_backtest.py` | Fastest runner  | `--strategy v2_1_stop_loss` |
| `fast_sweep.py` | V2 vs V2.1 sweep | `--intervals 5 10 30 60` |
| `run_parallel_backtest.py` | Excel parallel | `--strategy v1_baseline --benchmark` |
| `run_strategy.py` | Sequential ref | `--strategy v1_baseline` |
| `comprehensive_sweep.py` | Full V1/V2 sweep | `--intervals 10 30 60 120 300` |
| `convert_excel_to_parquet.py` | Data conversion | (one-time) |
| `compare_strategies.py` | Compare results | `v1_baseline v2_1_stop_loss` |

## Key Documentation Files

- `README.md` - Quick start and overview
- `docs/SCRIPTS_REFERENCE.md` - Detailed script documentation
- `docs/strategies/v2_1_stop_loss/` - V2.1 strategy docs
- `docs/strategies/v2_price_follow_qty_cooldown/` - V2 strategy docs
- `FILL_REFILL_LOGIC_EXPLAINED.md` - Quote/fill mechanics
- `MULTI_STRATEGY_GUIDE.md` - Architecture guide
- `PARQUET_GUIDE.md` - Data format optimization

## Common Pitfalls

1. **Handler returns None**: Handler must return state dict
2. **State not synced**: Update handler state from strategy state after processing
3. **OrderBook pollution**: Clear orderbook on date changes
4. **EOD flatten missing**: Must check `is_eod_close_time()` and call `flatten_position()`
5. **Stop-loss not checked**: V2.1 must call `check_stop_loss()` on every trade event
6. **Parquet not converted**: Run `convert_excel_to_parquet.py` first

## Module Import Pattern

Handlers need parent directory in path:

```python
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from strategies.base_strategy import BaseMarketMakingStrategy
```

## Latest Sweep Results (Jan 2026)

```
Strategy    Interval  Trades      P&L (AED)     Sharpe   
----------  --------  ----------  ------------  -------  
V2          5s        283,309     1,319,147.87  14.19    
V2          10s       277,212     1,273,433.17  13.92    
V2.1        5s        283,781     1,408,863.92  14.96   BEST
V2.1        10s       277,624     1,365,515.77  14.80    
```

**Key Finding**: V2.1 @ 5s is the optimal configuration with +89,716 AED higher P&L than V2 and better risk-adjusted returns.
