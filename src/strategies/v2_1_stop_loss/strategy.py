"""
V2.1 Stop Loss Strategy

Extends V2 (Price Follow + Quantity Cooldown) with stop-loss mechanism:
- Monitors unrealized P&L on open positions
- Liquidates position when unrealized loss exceeds threshold (default 2%)
- Supports partial execution when insufficient liquidity
- Maintains all V2 functionality (aggressive price updates, cooldown after fills)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from ..v2_price_follow_qty_cooldown.strategy import V2PriceFollowQtyCooldownStrategy


class V21StopLossStrategy(V2PriceFollowQtyCooldownStrategy):
    """
    V2.1: V2 with stop-loss protection.
    
    Stop Loss Logic:
    - Calculates unrealized P&L as: (current_price - avg_entry_price) * position
    - Triggers when unrealized_loss / abs(position * avg_entry_price) > threshold
    - Liquidation:
        * Long position (positive): Sell at bid price
        * Short position (negative): Buy at ask price
    - Partial fills supported: tracks pending liquidation qty across updates
    
    Parameters (in config):
        stop_loss_threshold_pct: float, default 2.0 (2% loss triggers liquidation)
        + all V2 parameters
    """
    
    def __init__(self, config: Dict = None):
        """Initialize V2.1 strategy with stop-loss parameters."""
        super().__init__(config)
        
        # Stop-loss state tracking per security
        self.stop_loss_pending = {}  # {security: {'qty': int, 'side': str, 'triggered_at': datetime}}
        self.position_cost_basis = {}  # {security: float} - avg entry price * position qty
        self.position_qty_filled = {}  # {security: float} - total position qty for cost basis calc
    
    def initialize_security(self, security: str):
        """Initialize strategy state for a security."""
        super().initialize_security(security)
        
        if security not in self.stop_loss_pending:
            self.stop_loss_pending[security] = None
        
        if security not in self.position_cost_basis:
            self.position_cost_basis[security] = 0.0
            self.position_qty_filled[security] = 0
    
    def get_config(self, security: str) -> dict:
        """Get configuration for a security (includes stop-loss threshold)."""
        base_config = super().get_config(security)
        
        # Get stop-loss threshold from original config (not base_config which is filtered)
        cfg = self.config.get(security, {})
        base_config['stop_loss_threshold_pct'] = cfg.get('stop_loss_threshold_pct', 2.0)
        
        return base_config
    
    def _record_fill(self, security: str, side: str, price: float, qty: float, timestamp: datetime):
        """
        Record fill and update cost basis for stop-loss calculation.
        
        Cost basis tracking:
        - Track total cost (signed: positive for longs, negative for shorts)
        - When adding to same-direction position: add to cost
        - When reducing position: reduce cost proportionally  
        - When crossing zero: reset and start new position
        """
        old_position = self.position[security]
        
        # Call parent to update position, P&L, and cooldown
        super()._record_fill(security, side, price, qty, timestamp)
        
        new_position = self.position[security]
        
        # Determine if we're adding to position, reducing, or flipping
        old_sign = 1 if old_position > 0 else (-1 if old_position < 0 else 0)
        new_sign = 1 if new_position > 0 else (-1 if new_position < 0 else 0)
        
        if old_position == 0:
            # Opening new position
            self.position_cost_basis[security] = price * abs(new_position)
            self.position_qty_filled[security] = abs(new_position)
        elif new_position == 0:
            # Closed position completely
            self.position_cost_basis[security] = 0.0
            self.position_qty_filled[security] = 0
        elif old_sign == new_sign and abs(new_position) > abs(old_position):
            # Adding to existing position (same direction)
            qty_added = abs(new_position) - abs(old_position)
            self.position_cost_basis[security] += price * qty_added
            self.position_qty_filled[security] = abs(new_position)
        elif old_sign == new_sign and abs(new_position) < abs(old_position):
            # Reducing position (same direction, smaller size)
            reduction_ratio = abs(new_position) / abs(old_position)
            self.position_cost_basis[security] *= reduction_ratio
            self.position_qty_filled[security] = abs(new_position)
        else:
            # Position flipped direction - reset to new position
            self.position_cost_basis[security] = price * abs(new_position)
            self.position_qty_filled[security] = abs(new_position)
    
    def flatten_position(self, security: str, price: float, timestamp: datetime):
        """Override to reset cost basis when position flattened."""
        super().flatten_position(security, price, timestamp)
        
        # Reset cost basis after flatten
        self.position_cost_basis[security] = 0.0
        self.position_qty_filled[security] = 0
    
    def get_unrealized_pnl(self, security: str, current_price: float) -> float:
        """
        Calculate unrealized P&L on current position.
        
        Returns:
            float: Unrealized P&L in local currency
        """
        position = self.position[security]
        
        if position == 0 or self.position_qty_filled[security] == 0:
            return 0.0
        
        # Average entry price
        avg_entry_price = abs(self.position_cost_basis[security]) / self.position_qty_filled[security]
        
        # Unrealized P&L = (current - entry) * position
        # Positive position (long): profit if current > entry
        # Negative position (short): profit if current < entry
        unrealized_pnl = (current_price - avg_entry_price) * position
        
        return unrealized_pnl
    
    def get_unrealized_pnl_pct(self, security: str, current_price: float) -> float:
        """
        Calculate unrealized P&L as percentage of position value.
        
        Returns:
            float: Unrealized P&L percentage (positive = profit, negative = loss)
        """
        position = self.position[security]
        
        if position == 0 or abs(self.position_cost_basis[security]) < 1e-6:
            return 0.0
        
        unrealized_pnl = self.get_unrealized_pnl(security, current_price)
        
        # Calculate as % of cost basis (absolute value)
        pnl_pct = (unrealized_pnl / abs(self.position_cost_basis[security])) * 100.0
        
        return pnl_pct
    
    def should_trigger_stop_loss(self, security: str, current_price: float) -> bool:
        """
        Check if stop-loss should be triggered.
        
        Args:
            security: Security name
            current_price: Current market price for unrealized P&L calculation
        
        Returns:
            bool: True if stop-loss threshold exceeded (loss too large)
        """
        position = self.position[security]
        
        # No position = no stop loss
        if position == 0:
            return False
        
        # Already have pending stop loss
        if self.stop_loss_pending[security] is not None:
            return False
        
        # Get stop-loss threshold
        cfg = self.get_config(security)
        threshold_pct = cfg.get('stop_loss_threshold_pct', 2.0)
        
        # Calculate unrealized P&L %
        pnl_pct = self.get_unrealized_pnl_pct(security, current_price)
        
        # Trigger if LOSS exceeds threshold (pnl_pct is negative and magnitude > threshold)
        if pnl_pct < -threshold_pct:
            return True
        
        return False
    
    def trigger_stop_loss(self, security: str, timestamp: datetime):
        """
        Mark stop-loss as triggered for a security.
        
        Sets up pending liquidation that will be executed when liquidity available.
        """
        position = self.position[security]
        
        if position == 0:
            return
        
        # Determine liquidation side
        # Long position (positive) -> need to SELL
        # Short position (negative) -> need to BUY
        liquidation_side = 'sell' if position > 0 else 'buy'
        liquidation_qty = abs(position)
        
        self.stop_loss_pending[security] = {
            'qty': liquidation_qty,
            'side': liquidation_side,
            'triggered_at': timestamp,
            'remaining': liquidation_qty  # Track partial fills
        }
    
    def execute_stop_loss_liquidation(self, security: str, bid_price: float, ask_price: float,
                                     bid_size: float, ask_size: float, timestamp: datetime) -> bool:
        """
        Execute stop-loss liquidation (full or partial based on available liquidity).
        
        Args:
            security: Security name
            bid_price: Current best bid price
            ask_price: Current best ask price
            bid_size: Available liquidity at bid
            ask_size: Available liquidity at ask
            timestamp: Current timestamp
        
        Returns:
            bool: True if liquidation fully completed, False if partial/pending
        """
        if self.stop_loss_pending[security] is None:
            return True  # No pending liquidation
        
        pending = self.stop_loss_pending[security]
        side = pending['side']
        remaining_qty = pending['remaining']
        
        # Determine execution price and available liquidity
        if side == 'sell':
            # Liquidating long position -> sell at bid
            exec_price = bid_price
            available_qty = bid_size
        else:  # side == 'buy'
            # Liquidating short position -> buy at ask
            exec_price = ask_price
            available_qty = ask_size
        
        # Check if we have price and liquidity
        if exec_price is None or available_qty <= 0:
            return False  # Can't execute yet
        
        # Execute as much as possible
        fill_qty = min(remaining_qty, available_qty)
        
        # Record the fill
        self._record_fill(security, side, exec_price, fill_qty, timestamp)
        
        # Update remaining
        pending['remaining'] -= fill_qty
        
        # Check if fully liquidated
        if pending['remaining'] <= 0:
            self.stop_loss_pending[security] = None
            return True
        
        return False
    
    def get_strategy_info(self) -> dict:
        """Return strategy identification and parameters."""
        return {
            'name': 'v2_1_stop_loss',
            'version': '2.1',
            'description': 'V2 with stop-loss protection (liquidate at opposite price when loss > threshold)',
            'characteristics': {
                'price_update': 'continuous',
                'quantity_refill': 'cooldown_after_fills',
                'queue_priority': 'reset_on_price_change',
                'cooldown_trigger': 'any_fill',
                'stop_loss': 'enabled',
                'stop_loss_execution': 'partial_supported'
            }
        }
