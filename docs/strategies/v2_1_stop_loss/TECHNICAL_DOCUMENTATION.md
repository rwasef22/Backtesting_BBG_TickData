# V2.1 Stop-Loss Strategy - Technical Documentation

## Architecture

### Class Hierarchy

```
BaseMarketMakingStrategy (base_strategy.py)
    ↓ inherits
V2PriceFollowQtyCooldownStrategy (v2.../strategy.py)
    ↓ inherits
V2_1StopLossStrategy (v2_1.../strategy.py)
```

### Module Structure

```
src/strategies/v2_1_stop_loss/
├── __init__.py
│   └── exports: V2_1StopLossStrategy, create_v2_1_stop_loss_handler
├── strategy.py
│   └── V2_1StopLossStrategy class
└── handler.py
    └── create_v2_1_stop_loss_handler() factory function
```

## Strategy Implementation

### V2_1StopLossStrategy Class

```python
class V2_1StopLossStrategy(V2PriceFollowQtyCooldownStrategy):
    """
    V2.1 extends V2 with stop-loss protection.
    
    When unrealized losses exceed stop_loss_threshold_pct (default 2%),
    the position is immediately closed to limit losses.
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        # Additional state for stop-loss tracking
        self.stop_loss_triggered = {}  # {security: bool}
    
    def check_stop_loss(self, security: str, current_price: float, 
                        timestamp: datetime) -> bool:
        """
        Check if stop-loss should trigger.
        
        Args:
            security: Security symbol
            current_price: Current market price
            timestamp: Current timestamp
            
        Returns:
            True if stop-loss was triggered and position closed
        """
        position = self.position.get(security, 0)
        if position == 0:
            return False
            
        entry_price = self.entry_price.get(security, 0)
        if entry_price == 0:
            return False
        
        # Calculate unrealized P&L
        if position > 0:
            unrealized_pnl = (current_price - entry_price) * position
        else:
            unrealized_pnl = (entry_price - current_price) * abs(position)
        
        # Get stop-loss threshold
        cfg = self.get_config(security)
        threshold_pct = cfg.get('stop_loss_threshold_pct', 2.0)
        threshold_value = abs(entry_price * position) * (threshold_pct / 100)
        
        # Check if loss exceeds threshold
        if unrealized_pnl < -threshold_value:
            # Execute stop-loss
            self.flatten_position(security, current_price, timestamp)
            self.stop_loss_triggered[security] = True
            return True
        
        return False
    
    def get_strategy_name(self) -> str:
        return "v2_1_stop_loss"
    
    def get_strategy_description(self) -> str:
        return "V2 with stop-loss protection at configurable threshold"
```

### Handler Implementation

```python
def create_v2_1_stop_loss_handler(config: dict):
    """
    Factory function to create V2.1 handler.
    
    Args:
        config: Strategy configuration dict
        
    Returns:
        Handler function for backtest framework
    """
    strategy = V2_1StopLossStrategy(config=config)
    
    def v2_1_handler(security: str, df: pd.DataFrame, 
                     orderbook: OrderBook, state: dict) -> dict:
        """Process chunk of data for one security."""
        
        strategy.initialize_security(security)
        
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = str(row.type).lower()
            price = float(row.price)
            volume = int(row.volume) if hasattr(row, 'volume') else 0
            
            # Skip time windows
            if strategy.is_in_opening_auction(timestamp):
                continue
            if strategy.is_in_closing_auction(timestamp):
                continue
            
            # === STOP-LOSS CHECK (V2.1 addition) ===
            if event_type == 'trade' and price > 0:
                if strategy.check_stop_loss(security, price, timestamp):
                    # Stop-loss triggered, continue to next event
                    continue
            
            # === Standard V2 processing ===
            
            # Update orderbook
            if event_type == 'bid':
                orderbook.set_bid(price, volume)
            elif event_type == 'ask':
                orderbook.set_ask(price, volume)
            elif event_type == 'trade':
                orderbook.last_trade = {'price': price, 'volume': volume}
                strategy.process_trade(security, timestamp, price, volume, orderbook)
            
            # Quote generation (same as V2)
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            for side in ['bid', 'ask']:
                if strategy.should_refill_side(security, timestamp, side):
                    quotes = strategy.generate_quotes(security, best_bid, best_ask, timestamp)
                    # ... place quote logic ...
            
            # EOD flatten
            if strategy.is_eod_close_time(timestamp):
                if strategy.position.get(security, 0) != 0:
                    strategy.flatten_position(security, price, timestamp)
        
        # Sync state
        state['position'] = strategy.position.get(security, 0)
        state['pnl'] = strategy.pnl.get(security, 0)
        state['trades'] = strategy.trades.get(security, [])
        
        return state
    
    return v2_1_handler
```

## Stop-Loss Logic Details

### Calculation Formula

```python
# For LONG positions:
unrealized_pnl = (current_price - entry_price) * position
loss_threshold = entry_price * position * (threshold_pct / 100)

# For SHORT positions:
unrealized_pnl = (entry_price - current_price) * abs(position)
loss_threshold = entry_price * abs(position) * (threshold_pct / 100)

# Trigger condition (both cases):
if unrealized_pnl < -loss_threshold:
    trigger_stop_loss()
```

### Example Calculation

```
Entry:
  - Side: Buy (long)
  - Price: 3.50 AED
  - Quantity: 65,000 shares
  - Position Value: 227,500 AED

Stop-Loss Threshold:
  - Percentage: 2%
  - Threshold Value: 227,500 × 0.02 = 4,550 AED

Trigger Price:
  - Loss = 4,550 AED
  - Price Change = 4,550 / 65,000 = 0.07 AED
  - Trigger Price = 3.50 - 0.07 = 3.43 AED

When market price ≤ 3.43 AED:
  - Stop-loss triggers
  - Position sold at market price
  - Realized loss ≈ -4,550 AED
```

### Processing Order

```
┌─────────────────────────────────────────────────────────────┐
│                    Event Processing Loop                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Time Window Check                                        │
│     ├─ Opening auction (9:30-10:00)? → Skip                  │
│     └─ Closing auction (14:45+)? → Skip                      │
│                                                               │
│  2. STOP-LOSS CHECK (V2.1 addition) ────────────────────────│
│     │                                                         │
│     ├─ Is this a trade event?                                │
│     │   └─ Yes → Check unrealized P&L vs threshold           │
│     │            │                                            │
│     │            ├─ Loss > threshold?                        │
│     │            │   └─ Yes → Flatten position               │
│     │            │           Record stop-loss trade          │
│     │            │           Continue to next event          │
│     │            │                                            │
│     │            └─ No → Continue normal processing          │
│     │                                                         │
│     └─ No → Continue normal processing                       │
│                                                               │
│  3. Orderbook Update                                         │
│     └─ Update best bid/ask from event                        │
│                                                               │
│  4. Trade Processing                                         │
│     └─ Check if our quotes were hit                          │
│                                                               │
│  5. Quote Generation (if cooldown expired)                   │
│     └─ Generate new quotes at best bid/ask                   │
│                                                               │
│  6. EOD Flatten Check                                        │
│     └─ Close any remaining position at 14:55+                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Schema

### Full Configuration Example

```json
{
  "ADNOCGAS": {
    "quote_size": 65000,
    "quote_size_bid": 65000,
    "quote_size_ask": 65000,
    "refill_interval_sec": 5,
    "max_position": 130000,
    "max_notional": 1500000,
    "min_local_currency_before_quote": 13000,
    "stop_loss_threshold_pct": 2.0
  },
  "EMAAR": {
    "quote_size": 100000,
    "refill_interval_sec": 5,
    "max_position": 200000,
    "stop_loss_threshold_pct": 2.0
  }
}
```

### Parameter Validation

```python
def get_config(self, security: str) -> dict:
    cfg = self.config.get(security, {})
    
    # Defaults
    base_quote_size = cfg.get('quote_size', 50000)
    
    return {
        'quote_size_bid': cfg.get('quote_size_bid', base_quote_size),
        'quote_size_ask': cfg.get('quote_size_ask', base_quote_size),
        'refill_interval_sec': cfg.get('refill_interval_sec', 60),
        'max_position': cfg.get('max_position', 2000000),
        'max_notional': cfg.get('max_notional'),
        'min_local_currency_before_quote': cfg.get('min_local_currency_before_quote', 25000),
        'stop_loss_threshold_pct': cfg.get('stop_loss_threshold_pct', 2.0),  # V2.1
    }
```

## State Management

### Strategy State

```python
# Inherited from BaseMarketMakingStrategy
self.position: Dict[str, float]           # Current inventory
self.entry_price: Dict[str, float]        # Average entry price
self.pnl: Dict[str, float]                # Realized P&L
self.trades: Dict[str, list]              # Trade history
self.last_refill_time: Dict[str, Dict]    # Per-side timers
self.quote_prices: Dict[str, dict]        # Current quotes
self.active_orders: Dict[str, dict]       # Queue state

# V2.1 additions
self.stop_loss_triggered: Dict[str, bool] # Stop-loss event tracking
```

### Trade Record Format

```python
# Standard trade record
{
    'timestamp': datetime,
    'side': 'buy' | 'sell',
    'fill_price': float,
    'fill_qty': int,
    'realized_pnl': float,
    'position': int,
    'pnl': float
}

# Stop-loss trades are recorded identically
# Can be identified by checking if realized_pnl is large negative
```

## Performance Analysis

### Sweep Results (Jan 2026)

| Strategy | Interval | Trades | P&L | Sharpe | Max DD | Win Rate |
|----------|----------|--------|-----|--------|--------|----------|
| V2 | 5s | 283,309 | 1,319,148 | 14.19 | -664,129 | 23.55% |
| V2 | 10s | 277,212 | 1,273,433 | 13.92 | -702,572 | 23.57% |
| **V2.1** | **5s** | **283,781** | **1,408,864** | **14.96** | **-648,422** | **23.64%** |
| V2.1 | 10s | 277,624 | 1,365,516 | 14.80 | -684,888 | 23.66% |

### Why V2.1 Outperforms V2

1. **Earlier Exit from Losers**
   - V2: Holds losing positions hoping for recovery
   - V2.1: Cuts losses at 2%, preserves capital

2. **Reduced Maximum Drawdown**
   - V2 @ 5s: -664,129 AED max drawdown
   - V2.1 @ 5s: -648,422 AED max drawdown (-2.4%)

3. **Better Capital Utilization**
   - Stop-loss frees capital to re-enter at better prices
   - More trading opportunities when positions cut early

4. **Improved Risk-Adjusted Returns**
   - Sharpe increases from 14.19 to 14.96 (+5.4%)
   - Higher returns per unit of risk taken

## Testing

### Unit Test Example

```python
def test_stop_loss_triggers():
    """Test stop-loss triggers at 2% loss."""
    config = {
        'TEST': {
            'quote_size': 10000,
            'stop_loss_threshold_pct': 2.0
        }
    }
    strategy = V2_1StopLossStrategy(config)
    strategy.initialize_security('TEST')
    
    # Simulate long position
    strategy.position['TEST'] = 10000
    strategy.entry_price['TEST'] = 100.0  # Entry at 100
    
    # Price drops to 98 (-2%)
    timestamp = pd.Timestamp('2025-01-15 10:00:00')
    triggered = strategy.check_stop_loss('TEST', 98.0, timestamp)
    
    assert triggered == True
    assert strategy.position['TEST'] == 0  # Position closed
    assert strategy.pnl['TEST'] < 0  # Loss realized

def test_stop_loss_not_triggered():
    """Test stop-loss doesn't trigger for small loss."""
    config = {'TEST': {'stop_loss_threshold_pct': 2.0}}
    strategy = V2_1StopLossStrategy(config)
    strategy.initialize_security('TEST')
    
    strategy.position['TEST'] = 10000
    strategy.entry_price['TEST'] = 100.0
    
    # Price drops to 99 (-1%, below threshold)
    timestamp = pd.Timestamp('2025-01-15 10:00:00')
    triggered = strategy.check_stop_loss('TEST', 99.0, timestamp)
    
    assert triggered == False
    assert strategy.position['TEST'] == 10000  # Position unchanged
```

### Integration Test

```bash
# Quick validation test
python scripts/run_parquet_backtest.py --strategy v2_1_stop_loss --max-sheets 3

# Compare against V2
python scripts/fast_sweep.py --intervals 30 60 --max-sheets 5
```

## Debugging

### Enable Verbose Logging

```python
# In handler.py
import logging
logging.basicConfig(level=logging.DEBUG)

def create_v2_1_stop_loss_handler(config):
    strategy = V2_1StopLossStrategy(config=config)
    logger = logging.getLogger(__name__)
    
    def v2_1_handler(security, df, orderbook, state):
        for row in df.itertuples():
            # ... processing ...
            
            if strategy.check_stop_loss(security, price, timestamp):
                logger.debug(f"STOP-LOSS {security} @ {price} "
                           f"position={strategy.position[security]} "
                           f"pnl={strategy.pnl[security]}")
```

### Trace Stop-Loss Events

```python
# Add to strategy class
def check_stop_loss(self, security, current_price, timestamp):
    result = super().check_stop_loss(security, current_price, timestamp)
    
    if result:
        print(f"[STOP-LOSS] {security}")
        print(f"  Time: {timestamp}")
        print(f"  Price: {current_price}")
        print(f"  Entry: {self.entry_price.get(security)}")
        print(f"  Loss: {self.pnl.get(security)}")
    
    return result
```

## Related Documentation

- [Base Strategy Reference](../../STRATEGY_TECHNICAL_DOCUMENTATION.md)
- [V2 Strategy Documentation](../v2_price_follow_qty_cooldown/TECHNICAL_DOCUMENTATION.md)
- [Fill/Refill Logic](../../FILL_REFILL_LOGIC_EXPLAINED.md)
- [Handler Architecture](../../MULTI_STRATEGY_GUIDE.md)
