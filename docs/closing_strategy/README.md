# Closing Auction Arbitrage Strategy

## Table of Contents
1. [Strategy Overview](#strategy-overview)
2. [How It Works (Non-Technical)](#how-it-works-non-technical)
3. [Technical Documentation](#technical-documentation)
4. [Configuration Reference](#configuration-reference)
5. [Running the Backtest](#running-the-backtest)
6. [Parameter Sweeps](#parameter-sweeps)
7. [Assumptions & Limitations](#assumptions--limitations)
8. [Output Files](#output-files)

---

## Strategy Overview

The **Closing Auction Arbitrage Strategy** exploits predictable price relationships between:
- The **VWAP (Volume Weighted Average Price)** calculated during pre-close trading
- The **Closing Auction Price** determined at market close
- The **Next Day's VWAP** when exiting positions

### Key Concept
The closing auction price often deviates from the pre-close VWAP. By placing limit orders at a spread around the VWAP, we can profit when:
1. The closing price crosses our order price (we get filled)
2. The price mean-reverts the next day toward VWAP (we exit profitably)

---

## How It Works (Non-Technical)

### The Trading Day Timeline

```
10:00 ─────────────────────────────────────────────────────── 14:30 ── 14:45 ── 14:55 ── 15:00
  │                                                             │        │        │        │
  │  Regular Trading Session                                    │  VWAP  │ Auction│ Close  │
  │  - Monitor positions                                        │ Calc   │ Orders │ Auction│
  │  - Execute exit orders from previous day                    │ Period │ Placed │ Exec.  │
  │  - Stop-loss protection active                              │        │        │        │
```

### Daily Workflow

#### Phase 1: Morning (10:00 - 14:30)
- **Exit Previous Day's Position**: If we entered a position yesterday at the closing auction, we exit today at VWAP prices
- **Stop-Loss Monitoring**: If our position is losing more than 2%, we exit immediately at the best available price

#### Phase 2: Pre-Close VWAP Calculation (14:30 - 14:45)
- Calculate the Volume Weighted Average Price from all trades
- This VWAP will be our reference price for placing auction orders

#### Phase 3: Auction Order Placement (14:45)
- **Buy Order**: Place at VWAP × (1 - spread%), e.g., VWAP × 99.5%
- **Sell Order**: Place at VWAP × (1 + spread%), e.g., VWAP × 100.5%
- Order size is determined by the configured notional value (e.g., 1,000,000 AED)

#### Phase 4: Closing Auction Execution (14:55 - 15:00)
- If the closing price ≤ our buy order price → **Buy executed**
- If the closing price ≥ our sell order price → **Sell executed**
- Fill quantity limited to 10% of total auction volume (realistic assumption)

#### Phase 5: Next Day Exit
- Exit the position at VWAP price during regular trading hours
- The VWAP exit price is the same VWAP we used as reference when entering

### Example Trade

1. **Pre-close VWAP**: 10.00 AED
2. **Spread**: 0.5%
3. **Buy order placed**: 9.95 AED (VWAP - 0.5%)
4. **Sell order placed**: 10.05 AED (VWAP + 0.5%)
5. **Closing price**: 9.90 AED → **Buy order filled!**
6. **Next day**: Exit at 10.00 AED (VWAP)
7. **Profit**: (10.00 - 9.90) × quantity = **0.10 AED per share**

### Risk Management

1. **Stop-Loss (2% default)**: Exits position if unrealized loss exceeds threshold
2. **Auction Fill Limit (10%)**: Won't assume fills larger than 10% of auction volume
3. **Position Limits**: Controlled by notional value configuration per security
4. **EOD Flatten**: Unfilled positions are closed at end of day

---

## Technical Documentation

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Backtest Runner                                 │
│                    (run_closing_strategy.py)                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │  Parquet Data    │───▶│     Handler      │───▶│    Strategy      │   │
│  │  (16 securities) │    │  (handler.py)    │    │  (strategy.py)   │   │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘   │
│                                 │                        │               │
│                                 ▼                        ▼               │
│                          ┌──────────────────────────────────────┐       │
│                          │           Output Files               │       │
│                          │  - Per-security trade logs           │       │
│                          │  - Summary statistics                │       │
│                          │  - Visualization plots               │       │
│                          └──────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Classes

#### `ClosingStrategy` (strategy.py)
Main strategy class implementing all trading logic.

```python
class ClosingStrategy:
    # Market Hours (UAE)
    PRECLOSE_END_TIME = time(14, 45, 0)      # VWAP calc ends
    CLOSING_AUCTION_TIME = time(14, 55, 0)   # Auction starts
    TRADING_START_TIME = time(10, 0, 0)      # Regular session
    TRADING_END_TIME = time(14, 45, 0)       # Regular session ends
    
    # Key Methods:
    # - update_vwap(): Accumulate VWAP data during pre-close
    # - place_auction_orders(): Generate buy/sell orders at spread
    # - process_closing_price(): Check if orders filled at auction
    # - process_exit_order(): Fill exit orders during next day
    # - check_stop_loss(): Monitor and execute stop-loss
```

#### `Trade` (dataclass)
Represents an executed trade:
```python
@dataclass
class Trade:
    timestamp: datetime
    side: str           # 'buy' or 'sell'
    price: float
    quantity: int
    realized_pnl: float
    trade_type: str     # 'auction_entry', 'vwap_exit', 'stop_loss', 'eod_flatten'
    vwap_reference: float
```

### Trading Logic Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        For Each Tick Event                              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. DATE CHANGE CHECK                                                   │
│     └─▶ Reset daily state, process pending auctions                     │
│                                                                         │
│  2. ORDERBOOK UPDATE                                                    │
│     └─▶ Track best bid/ask for stop-loss pricing                       │
│                                                                         │
│  3. STOP-LOSS CHECK (10:10 - 14:44)                                    │
│     └─▶ If unrealized loss > threshold% → Exit at best opposite price  │
│                                                                         │
│  4. EXIT ORDER PROCESSING (10:00 - 14:45)                              │
│     └─▶ If trade price crosses exit price → Fill (partial/full)        │
│                                                                         │
│  5. VWAP ACCUMULATION (configurable period before 14:45)               │
│     └─▶ sum_pv += price × volume; sum_v += volume                      │
│                                                                         │
│  6. AUCTION ORDER PLACEMENT (at 14:45)                                 │
│     └─▶ Calculate VWAP, place buy/sell orders at spread                │
│                                                                         │
│  7. AUCTION VOLUME TRACKING (14:55 - 15:00)                            │
│     └─▶ Accumulate volume for fill limit calculation                   │
│                                                                         │
│  8. CLOSING PRICE PROCESSING (last trade of auction)                   │
│     └─▶ Check order fills, create exit orders for next day             │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Exchange-Specific Tick Sizes

The strategy uses exchange-specific tick sizes for order pricing:

**ADX (Abu Dhabi Securities Exchange):**
| Price Range | Tick Size |
|------------|-----------|
| < 1 AED | 0.001 |
| 1 - 10 AED | 0.01 |
| 10 - 50 AED | 0.02 |
| 50 - 100 AED | 0.05 |
| ≥ 100 AED | 0.1 |

**DFM (Dubai Financial Market):**
| Price Range | Tick Size |
|------------|-----------|
| < 1 AED | 0.001 |
| 1 - 10 AED | 0.01 |
| ≥ 10 AED | 0.05 |

---

## Configuration Reference

### Config File Structure

```json
{
  "SECURITY_NAME": {
    "vwap_preclose_period_min": 15,
    "spread_vwap_pct": 0.5,
    "order_notional": 1000000,
    "stop_loss_threshold_pct": 2.0
  }
}
```

### Parameters Explained

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vwap_preclose_period_min` | int | 15 | Minutes before 14:45 to calculate VWAP (e.g., 15 = 14:30-14:45) |
| `spread_vwap_pct` | float | 0.5 | Percentage spread around VWAP for orders (e.g., 0.5 = ±0.5%) |
| `order_notional` | int | 250000 | Order size in local currency (AED). Quantity = notional / VWAP |
| `stop_loss_threshold_pct` | float | 2.0 | Exit position if unrealized loss exceeds this percentage |

### Exchange Mapping File

```json
{
  "EMAAR": "DFM",
  "ALDAR": "ADX",
  "FAB": "ADX",
  ...
}
```

---

## Running the Backtest

### Prerequisites

```bash
# Ensure you're in the project directory
cd tick-backtest-project

# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Convert Excel data to Parquet (one-time, 8-15x faster)
python scripts/convert_excel_to_parquet.py
```

### Basic Backtest

```bash
# Run with default configuration
python scripts/run_closing_strategy.py

# Quick test with limited securities
python scripts/run_closing_strategy.py --max-sheets 5

# Disable plot generation (faster)
python scripts/run_closing_strategy.py --no-plots
```

### Custom Configuration

```bash
# Use custom config file
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_1m_cap.json

# Override spread for all securities
python scripts/run_closing_strategy.py --spread 0.75

# Override VWAP period for all securities
python scripts/run_closing_strategy.py --vwap-period 30

# Override stop-loss threshold
python scripts/run_closing_strategy.py --stop-loss 1.5

# Custom output directory
python scripts/run_closing_strategy.py --output-dir output/my_backtest

# Custom auction fill percentage (default 10%)
python scripts/run_closing_strategy.py --auction-fill-pct 5
```

### Full Example with Multiple Options

```bash
python scripts/run_closing_strategy.py \
    --config configs/closing_strategy_config_1m_cap.json \
    --output-dir output/test_run \
    --spread 0.5 \
    --vwap-period 15 \
    --stop-loss 2.0 \
    --auction-fill-pct 10 \
    --no-plots
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--config` | Path to config JSON file | `configs/closing_strategy_config.json` |
| `--output-dir` | Output directory | `output/closing_strategy` |
| `--max-sheets` | Limit number of securities | All |
| `--spread` | Override spread_vwap_pct | From config |
| `--vwap-period` | Override vwap_preclose_period_min | From config |
| `--stop-loss` | Override stop_loss_threshold_pct | From config |
| `--auction-fill-pct` | Max fill as % of auction volume | 10.0 |
| `--no-plots` | Disable plot generation | False |

---

## Parameter Sweeps

### VWAP Spread Sweep

Test different spread values to find optimal per-security settings:

```bash
# Edit sweep configuration in scripts/sweep_vwap_spread.py:
# param_name = 'spread_vwap_pct'
# param_values = [0.5, 1.0, 1.5, 2.0]

python scripts/sweep_vwap_spread.py
```

**Output:**
- `output/vwap_spread_sweep/sweep_all_results.csv` - All run results
- `output/vwap_spread_sweep/optimal_per_security.csv` - Best spread per security
- `output/vwap_spread_sweep/closing_strategy_config_optimal.json` - Optimized config

### VWAP Pre-Close Period Sweep

Test different VWAP calculation windows:

```bash
# Edit sweep configuration in scripts/sweep_vwap_spread.py:
# param_name = 'vwap_preclose_period_min'
# param_values = [15, 30, 45, 60]
# fixed_spread = 0.5  # Keep spread constant

python scripts/sweep_vwap_spread.py
```

### Creating Custom Sweeps

Modify the sweep script configuration section:

```python
def main():
    # === CONFIGURATION ===
    
    # Option 1: Sweep VWAP spread
    param_name = 'spread_vwap_pct'
    param_values = [0.25, 0.5, 0.75, 1.0]
    
    # Option 2: Sweep VWAP period
    # param_name = 'vwap_preclose_period_min'
    # param_values = [10, 15, 20, 30, 45, 60]
    # fixed_spread = 0.5
    
    # Config and output paths
    config_path = Path("configs/closing_strategy_config_1m_cap.json")
    output_dir = Path("output/my_custom_sweep")
```

### Notional Cap Testing

Create capped configurations for position sizing analysis:

```python
# Run in Python REPL or script
import json

# Load original config
with open('configs/closing_strategy_config.json') as f:
    config = json.load(f)

# Cap all notionals at 1M AED
cap = 1000000
for security in config:
    config[security]['order_notional'] = min(config[security]['order_notional'], cap)

# Save capped config
with open('configs/closing_strategy_config_1m_cap.json', 'w') as f:
    json.dump(config, f, indent=2)
```

Then run backtest with the capped config:

```bash
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_1m_cap.json
```

---

## Assumptions & Limitations

### Key Assumptions

1. **Fill Probability**: We assume fills up to 10% of auction volume. This is conservative but may still overestimate fills in low-liquidity situations.

2. **Execution Price**: Auction entries execute at the closing auction price (not our limit price). This is realistic for UAE markets.

3. **Exit Execution**: Exit orders fill when market trades at or through our price level, using actual trade volume for fill sizing.

4. **No Market Impact**: We assume our orders don't move the market. This is reasonable for fill sizes limited to 10% of auction volume.

5. **Perfect VWAP Exit**: We assume we can exit at the pre-close VWAP. In practice, this may require working the order.

6. **Stop-Loss Execution**: Stop-loss orders execute at the current best bid/ask, assuming sufficient liquidity.

7. **Single Position per Security**: We don't enter new auction positions while holding an existing position from the previous day.

### Limitations

1. **No Transaction Costs**: Commissions, fees, and slippage are not modeled. Add ~5-10 bps for realistic results.

2. **No Trading Calendar**: Weekends and holidays are not explicitly handled. The backtest relies on date changes in the data.

3. **No Intraday Position Sizing**: Position sizes are fixed per config, not dynamically adjusted based on volatility.

4. **Simplified Partial Fills**: Exit order partial fills use trade volume directly, without modeling queue position.

5. **No Short Selling Restrictions**: Strategy assumes both long and short positions are equally feasible.

---

## Output Files

### Trade Logs

Per-security trade files: `output/{run_name}/{SECURITY}_trades.csv`

| Column | Description |
|--------|-------------|
| timestamp | Trade execution time |
| side | 'buy' or 'sell' |
| price | Execution price |
| quantity | Shares traded |
| realized_pnl | P&L from this trade |
| trade_type | 'auction_entry', 'vwap_exit', 'stop_loss', 'eod_flatten' |
| vwap_reference | VWAP used for order calculation |
| security | Security symbol |

### Summary File

Aggregate statistics: `output/{run_name}/backtest_summary.csv`

| Column | Description |
|--------|-------------|
| security | Security symbol |
| total_trades | Number of trades |
| auction_entries | Auction fills |
| vwap_exits | VWAP exit fills |
| stop_losses | Stop-loss executions |
| eod_flattens | End-of-day position closures |
| pnl | Total realized P&L (AED) |

### Visualization Plots

Per-security charts: `output/{run_name}/plots/{SECURITY}_trades.png`

Each plot includes:
- **Price line** (1-minute aggregation)
- **Volume bars** (30-minute aggregation)
- **Entry markers** (▲ buy, ▼ sell)
- **Exit markers** (★ for all exits)
- **Cumulative P&L line** (purple)
- **Day shading** (alternating colors)

---

## Performance Benchmarks

Based on historical backtests (193 trading days):

| Configuration | Total P&L | Trades | Sharpe-like |
|--------------|-----------|--------|-------------|
| Original (variable notional) | 1,000,194 AED | 10,669 | - |
| 1M Cap | 635,137 AED | 8,842 | - |
| 2M Cap | 871,502 AED | 10,312 | - |
| Optimal Spread per Security | +9.6% vs uniform | - | - |

### Top Performing Securities
1. **FAB**: Consistent performer across configurations
2. **EMAAR**: Benefits from longer VWAP windows (60min)
3. **EMIRATES**: Strong with 30min VWAP window
4. **ADNOCGAS**: Prefers 60min VWAP window

### Underperforming Securities
- **EAND**: Negative P&L at most spreads, use wider spread (1.5%+) to avoid
- **ALDAR**: Sensitive to notional sizing, performs better with caps

---

## File Structure

```
tick-backtest-project/
├── configs/
│   ├── closing_strategy_config.json          # Main config (variable notional)
│   ├── closing_strategy_config_1m_cap.json   # 1M notional cap
│   ├── closing_strategy_config_2m_cap.json   # 2M notional cap
│   └── exchange_mapping.json                 # Security → Exchange mapping
├── data/
│   └── parquet/                              # Converted tick data
├── docs/
│   └── closing_strategy/
│       └── README.md                         # This documentation
├── output/
│   ├── closing_strategy/                     # Default output
│   ├── closing_strategy_1m_cap/              # 1M cap results
│   ├── closing_strategy_2m_cap/              # 2M cap results
│   ├── vwap_spread_sweep/                    # Spread sweep results
│   └── vwap_period_sweep/                    # Period sweep results
├── scripts/
│   ├── run_closing_strategy.py               # Main backtest runner
│   ├── sweep_vwap_spread.py                  # Parameter sweep script
│   └── plot_closing_strategy_trades.py       # Visualization generator
└── src/
    └── closing_strategy/
        ├── __init__.py
        ├── strategy.py                       # Core strategy logic
        └── handler.py                        # Backtest integration
```

---

## Quick Reference Commands

```bash
# Basic backtest
python scripts/run_closing_strategy.py

# With 1M notional cap
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_1m_cap.json

# Quick test (5 securities, no plots)
python scripts/run_closing_strategy.py --max-sheets 5 --no-plots

# Parameter sweep
python scripts/sweep_vwap_spread.py

# Generate plots only (after backtest)
python scripts/plot_closing_strategy_trades.py --output-dir output/closing_strategy
```
