# V2 Price-Follow Strategy - Technical Documentation

## Architecture

### Class Hierarchy

```
BaseMarketMakingStrategy (base_strategy.py)
    ↓ inherits
V2PriceFollowQtyCooldownStrategy (v2.../strategy.py)
```

### Module Structure

```
src/strategies/v2_price_follow_qty_cooldown/
├── __init__.py
│   └── exports: V2PriceFollowQtyCooldownStrategy, create_v2_handler
├── strategy.py
│   └── V2PriceFollowQtyCooldownStrategy class
└── handler.py
    └── create_v2_price_follow_qty_cooldown_handler()
```

## Strategy Implementation

### Key Differences from V1

| Aspect | V1 Baseline | V2 Price-Follow |
|--------|-------------|-----------------|
| Quote Generation | Quote at entry price | Quote at current best bid/ask |
| Refill Trigger | Fixed interval from placement | Interval from last fill |
| Price Tracking | Static | Dynamic |

### V2PriceFollowQtyCooldownStrategy Class

```python
class V2PriceFollowQtyCooldownStrategy(BaseMarketMakingStrategy):
    """
    Price-following market-making strategy with fill-based cooldown.
    
    Key behaviors:
    1. Quotes always placed at current best bid/ask
    2. Cooldown timer resets on fills (not on quote placement)
    3. Designed for short intervals (5-10 seconds)
    """
    
    def generate_quotes(self, security: str, best_bid: tuple, 
                       best_ask: tuple, timestamp: datetime) -> dict:
        """
        Generate quotes at current market prices.
        
        Unlike V1 which may quote at different prices, V2 always
        quotes at the current best bid/ask to stay competitive.
        """
        cfg = self.get_config(security)
        max_pos = cfg['max_position']
        current_pos = self.position.get(security, 0)
        
        # Position-aware sizing
        bid_size = min(cfg['quote_size_bid'], max_pos - current_pos)
        bid_size = max(0, bid_size)
        
        ask_size = min(cfg['quote_size_ask'], max_pos + current_pos)
        ask_size = max(0, ask_size)
        
        return {
            'bid_price': best_bid[0] if best_bid else None,
            'ask_price': best_ask[0] if best_ask else None,
            'bid_size': bid_size,
            'ask_size': ask_size
        }
    
    def should_refill_side(self, security: str, timestamp: datetime, 
                          side: str) -> bool:
        """
        Check if cooldown from last fill has expired.
        
        V2 uses fill-based cooldown: the timer starts when we get
        filled, not when we place the quote.
        """
        cfg = self.get_config(security)
        interval_sec = cfg['refill_interval_sec']
        
        last = self.last_refill_time.get(security, {}).get(side)
        if last is None:
            return True  # First time
        
        elapsed = (timestamp - last).total_seconds()
        return elapsed >= interval_sec
    
    def get_strategy_name(self) -> str:
        return "v2_price_follow_qty_cooldown"
```

### Handler Implementation

```python
def create_v2_price_follow_qty_cooldown_handler(config: dict):
    """Factory function to create V2 handler."""
    strategy = V2PriceFollowQtyCooldownStrategy(config=config)
    
    def v2_handler(security: str, df: pd.DataFrame, 
                   orderbook: OrderBook, state: dict) -> dict:
        """Process chunk of data for one security."""
        
        strategy.initialize_security(security)
        
        for row in df.itertuples(index=False):
            timestamp = row.timestamp
            event_type = str(row.type).lower()
            price = float(row.price)
            volume = int(row.volume) if hasattr(row, 'volume') else 0
            
            # Time window filters
            if strategy.is_in_opening_auction(timestamp):
                continue
            if strategy.is_in_closing_auction(timestamp):
                continue
            
            # Update orderbook
            if event_type == 'bid':
                orderbook.set_bid(price, volume)
            elif event_type == 'ask':
                orderbook.set_ask(price, volume)
            elif event_type == 'trade':
                orderbook.last_trade = {'price': price, 'volume': volume}
                # Process potential fills against our quotes
                strategy.process_trade(security, timestamp, price, volume, orderbook)
            
            # Quote generation with price-following
            best_bid = orderbook.get_best_bid()
            best_ask = orderbook.get_best_ask()
            
            for side in ['bid', 'ask']:
                if strategy.should_refill_side(security, timestamp, side):
                    quotes = strategy.generate_quotes(
                        security, best_bid, best_ask, timestamp
                    )
                    
                    # Get quote details for this side
                    if side == 'bid':
                        quote_price = quotes['bid_price']
                        quote_size = quotes['bid_size']
                        ahead_qty = orderbook.bids.get(quote_price, 0) if quote_price else 0
                    else:
                        quote_price = quotes['ask_price']
                        quote_size = quotes['ask_size']
                        ahead_qty = orderbook.asks.get(quote_price, 0) if quote_price else 0
                    
                    # Liquidity check
                    if quote_price and quote_size > 0:
                        liquidity = quote_price * ahead_qty
                        threshold = cfg.get('min_local_currency_before_quote', 25000)
                        
                        if liquidity >= threshold:
                            # Place quote
                            strategy.active_orders[security][side] = {
                                'price': quote_price,
                                'ahead_qty': int(ahead_qty),
                                'our_remaining': int(quote_size)
                            }
                            strategy.quote_prices[security][side] = quote_price
                            # Note: Timer set on FILL, not placement (V2 behavior)
            
            # EOD flatten
            if strategy.is_eod_close_time(timestamp):
                if strategy.position.get(security, 0) != 0:
                    strategy.flatten_position(security, price, timestamp)
        
        # Sync state
        state['position'] = strategy.position.get(security, 0)
        state['pnl'] = strategy.pnl.get(security, 0)
        state['trades'] = strategy.trades.get(security, [])
        
        return state
    
    return v2_handler
```

## Quote Update Flow

### V1 vs V2 Quote Timing

```
V1 BASELINE (Time-Based):
┌─────────────────────────────────────────────────────────┐
│ 10:00:00  Place quote @ 3.50                           │
│           │                                             │
│           └── 180s cooldown starts ──────────────────► │
│                                                         │
│ 10:00:30  Best bid moves to 3.52                       │
│           Quote stays at 3.50 (in cooldown)            │
│                                                         │
│ 10:01:00  Best bid moves to 3.55                       │
│           Quote stays at 3.50 (in cooldown)            │
│                                                         │
│ 10:03:00  Cooldown expires                             │
│           Place NEW quote @ 3.55 (current best)        │
└─────────────────────────────────────────────────────────┘

V2 PRICE-FOLLOW (Fill-Based):
┌─────────────────────────────────────────────────────────┐
│ 10:00:00  Place quote @ 3.50 (no cooldown yet)         │
│                                                         │
│ 10:00:05  Best bid = 3.52                              │
│           Update quote to 3.52 (no cooldown active)    │
│                                                         │
│ 10:00:10  Best bid = 3.55                              │
│           Update quote to 3.55 (still no cooldown)     │
│                                                         │
│ 10:00:15  FILL 30k @ 3.55                              │
│           │                                             │
│           └── 5s cooldown starts ───────────────────►  │
│                                                         │
│ 10:00:18  Best bid = 3.58                              │
│           No update (in cooldown)                       │
│                                                         │
│ 10:00:20  Cooldown expires                             │
│           Place NEW quote @ 3.58                        │
└─────────────────────────────────────────────────────────┘
```

### Why Fill-Based Cooldown?

1. **Maximizes Price Tracking**: Quotes follow market until a fill occurs
2. **Prevents Chasing**: After fill, brief pause to assess new position
3. **Optimal for Short Intervals**: 5s cooldown with aggressive price-following

## Trade Processing

### Fill Recording (Sets Cooldown)

```python
def _record_fill(self, security: str, side: str, price: float, 
                 qty: float, timestamp: datetime):
    """Record fill and reset cooldown timer."""
    
    # Standard P&L calculation (inherited from base)
    realized_pnl = self._calculate_pnl(security, side, price, qty)
    
    # Update position
    if side == 'buy':
        self._update_long_position(security, price, qty)
    else:
        self._update_short_position(security, price, qty)
    
    # Record trade
    self.trades[security].append({
        'timestamp': timestamp,
        'side': side,
        'fill_price': price,
        'fill_qty': qty,
        'realized_pnl': realized_pnl,
        'position': self.position[security],
        'pnl': self.pnl[security]
    })
    
    # === V2 KEY: Reset cooldown on fill ===
    self.set_refill_time(security, side, timestamp)
```

## Configuration

### Optimal Parameters

Based on extensive backtesting:

```json
{
  "DEFAULT": {
    "quote_size": 65000,
    "refill_interval_sec": 5,     // Short for price-following
    "max_position": 130000,
    "min_local_currency_before_quote": 13000
  }
}
```

### Parameter Sensitivity

| Interval | Trades | P&L | Sharpe | Notes |
|----------|--------|-----|--------|-------|
| 5s | 283,309 | 1,319,148 | 14.19 | **Optimal** |
| 10s | 277,212 | 1,273,433 | 13.92 | Good balance |
| 30s | 262,150 | 1,156,847 | 12.85 | Moderate |
| 60s | 243,892 | 1,042,563 | 11.73 | Conservative |
| 180s | 168,543 | 785,234 | 9.45 | Too slow for V2 |

## Performance Analysis

### Why V2 Trades More

```
V1 (180s interval):
  - ~1 quote update per 3 minutes
  - Quote often off-market
  - Lower fill probability

V2 (5s interval + price-following):
  - Quote always at best bid/ask
  - Higher fill probability
  - More round-trip trades
```

### Trade Frequency Comparison

```
V1 @ 180s: 106,826 trades over backtest period
           ~6,676 trades per security
           ~4.5 trades per security per day

V2 @ 5s:   283,309 trades over backtest period
           ~17,706 trades per security
           ~11.8 trades per security per day
```

## State Management

### Strategy State

```python
# From BaseMarketMakingStrategy
self.position: Dict[str, float]           # Current inventory
self.entry_price: Dict[str, float]        # Weighted average entry
self.pnl: Dict[str, float]                # Realized P&L
self.trades: Dict[str, list]              # Trade history
self.last_refill_time: Dict[str, Dict]    # Per-side cooldown timers
self.quote_prices: Dict[str, dict]        # Current quote prices
self.active_orders: Dict[str, dict]       # Queue simulation state
```

### State Synchronization

```python
# At end of handler
state['position'] = strategy.position.get(security, 0)
state['pnl'] = strategy.pnl.get(security, 0)
state['trades'] = strategy.trades.get(security, [])

# Handler returns state for framework to collect
return state
```

## Testing

### Unit Tests

```python
def test_price_following():
    """Test that quotes follow market price."""
    strategy = V2PriceFollowQtyCooldownStrategy({'TEST': {}})
    strategy.initialize_security('TEST')
    
    # Market at 3.50
    quotes1 = strategy.generate_quotes('TEST', (3.50, 1000), (3.52, 1000), now())
    assert quotes1['bid_price'] == 3.50
    
    # Market moves to 3.55
    quotes2 = strategy.generate_quotes('TEST', (3.55, 1000), (3.57, 1000), now())
    assert quotes2['bid_price'] == 3.55  # Should follow

def test_cooldown_on_fill():
    """Test cooldown starts on fill, not quote placement."""
    config = {'TEST': {'refill_interval_sec': 5}}
    strategy = V2PriceFollowQtyCooldownStrategy(config)
    strategy.initialize_security('TEST')
    
    t0 = datetime(2025, 1, 15, 10, 0, 0)
    
    # No cooldown yet
    assert strategy.should_refill_side('TEST', t0, 'bid') == True
    
    # Simulate fill (which sets cooldown)
    strategy.set_refill_time('TEST', 'bid', t0)
    
    # 3 seconds later - still in cooldown
    t1 = t0 + timedelta(seconds=3)
    assert strategy.should_refill_side('TEST', t1, 'bid') == False
    
    # 6 seconds later - cooldown expired
    t2 = t0 + timedelta(seconds=6)
    assert strategy.should_refill_side('TEST', t2, 'bid') == True
```

### Integration Test

```bash
# Quick validation
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown --max-sheets 3

# Full test
python scripts/run_parquet_backtest.py --strategy v2_price_follow_qty_cooldown
```

## Debugging

### Trace Quote Updates

```python
def v2_handler(security, df, orderbook, state):
    for row in df.itertuples():
        # ... processing ...
        
        for side in ['bid', 'ask']:
            if strategy.should_refill_side(security, timestamp, side):
                quotes = strategy.generate_quotes(...)
                
                print(f"[QUOTE] {security} {side}")
                print(f"  Time: {timestamp}")
                print(f"  Price: {quotes[f'{side}_price']}")
                print(f"  Size: {quotes[f'{side}_size']}")
```

### Monitor Fill-Based Cooldown

```python
def _record_fill(self, security, side, price, qty, timestamp):
    # ... existing code ...
    
    print(f"[FILL] {security} {side} {qty} @ {price}")
    print(f"  Cooldown started at: {timestamp}")
    print(f"  Cooldown expires at: {timestamp + timedelta(seconds=interval)}")
```

## Limitations

1. **No Stop-Loss**: V2 can hold losing positions indefinitely
   - Solution: Use V2.1 which adds 2% stop-loss

2. **Requires Active Markets**: Short intervals need continuous quotes
   - Solution: Increase interval for illiquid securities

3. **Higher Transaction Costs**: More trades = more commissions
   - Solution: Factor in costs when comparing to V1

## Related Documentation

- [V2.1 Stop-Loss](../v2_1_stop_loss/TECHNICAL_DOCUMENTATION.md) - V2 with stop-loss
- [Base Strategy](../../STRATEGY_TECHNICAL_DOCUMENTATION.md) - Parent class details
- [Fill/Refill Logic](../../FILL_REFILL_LOGIC_EXPLAINED.md) - Queue simulation
