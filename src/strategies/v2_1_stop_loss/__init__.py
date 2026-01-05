"""
V2.1 Stop Loss Strategy

Extends V2 with stop-loss protection:
- Monitors unrealized P&L continuously
- Triggers stop-loss when loss exceeds threshold (default 2%)
- Liquidates at opposite price (long->bid, short->ask)
- Supports partial execution
"""

from .strategy import V21StopLossStrategy
from .handler import create_v2_1_stop_loss_handler

__all__ = ['V21StopLossStrategy', 'create_v2_1_stop_loss_handler']
