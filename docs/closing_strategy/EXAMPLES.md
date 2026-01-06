# Closing Strategy - Quick Start Examples

## Prerequisites

```bash
# Navigate to project directory
cd tick-backtest-project

# Activate virtual environment
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac

# One-time: Convert Excel data to Parquet (8-15x faster)
python scripts/convert_excel_to_parquet.py
```

---

## Basic Backtest Commands

### 1. Run Default Backtest
```bash
python scripts/run_closing_strategy.py
```
- Uses: `configs/closing_strategy_config.json`
- Output: `output/closing_strategy/`

### 2. Quick Test (5 Securities)
```bash
python scripts/run_closing_strategy.py --max-sheets 5 --no-plots
```

### 3. Run with 1M Notional Cap
```bash
python scripts/run_closing_strategy.py \
    --config configs/closing_strategy_config_1m_cap.json \
    --output-dir output/closing_strategy_1m_cap
```

### 4. Run with 2M Notional Cap
```bash
python scripts/run_closing_strategy.py \
    --config configs/closing_strategy_config_2m_cap.json \
    --output-dir output/closing_strategy_2m_cap
```

---

## Parameter Override Examples

### Override VWAP Spread
```bash
# Test with 0.75% spread
python scripts/run_closing_strategy.py --spread 0.75 --output-dir output/spread_075

# Test with 1.0% spread
python scripts/run_closing_strategy.py --spread 1.0 --output-dir output/spread_100
```

### Override VWAP Period
```bash
# 30-minute VWAP window
python scripts/run_closing_strategy.py --vwap-period 30 --output-dir output/vwap_30min

# 60-minute VWAP window
python scripts/run_closing_strategy.py --vwap-period 60 --output-dir output/vwap_60min
```

### Override Stop-Loss Threshold
```bash
# Tighter stop-loss (1.5%)
python scripts/run_closing_strategy.py --stop-loss 1.5 --output-dir output/sl_150

# Wider stop-loss (3.0%)
python scripts/run_closing_strategy.py --stop-loss 3.0 --output-dir output/sl_300
```

### Override Auction Fill Percentage
```bash
# Conservative (5% of auction volume)
python scripts/run_closing_strategy.py --auction-fill-pct 5 --output-dir output/fill_5pct

# Aggressive (15% of auction volume)
python scripts/run_closing_strategy.py --auction-fill-pct 15 --output-dir output/fill_15pct
```

### Combined Overrides
```bash
python scripts/run_closing_strategy.py \
    --config configs/closing_strategy_config_1m_cap.json \
    --spread 0.5 \
    --vwap-period 30 \
    --stop-loss 2.0 \
    --auction-fill-pct 10 \
    --output-dir output/custom_test
```

---

## Parameter Sweep Examples

### Sweep VWAP Spread
Edit `scripts/sweep_vwap_spread.py`:
```python
# Configuration section
param_name = 'spread_vwap_pct'
param_values = [0.5, 1.0, 1.5, 2.0]
config_path = Path("configs/closing_strategy_config_1m_cap.json")
output_dir = Path("output/vwap_spread_sweep")
```

Run:
```bash
python scripts/sweep_vwap_spread.py
```

Output files:
- `output/vwap_spread_sweep/sweep_all_results.csv`
- `output/vwap_spread_sweep/optimal_per_security.csv`
- `output/vwap_spread_sweep/closing_strategy_config_optimal.json`

### Sweep VWAP Pre-Close Period
Edit `scripts/sweep_vwap_spread.py`:
```python
# Configuration section
param_name = 'vwap_preclose_period_min'
param_values = [15, 30, 45, 60]
fixed_spread = 0.5  # Keep spread constant
config_path = Path("configs/closing_strategy_config_1m_cap.json")
output_dir = Path("output/vwap_period_sweep")
```

Run:
```bash
python scripts/sweep_vwap_spread.py
```

---

## Creating Custom Configurations

### Python Script to Create Capped Config
```python
import json

# Load original config
with open('configs/closing_strategy_config.json') as f:
    config = json.load(f)

# Cap all notionals at desired value (e.g., 1M AED)
cap = 1000000
for security in config:
    original = config[security]['order_notional']
    config[security]['order_notional'] = min(original, cap)
    if original > cap:
        print(f"{security}: {original:,} -> {cap:,} (capped)")
    else:
        print(f"{security}: {original:,} (unchanged)")

# Save new config
with open('configs/closing_strategy_config_1m_cap.json', 'w') as f:
    json.dump(config, f, indent=2)

print("\nSaved to: configs/closing_strategy_config_1m_cap.json")
```

### Python Script to Create Optimized Config
```python
import json
import pandas as pd

# Load sweep results
optimal = pd.read_csv('output/vwap_spread_sweep/optimal_per_security.csv')

# Load base config
with open('configs/closing_strategy_config_1m_cap.json') as f:
    config = json.load(f)

# Apply optimal spreads per security
for _, row in optimal.iterrows():
    security = row['security']
    if security in config:
        config[security]['spread_vwap_pct'] = row['optimal_value']
        print(f"{security}: spread = {row['optimal_value']}%")

# Save optimized config
with open('configs/closing_strategy_config_optimized.json', 'w') as f:
    json.dump(config, f, indent=2)

print("\nSaved to: configs/closing_strategy_config_optimized.json")
```

---

## Visualization Commands

### Generate Plots After Backtest
Plots are generated automatically unless `--no-plots` is specified.

### Regenerate Plots for Existing Results
```bash
python scripts/plot_closing_strategy_trades.py \
    --output-dir output/closing_strategy \
    --trades-dir output/closing_strategy
```

### Plot Specific Securities
```python
from scripts.plot_closing_strategy_trades import generate_all_plots

generate_all_plots(
    output_dir='output/closing_strategy/plots',
    trades_dir='output/closing_strategy',
    securities=['FAB', 'EMAAR', 'EMIRATES']  # Only these
)
```

---

## Output Analysis

### Load Trade Results in Python
```python
import pandas as pd

# Load all trades for a security
trades = pd.read_csv('output/closing_strategy/FAB_trades.csv')
print(trades.head())

# Calculate statistics
print(f"Total P&L: {trades['realized_pnl'].sum():,.2f} AED")
print(f"Total Trades: {len(trades)}")
print(f"Win Rate: {(trades['realized_pnl'] > 0).mean() * 100:.1f}%")

# Group by trade type
print(trades.groupby('trade_type')['realized_pnl'].agg(['count', 'sum', 'mean']))
```

### Load Summary Results
```python
import pandas as pd

summary = pd.read_csv('output/closing_strategy/backtest_summary.csv')
print(summary.sort_values('pnl', ascending=False))

# Top performers
print("\nTop 5 Performers:")
print(summary.nlargest(5, 'pnl')[['security', 'pnl', 'total_trades']])
```

### Compare Configurations
```python
import pandas as pd

# Load summaries from different runs
original = pd.read_csv('output/closing_strategy/backtest_summary.csv')
capped_1m = pd.read_csv('output/closing_strategy_1m_cap/backtest_summary.csv')
capped_2m = pd.read_csv('output/closing_strategy_2m_cap/backtest_summary.csv')

# Compare totals
print(f"Original:  {original['pnl'].sum():>12,.0f} AED")
print(f"1M Cap:    {capped_1m['pnl'].sum():>12,.0f} AED")
print(f"2M Cap:    {capped_2m['pnl'].sum():>12,.0f} AED")
```

---

## Common Workflows

### Workflow 1: Initial Exploration
```bash
# 1. Quick test to verify setup
python scripts/run_closing_strategy.py --max-sheets 3 --no-plots

# 2. Full backtest with default settings
python scripts/run_closing_strategy.py

# 3. Review results
cat output/closing_strategy/backtest_summary.csv
```

### Workflow 2: Parameter Optimization
```bash
# 1. Run spread sweep
python scripts/sweep_vwap_spread.py

# 2. Review optimal parameters
cat output/vwap_spread_sweep/optimal_per_security.csv

# 3. Run with optimized config
python scripts/run_closing_strategy.py \
    --config output/vwap_spread_sweep/closing_strategy_config_optimal.json \
    --output-dir output/optimized_run
```

### Workflow 3: Position Sizing Analysis
```bash
# 1. Run with different notional caps
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_1m_cap.json --output-dir output/cap_1m
python scripts/run_closing_strategy.py --config configs/closing_strategy_config_2m_cap.json --output-dir output/cap_2m

# 2. Compare results in Python
python -c "
import pandas as pd
cap1m = pd.read_csv('output/cap_1m/backtest_summary.csv')['pnl'].sum()
cap2m = pd.read_csv('output/cap_2m/backtest_summary.csv')['pnl'].sum()
print(f'1M Cap: {cap1m:,.0f} AED')
print(f'2M Cap: {cap2m:,.0f} AED')
"
```

---

## Troubleshooting

### "Parquet directory not found"
```bash
# Convert Excel data to Parquet first
python scripts/convert_excel_to_parquet.py
```

### "ModuleNotFoundError"
```bash
# Ensure virtual environment is activated
.venv\Scripts\activate

# Or run with explicit Python path
.venv\Scripts\python scripts/run_closing_strategy.py
```

### "Config file not found"
```bash
# Check config exists
ls configs/

# Use full path if needed
python scripts/run_closing_strategy.py --config "C:\full\path\to\config.json"
```

### Memory Issues with Large Data
```bash
# Process fewer securities
python scripts/run_closing_strategy.py --max-sheets 5

# Or reduce parallelism (edit script to use fewer workers)
```

---

## Reference: All CLI Arguments

```
python scripts/run_closing_strategy.py --help

Arguments:
  --config PATH           Config JSON file (default: configs/closing_strategy_config.json)
  --output-dir PATH       Output directory (default: output/closing_strategy)
  --max-sheets INT        Limit number of securities to process
  --spread FLOAT          Override spread_vwap_pct for all securities
  --vwap-period INT       Override vwap_preclose_period_min for all securities
  --stop-loss FLOAT       Override stop_loss_threshold_pct for all securities
  --auction-fill-pct FLOAT  Max fill as % of auction volume (default: 10.0)
  --no-plots              Disable automatic plot generation
```
