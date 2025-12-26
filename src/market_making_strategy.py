"""Market-Making Strategy Handler for streaming backtest.

Implements a market maker that:
- Quotes at best bid/ask with configurable size
- Refills orders at configurable intervals
- Respects max position limits per security
- Skips opening auction (9:30-10:00) and closing auction (14:45-15:00)
- Flattens position at EOD close (14:55) at closing price
"""
from datetime import datetime, time
from typing import Dict, Optional
import pandas as pd


class MarketMakingStrategy:
    """Market-making strategy that quotes both sides."""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        config: dict with per-security configs
        {
            'SECURITY_NAME': {
                'quote_size': 50000,           # (optional) symmetric quote size
                'quote_size_bid': 50000,       # bid size override
                'quote_size_ask': 50000,       # ask size override
                'refill_interval_sec': 60,     # Refill quotes every N seconds
                'max_position': 2000000,       # Max position per security (shares)
                'max_notional': 100000,        # Optional currency cap; tighter than max_position at higher prices
            },
            ...
        }
        """
        self.config = config or {}
        
        # Per-security state
        self.position: Dict[str, float] = {}
        self.entry_price: Dict[str, float] = {}
        self.pnl: Dict[str, float] = {}
        self.trades: Dict[str, list] = {}
        # Per-security, per-side last refill timestamps
        self.last_refill_time: Dict[str, Dict[str, Optional[datetime]]] = {}
        self.quote_prices: Dict[str, dict] = {}  # {security: {'bid': price, 'ask': price}}
        # Active order tracking: per-security {'bid': {...}, 'ask': {...}}
        # Each side stores: price, our_size, ahead_qty (book ahead when we quoted), our_remaining
        self.active_orders: Dict[str, dict] = {}
    
    def get_config(self, security: str) -> dict:
        """Get config for security with defaults."""
        cfg = self.config.get(security, {})
        base_quote_size = cfg.get('quote_size', 50000)
        return {
            # Allow asymmetric quoting; fall back to symmetric size
            'quote_size_bid': cfg.get('quote_size_bid', base_quote_size),
            'quote_size_ask': cfg.get('quote_size_ask', base_quote_size),
            'refill_interval_sec': cfg.get('refill_interval_sec', 60),
            'max_position': cfg.get('max_position', 2000000),
            # Minimum local-currency (price * volume) present at the level before we quote
            'min_local_currency_before_quote': cfg.get('min_local_currency_before_quote', 25000),
            # Optional max notional (local currency) exposure cap; if set, overrides max_position
            'max_notional': cfg.get('max_notional'),
        }
    
    def initialize_security(self, security: str):
        """Initialize tracking for a new security."""
        if security not in self.position:
            self.position[security] = 0
            self.entry_price[security] = 0
            self.pnl[security] = 0.0
            self.trades[security] = []
            self.last_refill_time[security] = {'bid': None, 'ask': None}
            self.quote_prices[security] = {'bid': None, 'ask': None}
    
    def is_in_opening_auction(self, timestamp: datetime) -> bool:
        """Check if timestamp is during opening auction (9:30-10:00)."""
        try:
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            t = timestamp.time()
            return time(9, 30, 0) <= t < time(10, 0, 0)
        except Exception:
            return False
    
    def is_in_closing_auction(self, timestamp: datetime) -> bool:
        """Check if timestamp is during closing auction (14:45-15:00)."""
        try:
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            t = timestamp.time()
            return time(14, 45, 0) <= t <= time(15, 0, 0)
        except Exception:
            return False
    
    def is_in_silent_period(self, timestamp: datetime) -> bool:
        """Check if timestamp is during silent period (10:00-10:05)."""
        try:
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            t = timestamp.time()
            return time(10, 0, 0) <= t < time(10, 5, 0)
        except Exception:
            return False
    
    def is_eod_close_time(self, timestamp: datetime) -> bool:
        """Check if timestamp is at or after EOD close time (14:55)."""
        try:
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            t = timestamp.time()
            return t >= time(14, 55, 0)
        except Exception:
            return False
    
    def should_refill(self, security: str, timestamp: datetime) -> bool:
        """Check if either side needs refill (backward-compatible)."""
        return self.should_refill_side(security, timestamp, 'bid') or \
               self.should_refill_side(security, timestamp, 'ask')

    def should_refill_side(self, security: str, timestamp: datetime, side: str) -> bool:
        """Check if it's time to refill a given side ('bid' or 'ask').
        
        Refill logic:
        - After placing a quote (or trade), wait refill_interval before placing new quote
        - Refill time is set when quote passes liquidity check and is placed
        - This allows quotes to "stick" for the interval and have chance to get filled
        """
        cfg = self.get_config(security)
        interval_sec = cfg['refill_interval_sec']

        last = self.last_refill_time.get(security, {}).get(side)
        if last is None:
            return True

        try:
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)

            elapsed = (timestamp - last).total_seconds()
            # Only enforce interval if we had a trade on this side
            # Otherwise, always check (return True)
            # The refill_time gets set only after successful trades in process_trade
            return elapsed >= interval_sec
        except Exception:
            return True

    def set_refill_time(self, security: str, side: str, timestamp: datetime) -> None:
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        self.last_refill_time.setdefault(security, {'bid': None, 'ask': None})
        self.last_refill_time[security][side] = timestamp
    
    def generate_quotes(self, security: str, best_bid: Optional[tuple], best_ask: Optional[tuple]) -> Optional[dict]:
        """Generate quote prices and sizes based on current market.
        
        best_bid: (price, quantity) or None
        best_ask: (price, quantity) or None
        
        Returns: {'bid_price': float, 'ask_price': float, 'bid_size': float, 'ask_size': float}
        """
        # FIX: Allow quoting even if only one side is available
        # Previously returned None if both sides were None, blocking one-sided quotes
        if best_bid is None and best_ask is None:
            return None
        
        cfg = self.get_config(security)
        bid_quote_size = cfg['quote_size_bid']
        ask_quote_size = cfg['quote_size_ask']
        max_pos = cfg['max_position']
        max_notional = cfg.get('max_notional')
        
        bid_price, bid_qty = (best_bid if best_bid is not None else (None, 0))
        ask_price, ask_qty = (best_ask if best_ask is not None else (None, 0))

        # If max_notional is provided, derive a dynamic share cap based on mid price
        if max_notional is not None and (bid_price is not None or ask_price is not None):
            try:
                if bid_price is not None and ask_price is not None:
                    mid = (bid_price + ask_price) / 2
                else:
                    mid = bid_price if bid_price is not None else ask_price
                if mid > 0:
                    max_pos = min(max_pos, int(max_notional / mid))
            except Exception:
                pass
        
        # Determine how much we can quote based on position limits
        current_pos = self.position[security]
        
        # Max we can buy (go long): limited by distance to +max_pos
        bid_size = 0 if bid_price is None else min(bid_quote_size, int(max_pos - current_pos))
        bid_size = max(0, bid_size)
        
        # Max we can sell (go short): limited by distance to -max_pos
        ask_size = 0 if ask_price is None else min(ask_quote_size, int(max_pos + current_pos))
        ask_size = max(0, ask_size)
        
        return {
            'bid_price': bid_price,
            'ask_price': ask_price,
            'bid_size': bid_size,
            'ask_size': ask_size,
        }
    
    def process_trade(self, security: str, timestamp: datetime, trade_price: float, trade_qty: float, orderbook=None):
        """Simulate a trade fill if market trade hits our quotes.
        
        Simplified logic: if trade price is between our bid/ask, we fill proportionally.
        """
        if security not in self.quote_prices:
            return
        
        quotes = self.quote_prices[security]
        bid_price = quotes['bid']
        ask_price = quotes['ask']
        
        if bid_price is None and ask_price is None:
            return
        # Correct mapping:
        # - If market trade price >= our ask_price: our ASK was executed -> we SOLD
        # - If market trade price <= our bid_price: our BID was executed -> we BOUGHT
        cfg = self.get_config(security)

        # Access our active order snapshot
        ao = self.active_orders.get(security, None)
        if ao is None:
            return

        # Helper to reduce book level in orderbook if available
        def _reduce_book(side: str, price: float, qty: int):
            if orderbook is None:
                return
            try:
                if side == 'bid':
                    orderbook.remove_bid(price, qty)
                else:
                    orderbook.remove_ask(price, qty)
            except Exception:
                pass

        # ASK hit => our ASK was executed -> SELL from our ask order
        if ask_price is not None and trade_price >= ask_price:
            remaining = int(trade_qty)
            # consume ahead_qty first
            ask_side = ao.get('ask', {'ahead_qty': 0, 'our_remaining': 0})
            ahead = ask_side.get('ahead_qty', 0)
            consumed_ahead = min(ahead, remaining)
            ask_side['ahead_qty'] = ahead - consumed_ahead
            ao['ask'] = ask_side
            remaining -= consumed_ahead
            # reduce book level (best ask) accordingly
            if consumed_ahead > 0:
                _reduce_book('ask', ask_price, consumed_ahead)

            # now consume our remaining quantity
            our_rem = ask_side.get('our_remaining', 0)
            consumed_ours = 0
            if remaining > 0 and our_rem > 0:
                consumed_ours = min(our_rem, remaining)
                ask_side['our_remaining'] = our_rem - consumed_ours
                ao['ask'] = ask_side
                remaining -= consumed_ours
                # record sell fill for our consumed part
                if consumed_ours > 0:
                    self._record_fill(security, 'sell', trade_price, consumed_ours, timestamp)
                    # also reduce book by our consumed (simulate execution consuming liquidity)
                    _reduce_book('ask', ask_price, consumed_ours)

        # BID hit => our BID was executed -> BUY into our bid order
        if bid_price is not None and trade_price <= bid_price:
            remaining = int(trade_qty)
            bid_side = ao.get('bid', {'ahead_qty': 0, 'our_remaining': 0})
            ahead = bid_side.get('ahead_qty', 0)
            consumed_ahead = min(ahead, remaining)
            bid_side['ahead_qty'] = ahead - consumed_ahead
            ao['bid'] = bid_side
            remaining -= consumed_ahead
            if consumed_ahead > 0:
                _reduce_book('bid', bid_price, consumed_ahead)

            our_rem = bid_side.get('our_remaining', 0)
            consumed_ours = 0
            if remaining > 0 and our_rem > 0:
                consumed_ours = min(our_rem, remaining)
                bid_side['our_remaining'] = our_rem - consumed_ours
                ao['bid'] = bid_side
                remaining -= consumed_ours
                if consumed_ours > 0:
                    self._record_fill(security, 'buy', trade_price, consumed_ours, timestamp)
                    _reduce_book('bid', bid_price, consumed_ours)
    def _record_fill(self, security: str, side: str, price: float, qty: float, timestamp: datetime):
        """Record an executed fill and update position and realized P&L.

        This supports closing existing positions first (realized P&L), then
        opening or adding to positions with any remaining quantity.
        """
        realized_pnl = 0.0

        # Defensive defaults
        if qty <= 0:
            return

        # BUY: may close shorts first, then open/add longs
        if side == 'buy':
            # Close short position if present
            if self.position[security] < 0:
                close_qty = min(qty, abs(self.position[security]))
                realized_pnl += (self.entry_price[security] - price) * close_qty
                self.pnl[security] += realized_pnl
                self.position[security] += close_qty
                qty -= close_qty

            # Any remaining qty opens/extends a long
            if qty > 0:
                if self.position[security] == 0:
                    self.entry_price[security] = price
                    self.position[security] = qty
                else:
                    # Add to existing long: recompute weighted average entry price
                    total_cost = self.entry_price[security] * self.position[security] + price * qty
                    self.position[security] += qty
                    self.entry_price[security] = total_cost / self.position[security]

        # SELL: may close longs first, then open/add shorts
        elif side == 'sell':
            # Close long position if present
            if self.position[security] > 0:
                close_qty = min(qty, self.position[security])
                realized_pnl += (price - self.entry_price[security]) * close_qty
                self.pnl[security] += realized_pnl
                self.position[security] -= close_qty
                qty -= close_qty

            # Any remaining qty opens/extends a short
            if qty > 0:
                if self.position[security] == 0:
                    self.entry_price[security] = price
                    self.position[security] = -qty
                else:
                    # Add to existing short: compute weighted avg entry for shorts
                    existing_qty = abs(self.position[security])
                    total_cost = self.entry_price[security] * existing_qty + price * qty
                    new_qty = existing_qty + qty
                    self.entry_price[security] = total_cost / new_qty
                    self.position[security] -= qty

        # Record the fill
        self.trades[security].append({
            'timestamp': timestamp,
            'side': side,
            'fill_price': price,
            'fill_qty': qty if qty > 0 else 0,
            'realized_pnl': realized_pnl,
            'position': self.position[security],
            'pnl': self.pnl[security],
        })
        
        # After a fill, reset refill time to start new cooldown period
        # This prevents requoting immediately after being filled
        self.set_refill_time(security, side, timestamp)
 
    
    def flatten_position(self, security: str, close_price: float, timestamp: datetime):
        """Flatten entire position at given price."""
        if self.position[security] == 0:
            return
        
        if self.position[security] > 0:
            # Close long position
            self._record_fill(security, 'sell', close_price, self.position[security], timestamp)
        else:
            # Close short position
            self._record_fill(security, 'buy', close_price, abs(self.position[security]), timestamp)
    
    def get_total_pnl(self, security: str, mark_price: Optional[float] = None) -> float:
        """Get total P&L (realized + unrealized)."""
        realized = self.pnl[security]
        unrealized = 0.0
        
        if mark_price is not None and self.position[security] != 0:
            unrealized = (mark_price - self.entry_price[security]) * self.position[security]
        
        return realized + unrealized
