"""
V2 Price Follow with Quantity Cooldown Strategy

This strategy continuously updates quote prices to follow the market,
but implements a cooldown period for quantity refills after executions.
"""

from datetime import datetime
from typing import Dict, Optional, Tuple
from ..base_strategy import BaseMarketMakingStrategy


class V2PriceFollowQtyCooldownStrategy(BaseMarketMakingStrategy):
    """
    Market-making strategy that follows market prices aggressively
    but limits quantity refills after fills.
    
    Key Behavior:
    - Quote prices ALWAYS update to current best bid/ask
    - After fills, enter cooldown period (cannot refill quantity)
    - During cooldown, can still quote remaining unfilled quantity
    - Cooldown duration is same regardless of fill size
    - When price updates, reset queue position
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        # Track last fill time for cooldown logic (replaces last_refill_time)
        self.last_fill_time: Dict[str, Dict[str, Optional[datetime]]] = {}
    
    def initialize_security(self, security: str):
        """Initialize state for a new security."""
        super().initialize_security(security)
        if security not in self.last_fill_time:
            self.last_fill_time[security] = {'bid': None, 'ask': None}
    
    def is_in_cooldown(self, security: str, timestamp: datetime, side: str) -> bool:
        """
        Check if side is in quantity refill cooldown period.
        
        Returns True if:
        - Last fill occurred < refill_interval_sec ago
        
        Returns False if:
        - No previous fills (first quote)
        - Cooldown period has expired
        """
        last_fill = self.last_fill_time.get(security, {}).get(side)
        
        if last_fill is None:
            return False  # No previous fill
        
        cfg = self.get_config(security)
        interval_sec = cfg['refill_interval_sec']
        elapsed = (timestamp - last_fill).total_seconds()
        
        return elapsed < interval_sec  # True if still in cooldown
    
    def get_quote_size(self, security: str, timestamp: datetime, side: str) -> int:
        """
        Determine quote size based on cooldown state and position limits.
        
        Logic:
        1. If NOT in cooldown: Use full quote size (from config)
        2. If IN cooldown: Use remaining unfilled quantity only
        3. Apply position limit constraints
        
        Returns:
            int: Quantity to quote (0 if no room or fully filled in cooldown)
        """
        cfg = self.get_config(security)
        current_pos = self.position[security]
        max_pos = cfg['max_position']
        
        # Determine base size
        if side == 'bid':
            base_size = cfg['quote_size_bid']
        else:
            base_size = cfg['quote_size_ask']
        
        # Check if in cooldown
        if self.is_in_cooldown(security, timestamp, side):
            # In cooldown: use remaining unfilled quantity
            ao = self.active_orders.get(security, {})
            side_order = ao.get(side, {})
            base_size = side_order.get('our_remaining', 0)
        
        # Apply position limits
        if side == 'bid':
            # Can't buy if at +max_position
            size = min(base_size, max_pos - current_pos)
        else:
            # Can't sell if at -max_position
            size = min(base_size, max_pos + current_pos)
        
        return max(0, int(size))
    
    def generate_quotes(self, security: str, best_bid: Optional[Tuple[float, float]], 
                       best_ask: Optional[Tuple[float, float]], 
                       timestamp: datetime) -> Optional[dict]:
        """
        Generate quote prices and sizes.
        
        Key Differences from v1_baseline:
        - Prices ALWAYS set to current best bid/ask (no stickiness)
        - Sizes determined by cooldown state and remaining quantities
        
        Args:
            security: Security symbol
            best_bid: (price, quantity) tuple for best bid
            best_ask: (price, quantity) tuple for best ask
            timestamp: Current timestamp (needed for cooldown check)
        
        Returns:
            dict with 'bid_price', 'ask_price', 'bid_size', 'ask_size'
            or None if no valid quotes
        """
        if not best_bid and not best_ask:
            return None
        
        cfg = self.get_config(security)
        
        # Handle max_notional if set
        max_pos = cfg['max_position']
        max_notional = cfg.get('max_notional')
        if max_notional and best_bid and best_ask:
            mid_price = (best_bid[0] + best_ask[0]) / 2
            max_pos = min(max_pos, int(max_notional / mid_price))
        
        # Get quote sizes based on cooldown state
        bid_size = self.get_quote_size(security, timestamp, 'bid') if best_bid else 0
        ask_size = self.get_quote_size(security, timestamp, 'ask') if best_ask else 0
        
        return {
            'bid_price': best_bid[0] if best_bid else None,
            'ask_price': best_ask[0] if best_ask else None,
            'bid_size': bid_size,
            'ask_size': ask_size
        }
    
    def _record_fill(self, security: str, side: str, price: float, 
                    qty: float, timestamp: datetime):
        """
        Record fill and start quantity refill cooldown.
        
        Key Addition:
        - Sets last_fill_time[security][side] to start cooldown timer
        - This prevents quantity refills until cooldown expires
        """
        # Call parent implementation for P&L accounting
        super()._record_fill(security, side, price, qty, timestamp)
        
        # Start cooldown timer for this side
        # Map 'buy'/'sell' to 'bid'/'ask' for cooldown tracking
        cooldown_side = 'bid' if side == 'buy' else 'ask'
        
        if security not in self.last_fill_time:
            self.last_fill_time[security] = {'bid': None, 'ask': None}
        
        self.last_fill_time[security][cooldown_side] = timestamp
    
    def process_trade(self, security: str, timestamp: datetime, 
                     trade_price: float, trade_qty: float, 
                     orderbook=None) -> bool:
        """
        Process market trade and check for fills.
        
        Same logic as base class, but uses last_fill_time for cooldown.
        
        Returns:
            bool: True if we got filled, False otherwise
        """
        return super().process_trade(security, timestamp, trade_price, trade_qty, orderbook)
    
    def should_refill_side(self, security: str, timestamp: datetime, side: str) -> bool:
        """
        Override base class method - not used in v2.
        
        v2 doesn't use refill timers for price updates.
        Quotes always update on market changes.
        
        Returns:
            bool: Always True (quotes always update)
        """
        return True
    
    def should_update_quotes(self, security: str, timestamp: datetime) -> bool:
        """
        In v2, quotes ALWAYS update on every market update (BID/ASK event).
        
        This is different from v1_baseline which uses refill intervals.
        
        Returns:
            bool: Always True (continuous updates)
        """
        return True
    
    def get_strategy_info(self) -> dict:
        """Return strategy identification and parameters."""
        return {
            'name': 'v2_price_follow_qty_cooldown',
            'version': '2.0',
            'description': 'Aggressive price updates with quantity refill cooldown',
            'characteristics': {
                'price_update': 'continuous',
                'quantity_refill': 'cooldown_after_fills',
                'queue_priority': 'reset_on_price_change',
                'cooldown_trigger': 'any_fill'
            }
        }
