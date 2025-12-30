"""
v2_price_follow_qty_cooldown Strategy

Aggressive price updates with quantity refill cooldown.

Key Features:
- Prices continuously update to match best bid/ask (no sticky prices)
- After fills, quantity cannot be refilled for cooldown period
- During cooldown, quotes remaining unfilled quantity at updated prices
- When price updates, reset queue position (join back of queue)
"""

from .strategy import V2PriceFollowQtyCooldownStrategy
from .handler import create_v2_price_follow_qty_cooldown_handler

__all__ = [
    'V2PriceFollowQtyCooldownStrategy',
    'create_v2_price_follow_qty_cooldown_handler'
]
