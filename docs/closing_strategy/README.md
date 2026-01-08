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
| `trend_filter_sell_enabled` | bool | true | Enable SELL entry trend filter (skip sells in uptrends) |
| `trend_filter_sell_threshold_bps_hr` | float | 10.0 | SELL trend slope threshold in basis points per hour |
| `trend_filter_buy_enabled` | bool | false | Enable BUY entry trend filter (skip buys in downtrends) |
| `trend_filter_buy_threshold_bps_hr` | float | 10.0 | BUY trend slope threshold in basis points per hour |

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
| `--no-trend-filter-sell` | Disable SELL entry trend filter | False (filter enabled) |
| `--trend-threshold-sell` | SELL trend slope threshold (bps/hr) | 10.0 |
| `--trend-filter-buy` | Enable BUY entry trend filter | False (filter disabled) |
| `--trend-threshold-buy` | BUY trend slope threshold (bps/hr) | 10.0 |

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

## Trend Exclusion Filter

### Overview

Based on comprehensive statistical analysis of 1,447 closing strategy trades, a **trend exclusion filter** was implemented to improve entry performance. Each side (BUY/SELL) has independent enable flags and thresholds. The analysis revealed that SELL entries in uptrending markets significantly underperform.

### Analysis Findings

**Statistical Evidence (p=0.0017):**
- SELL entries in **uptrends** (>10 bps/hr slope): **65% win rate**
- SELL entries in **downtrends** (<10 bps/hr slope): **86% win rate**
- BUY entries show **no significant trend sensitivity** (filter disabled by default)

**Expected Impact:**
- Filters ~126 losing SELL trades
- Estimated savings: **~210,000 AED** in avoided losses
- Improved risk-adjusted returns

### How It Works

1. **Trend Data Collection**: During regular trading hours (10:00-14:45), the strategy collects (timestamp, price) pairs for each trade.

2. **Linear Regression**: At auction time, calculates the daily trend slope using simple OLS regression on (hours_since_10am, price).

3. **Filter Decision (Per-Side)**: 
   - If `slope > sell_threshold` AND `trend_filter_sell_enabled`: Skip SELL entry
   - If `slope < -buy_threshold` AND `trend_filter_buy_enabled`: Skip BUY entry

4. **Result**: Entries are only placed when market conditions are favorable for each side.

### Configuration

```json
{
  "ADNOCGAS": {
    "spread_vwap_pct": 0.5,
    "order_notional": 1000000,
    "trend_filter_sell_enabled": true,
    "trend_filter_sell_threshold_bps_hr": 10.0,
    "trend_filter_buy_enabled": false,
    "trend_filter_buy_threshold_bps_hr": 10.0
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `trend_filter_sell_enabled` | bool | true | Enable SELL entry trend filter |
| `trend_filter_sell_threshold_bps_hr` | float | 10.0 | SELL filter threshold (bps/hour) |
| `trend_filter_buy_enabled` | bool | false | Enable BUY entry trend filter |
| `trend_filter_buy_threshold_bps_hr` | float | 10.0 | BUY filter threshold (bps/hour) |

### CLI Usage

```bash
# Default: SELL filter enabled at 10 bps/hr, BUY filter disabled
python scripts/run_closing_strategy.py

# Disable SELL trend filter (compare baseline)
python scripts/run_closing_strategy.py --no-trend-filter-sell

# Enable BUY trend filter
python scripts/run_closing_strategy.py --trend-filter-buy

# Custom thresholds per side
python scripts/run_closing_strategy.py --trend-threshold-sell 15.0 --trend-threshold-buy 20.0

# Enable both filters
python scripts/run_closing_strategy.py --trend-filter-buy --trend-threshold-sell 10 --trend-threshold-buy 15

# Use 2M cap config with SELL filter only (default)
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_2m_cap.json

# Sweep trend threshold values
python scripts/sweep_vwap_spread.py --param trend_filter_sell_threshold_bps_hr --values 5 10 15 20
```

### Output Metrics

With trend filter enabled, the summary includes:

| Field | Description |
|-------|-------------|
| `buy_entries` | Number of BUY auction entries |
| `sell_entries` | Number of SELL auction entries (after filtering) |
| `filtered_sell_entries` | Number of SELL entries blocked by trend filter |
| `filtered_buy_entries` | Number of BUY entries blocked by trend filter |

### Technical Implementation

The trend calculation uses simple linear regression:

```python
def calculate_trend_slope(self, security):
    """Calculate trend slope in bps/hour using linear regression."""
    data = self.trend_data[security]
    if len(data) < 10:  # Need minimum data points
        return 0.0
    
    times, prices = zip(*data)
    hours = [(t - times[0]).total_seconds() / 3600 for t in times]
    
    # Simple OLS: slope = Σ((x-x̄)(y-ȳ)) / Σ((x-x̄)²)
    n = len(hours)
    mean_x = sum(hours) / n
    mean_y = sum(prices) / n
    
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(hours, prices))
    denominator = sum((x - mean_x) ** 2 for x in hours)
    
    slope = numerator / denominator if denominator > 0 else 0.0
    
    # Convert to bps/hour: (slope / mean_price) * 10000
    return (slope / mean_y) * 10000
```

### Best Practices

1. **Start with defaults**: The 10 bps/hr SELL threshold is based on rigorous statistical analysis.

2. **Run comparison tests**: Use `--no-trend-filter-sell` to compare performance with filter enabled vs disabled.

3. **Sweep threshold values**: Different securities may benefit from different thresholds:
   ```bash
   python scripts/sweep_vwap_spread.py --param trend_filter_sell_threshold_bps_hr --values 5 10 15 20
   ```

4. **Check filtered count**: High `filtered_sell_entries` count indicates the filter is actively protecting against uptrend sells.

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

Based on historical backtests (193 trading days, **with SELL trend filter enabled at 10 bps/hr**):

| Configuration | Total P&L | Trades | Sharpe | Filtered SELL |
|--------------|-----------|--------|--------|---------------|
| **250k (Baseline)** | 1,268,317 AED | 8,828 | ~5.5 | 624 |
| **1M Cap** | ~800,000 AED | ~8,500 | ~5.0 | ~620 |
| **2M Cap** | 1,103,485 AED | 8,519 | 5.48 | 624 |

### Latest Results (Jan 8, 2026) - 2M Cap with SELL Filter @ 10 bps/hr

```
Total P&L:            1,103,485 AED
Total Trades:         8,519
  Auction Entries:    534 (BUY: 303, SELL: 231)
  Filtered SELL:      624 (blocked due to uptrend)
  VWAP Exits:         7,835
  Stop-Losses:        48
  EOD Flattens:       102
Sharpe Ratio:         5.48
Win Rate:             ~70%
```

### Top Performing Securities (2M Cap)
| Security | P&L (AED) | Trades |
|----------|-----------|--------|
| 1. **FAB** | 297,433 | 773 |
| 2. **EMAAR** | 190,649 | 854 |
| 3. **EMIRATES** | 156,817 | 1,047 |
| 4. **MULTIPLY** | 107,015 | 258 |
| 5. **ADCB** | 82,143 | 612 |

### Underperforming Securities
- **EAND**: -27,492 AED (only negative performer)
- Consider wider spread (1.5%+) or exclusion for EAND

---

## File Structure

```
tick-backtest-project/
├── configs/
│   ├── closing_strategy_config.json          # Baseline config (250k notional)
│   ├── closing_strategy_config_250k.json     # Same as baseline (alias)
│   ├── closing_strategy_config_1m_cap.json   # 1M notional cap
│   ├── closing_strategy_config_2m_cap.json   # 2M notional cap (RECOMMENDED)
│   └── exchange_mapping.json                 # Security → Exchange mapping
├── data/
│   └── parquet/                              # Converted tick data (16 files)
├── docs/
│   └── closing_strategy/
│       └── README.md                         # This documentation
├── output/
│   ├── closing_strategy/                     # Default output
│   ├── closing_strategy_250k/                # 250k baseline results
│   ├── closing_strategy_1m_cap/              # 1M cap results
│   ├── closing_strategy_2m_cap/              # 2M cap results (CURRENT BEST)
│   │   ├── backtest_summary.csv              # Summary metrics
│   │   ├── {SECURITY}_trades.csv             # 16 trade logs
│   │   └── plots/
│   │       ├── performance_summary.png       # Aggregate 4-panel chart
│   │       └── {SECURITY}_trades.png         # 16 individual charts
│   └── vwap_spread_sweep/                    # Spread sweep results
├── scripts/
│   ├── run_closing_strategy.py               # Main backtest runner
│   ├── sweep_vwap_spread.py                  # Parameter sweep script
│   └── plot_closing_strategy_trades.py       # Visualization generator
└── src/
    └── closing_strategy/
        ├── __init__.py
        ├── strategy.py                       # Core strategy logic + trend filter
        └── handler.py                        # Backtest integration
```

### Config Files Comparison

| Config File | Order Notional | Use Case |
|-------------|----------------|----------|
| `closing_strategy_config.json` | 250k AED | Baseline/conservative |
| `closing_strategy_config_250k.json` | 250k AED | Same as baseline |
| `closing_strategy_config_1m_cap.json` | 1M AED | Medium position sizing |
| `closing_strategy_config_2m_cap.json` | 2M AED | **Recommended** - best P&L |

All configs include per-side trend filter settings:
- `trend_filter_sell_enabled`: true (default)
- `trend_filter_sell_threshold_bps_hr`: 10.0 (default)
- `trend_filter_buy_enabled`: false (default)
- `trend_filter_buy_threshold_bps_hr`: 10.0 (default)

---

## Quick Reference Commands

```bash
# Basic backtest (with SELL trend filter enabled by default)
python scripts/run_closing_strategy.py

# With different notional cap configs
python scripts/run_closing_strategy.py --config configs/closing_strategy_config.json           # 250k baseline
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_1m_cap.json    # 1M cap
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_2m_cap.json    # 2M cap

# Disable SELL trend filter (baseline comparison)
python scripts/run_closing_strategy.py --no-trend-filter-sell

# Enable BUY trend filter (disabled by default)
python scripts/run_closing_strategy.py --trend-filter-buy

# Custom thresholds per side
python scripts/run_closing_strategy.py --trend-threshold-sell 15.0 --trend-threshold-buy 20.0

# Both filters enabled with custom thresholds
python scripts/run_closing_strategy.py --trend-filter-buy --trend-threshold-sell 10 --trend-threshold-buy 15

# Quick test (5 securities, no plots)
python scripts/run_closing_strategy.py --max-sheets 5 --no-plots

# Parameter sweep (VWAP spread)
python scripts/sweep_vwap_spread.py

# Sweep trend threshold values
python scripts/sweep_vwap_spread.py --param trend_filter_sell_threshold_bps_hr --values 5 10 15 20

# Sweep with trend filter disabled
python scripts/sweep_vwap_spread.py --no-trend-filter-sell

# Generate plots only (after backtest)
python scripts/plot_closing_strategy_trades.py --trades-dir output/closing_strategy_2m_cap --output-dir output/closing_strategy_2m_cap/plots
```

---

## Output Files Summary

Each backtest run generates:

```
output/{run_name}/
├── backtest_summary.csv          # Per-security summary with P&L, trade counts
├── {SECURITY}_trades.csv         # 16 per-security trade logs
├── performance_summary.png       # 6-panel aggregate performance chart
└── plots/
    └── {SECURITY}_trades.png     # 16 per-security charts
```

### Performance Summary Plot (performance_summary.png)

A 6-panel visualization including:
1. **Portfolio Cumulative P&L Over Time** - Blue line with filled area (date x-axis)
2. **P&L by Security** - Bar chart (green=profit, red=loss)
3. **Performance Metrics Table** - Total P&L, Sharpe, Win Rate, Drawdown, etc.
4. **Per-Security Cumulative P&L** - Multi-line chart
5. **Global Configuration Parameters** - Table showing shared config settings
6. **Per-Security Notional Parameters** - Table showing order_notional per security

### Sweep Output Structure

Each sweep run generates:

```
output/{sweep_name}/
├── sweep_all_results.csv              # All results (security × parameter)
├── optimal_*_per_security.csv         # Best parameter per security
├── closing_strategy_config_optimal.json  # Generated optimal config
└── performance_summary.png            # 7-panel sweep summary
```

### Sweep Performance Summary Plot (performance_summary.png)

A 7-panel visualization including:
1. **Cumulative P&L Across Securities** - One curve per parameter value
2. **Total P&L by Parameter Value** - Bar chart
3. **Best P&L by Security** - Horizontal bar chart
4. **Total Trades by Parameter Value** - Bar chart
5. **P&L Heatmap** - Security × Parameter matrix
6. **Sweep Summary Statistics** - Table with best uniform/optimal params
7. **Optimal Parameter per Security** - Table with best param for each security

---

## Where to Start When Revisiting

### Quick Status Check
1. **Latest Config**: `configs/closing_strategy_config_2m_cap.json` (best balance of P&L and risk)
2. **Current Best Settings**: SELL trend filter @ 10 bps/hr, BUY filter disabled
3. **Latest Results**: `output/closing_strategy_2m_cap/` with ~1.1M AED P&L

### Key Files to Understand
1. [src/closing_strategy/strategy.py](../../src/closing_strategy/strategy.py) - Core strategy with trend filter
2. [scripts/run_closing_strategy.py](../../scripts/run_closing_strategy.py) - Main backtest runner
3. [configs/closing_strategy_config_2m_cap.json](../../configs/closing_strategy_config_2m_cap.json) - Current best config

### Run a Quick Test
```bash
# 5-security quick test with 2M cap
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_2m_cap.json --max-sheets 5

# Full backtest
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_2m_cap.json
```

### Things to Explore
1. **Different thresholds**: Try `--trend-threshold-sell 5` or `--trend-threshold-sell 15`
2. **BUY filter**: Enable with `--trend-filter-buy` (analysis showed no benefit, but worth testing)
3. **Per-security optimization**: Some securities may need different thresholds
4. **EAND exclusion**: Consider excluding EAND (only negative performer)
