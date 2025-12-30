"""
V3 Liquidity Monitor Strategy

Extends V2 price-following strategy with continuous orderbook depth monitoring.
Key addition: Removes quotes when liquidity at our price level falls below threshold.
"""

from datetime import datetime
from typing import Dict, Optional, Tuple
from ..v2_price_follow_qty_cooldown.strategy import V2PriceFollowQtyCooldownStrategy


class V3LiquidityMonitorStrategy(V2PriceFollowQtyCooldownStrategy):
    """
    Market-making strategy that follows market prices and continuously
    monitors orderbook depth at quoted prices.
    
    Key Behavior (inherits from V2):
    - Quote prices ALWAYS update to current best bid/ask
    - After fills, enter cooldown period (cannot refill quantity)
    - During cooldown, can still quote remaining unfilled quantity
    - When price updates, reset queue position
    
    NEW V3 Feature:
    - Continuously check liquidity at our quoted price level
    - Remove quote if depth falls below min_local_currency_before_quote
    - Restore quote when liquidity returns above threshold
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        # Track if quotes are currently active (not withdrawn due to liquidity)
        self.quotes_active: Dict[str, Dict[str, bool]] = {}
    
    def initialize_security(self, security: str):
        """Initialize state for a new security."""
        super().initialize_security(security)
        if security not in self.quotes_active:
            self.quotes_active[security] = {'bid': False, 'ask': False}
    
    def check_liquidity_at_price(self, orderbook, side: str, price: Optional[float]) -> Tuple[int, float]:
        """
        Check current liquidity at a specific price level.
        
        Args:
            orderbook: OrderBook instance
            side: 'bid' or 'ask'
            price: Price level to check
        
        Returns:
            Tuple of (quantity_at_level, local_currency_value)
        """
        if price is None:
            return 0, 0.0
        
        if side == 'bid':
            qty_at_level = orderbook.bids.get(price, 0)
        else:
            qty_at_level = orderbook.asks.get(price, 0)
        
        local_value = price * qty_at_level
        return int(qty_at_level), local_value
    
    def should_activate_quote(self, security: str, side: str, price: Optional[float], 
                             orderbook, timestamp: datetime) -> bool:
        """
        Determine if quote should be active based on current liquidity.
        
        Checks:
        1. Price is valid
        2. Not in opening/silent/closing periods
        3. Liquidity at price >= threshold
        
        Args:
            security: Security symbol
            side: 'bid' or 'ask'
            price: Quote price to check
            orderbook: Current orderbook state
            timestamp: Current time
        
        Returns:
            bool: True if quote should be active, False if should be withdrawn
        """
        if price is None:
            return False
        
        # Check time restrictions
        if self.is_in_opening_auction(timestamp):
            return False
        if self.is_in_silent_period(timestamp):
            return False
        if self.is_in_closing_auction(timestamp):
            return False
        
        # Check liquidity at our price
        cfg = self.get_config(security)
        threshold = cfg.get('min_local_currency_before_quote', 25000)
        
        qty_at_level, local_value = self.check_liquidity_at_price(orderbook, side, price)
        
        # Quote is valid if liquidity >= threshold
        return local_value >= threshold
    
    def get_strategy_info(self) -> dict:
        """Return strategy identification and parameters."""
        return {
            'name': 'v3_liquidity_monitor',
            'version': '3.0',
            'description': 'V2 strategy + continuous orderbook depth monitoring',
            'characteristics': {
                'price_update': 'continuous',
                'quantity_refill': 'cooldown_after_fills',
                'queue_priority': 'reset_on_price_change',
                'cooldown_trigger': 'any_fill',
                'liquidity_monitor': 'continuous_depth_check'
            }
        }
