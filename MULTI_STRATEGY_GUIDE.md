# Multi-Strategy Architecture

This project supports multiple market-making strategy variations with a clean, organized structure. Each strategy is self-contained with its own code, configuration, documentation, and results.

## Directory Structure

```
tick-backtest-project/
├── src/
│   └── strategies/
│       ├── base_strategy.py          # Abstract base class (all strategies inherit)
│       ├── v1_baseline/               # Original baseline strategy
│       │   ├── __init__.py
│       │   ├── strategy.py            # Strategy logic
│       │   └── handler.py             # Data processing handler
│       ├── v2_aggressive_refill/      # Future variation (example)
│       └── v3_inventory_skew/         # Future variation (example)
│
├── configs/
│   ├── mm_config.json                 # Original config (deprecated)
│   ├── v1_baseline_config.json        # V1 baseline parameters
│   ├── v2_aggressive_refill_config.json
│   └── v3_inventory_skew_config.json
│
├── docs/strategies/
│   ├── v1_baseline/
│   │   ├── TECHNICAL_DOCUMENTATION.md
│   │   ├── NON_TECHNICAL_EXPLANATION.md
│   │   └── README.md                  # V1-specific notes
│   ├── v2_aggressive_refill/
│   │   ├── TECHNICAL_DOCUMENTATION.md
│   │   ├── CHANGES_FROM_V1.md         # What changed
│   │   └── README.md
│   └── strategy_comparison.md         # Cross-strategy analysis
│
├── output/
│   ├── v1_baseline/                   # V1 results
│   │   ├── {security}_trades_timeseries.csv
│   │   └── backtest_summary.csv
│   ├── v2_aggressive_refill/          # V2 results
│   └── comparison/                    # Comparison outputs
│       ├── strategy_comparison.csv
│       └── strategy_comparison.png
│
└── scripts/
    ├── run_strategy.py                # Generic runner for any strategy
    └── compare_strategies.py          # Compare multiple strategies
```

## Quick Start

### Running a Strategy

Run any strategy by name:

```bash
# Run V1 baseline
python scripts/run_strategy.py --strategy v1_baseline

# Run with custom config
python scripts/run_strategy.py --strategy v1_baseline --config configs/v1_baseline_config.json

# Limit to first 5 securities for testing
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5
```

### Comparing Strategies

Compare multiple strategies:

```bash
# Compare two strategies
python scripts/compare_strategies.py v1_baseline v2_aggressive_refill

# Compare all strategies in output/
python scripts/compare_strategies.py --all

# Custom output location
python scripts/compare_strategies.py --all --output my_comparison.csv --plot my_plot.png
```

## Creating a New Strategy Variation

### Step 1: Create Strategy Directory

```bash
mkdir src/strategies/v2_my_variation
```

### Step 2: Implement Strategy Class

Create `src/strategies/v2_my_variation/strategy.py`:

```python
from strategies.base_strategy import BaseMarketMakingStrategy

class V2MyVariation(BaseMarketMakingStrategy):
    def generate_quotes(self, security, best_bid, best_ask):
        # Your custom quote logic here
        pass
    
    def should_refill_side(self, security, timestamp, side):
        # Your custom refill logic here
        pass
    
    def get_strategy_name(self):
        return "v2_my_variation"
    
    def get_strategy_description(self):
        return "Description of what makes this variation different"
```

### Step 3: Create Handler

Create `src/strategies/v2_my_variation/handler.py`:

```python
from strategies.v2_my_variation.strategy import V2MyVariation

def create_v2_handler(config=None):
    strategy = V2MyVariation(config=config)
    
    def v2_handler(security, df, orderbook, state):
        # Use same handler logic as v1_baseline
        # Or customize as needed
        pass
    
    return v2_handler
```

### Step 4: Create __init__.py

Create `src/strategies/v2_my_variation/__init__.py`:

```python
from .strategy import V2MyVariation
from .handler import create_v2_handler

__all__ = ['V2MyVariation', 'create_v2_handler']
```

### Step 5: Create Configuration

Copy and modify `configs/v1_baseline_config.json` to `configs/v2_my_variation_config.json`

### Step 6: Document Changes

Create `docs/strategies/v2_my_variation/CHANGES_FROM_V1.md`:

```markdown
# V2 My Variation - Changes from V1 Baseline

## Summary
Brief description of what changed and why.

## Code Changes

### Quote Generation
- Changed: ...
- Reason: ...

### Refill Logic
- Changed: ...
- Reason: ...

## Configuration Changes
- New parameter: ...
- Modified parameter: ...

## Expected Impact
- Performance: ...
- Risk: ...
```

### Step 7: Run and Compare

```bash
# Run your new strategy
python scripts/run_strategy.py --strategy v2_my_variation

# Compare against baseline
python scripts/compare_strategies.py v1_baseline v2_my_variation
```

## Base Strategy Class

All strategies inherit from `BaseMarketMakingStrategy` which provides:

### Required Methods (must implement)

- `generate_quotes(security, best_bid, best_ask)`: Determine quote prices and sizes
- `should_refill_side(security, timestamp, side)`: Decide when to update quotes

### Provided Methods (ready to use)

- `initialize_security(security)`: Set up tracking for new security
- `process_trade(...)`: Handle fills with queue simulation
- `flatten_position(...)`: EOD position closing
- `set_refill_time(...)`: Record quote placement time
- Time window checks: `is_in_opening_auction()`, `is_in_silent_period()`, etc.

### State Management

The base class manages:
- `self.position`: Current inventory per security
- `self.entry_price`: Average entry price per security
- `self.pnl`: Realized P&L per security
- `self.trades`: Trade history per security
- `self.last_refill_time`: Per-side quote timers
- `self.quote_prices`: Current quotes per security
- `self.active_orders`: Queue state per security

## Strategy Variations Ideas

### V2: Aggressive Refill
- Shorter refill interval (60s vs 180s)
- More frequent quote updates
- Trade more but capture less spread

### V3: Inventory Skew
- Skew quotes when position builds
- Quote wider on side that increases position
- Quote tighter on side that reduces position

### V4: Spread Requirements
- Only quote if spread >= minimum threshold
- Skip tight markets
- Better prices when filled

### V5: Dynamic Sizing
- Reduce quote size as inventory grows
- Inventory penalty factor (e.g., 50% at max position)
- More conservative risk management

### V6: Distance-Based Refill
- Refill if market moves away from quote
- Time-based OR distance-based trigger
- Adapt to market movement

## Configuration Parameters

Standard parameters for all strategies:

| Parameter | Type | Description |
|-----------|------|-------------|
| `quote_size` | int | Base quote size (shares) |
| `quote_size_bid` | int | Override bid size |
| `quote_size_ask` | int | Override ask size |
| `refill_interval_sec` | int | Quote refresh interval |
| `max_position` | int | Max inventory (shares) |
| `max_notional` | int | Max dollar exposure |
| `min_local_currency_before_quote` | int | Liquidity threshold |

Strategy-specific parameters can be added as needed.

## Git Workflow

### Recommended Branch Strategy

```bash
# Main branch: production-ready strategies
git checkout main

# Create branch for new strategy
git checkout -b strategy/v2-aggressive-refill

# Develop and test
# ... make changes ...

# Commit with clear messages
git add src/strategies/v2_aggressive_refill/
git commit -m "Add V2 aggressive refill strategy"

# Merge when validated
git checkout main
git merge strategy/v2-aggressive-refill
```

### Tag Stable Versions

```bash
# Tag a tested strategy version
git tag -a v1_baseline-stable -m "V1 baseline validated on full dataset"
git tag -a v2_aggressive_refill-v1.0 -m "First version of aggressive refill"

# Push tags
git push --tags
```

## Testing Strategies

### Quick Test (5 securities)

```bash
python scripts/run_strategy.py --strategy v2_my_variation --max-sheets 5
```

### Full Backtest

```bash
python scripts/run_strategy.py --strategy v2_my_variation
```

### Compare Results

```bash
python scripts/compare_strategies.py v1_baseline v2_my_variation
```

### Review Trade Details

```bash
# Check individual trade files
cat output/v2_my_variation/ADCB_trades_timeseries.csv
```

## Best Practices

1. **Always inherit from BaseMarketMakingStrategy**: Ensures consistent interface
2. **Document what changed**: Create CHANGES_FROM_V1.md for each variation
3. **Use descriptive names**: v2_aggressive_refill, not v2_test
4. **Keep v1_baseline stable**: Don't modify; create new variations instead
5. **Test incrementally**: Start with --max-sheets 5, then full run
6. **Compare systematically**: Always compare new strategy to v1_baseline
7. **Track in git**: Use branches for development, tags for validated versions
8. **Version configs**: Each strategy gets its own config file

## Troubleshooting

### Import Errors

```
ModuleNotFoundError: No module named 'strategies.v2_xxx'
```

**Solution**: Ensure `__init__.py` exists and handler function name matches pattern

### No Results Found

```
Warning: No results found for v2_xxx
```

**Solution**: Run the strategy first with `run_strategy.py`

### Handler Not Found

```
Error importing strategy 'v2_xxx': module has no attribute 'create_v2_handler'
```

**Solution**: Check handler function name in handler.py

## Support

- Technical docs: `docs/strategies/{strategy}/TECHNICAL_DOCUMENTATION.md`
- Non-technical explanation: `docs/strategies/{strategy}/NON_TECHNICAL_EXPLANATION.md`
- Base class reference: `src/strategies/base_strategy.py` (docstrings)
- Example implementation: `src/strategies/v1_baseline/`

## Future Enhancements

Potential additions to this architecture:

1. **Parameter optimization tools**: Grid search over config parameters
2. **Risk metrics**: Sharpe ratio, max drawdown, volatility
3. **Strategy templates**: Starter code for common variations
4. **Automated testing**: Unit tests for each strategy
5. **Live monitoring**: Real-time dashboard for running strategies
6. **Backtesting on different periods**: Train/test split validation
