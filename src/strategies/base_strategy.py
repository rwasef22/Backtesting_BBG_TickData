"""Base abstract class for market-making strategies.

This module provides the foundational abstract base class that all
market-making strategy variations must inherit from. It defines the
interface and common functionality that all strategies share.
"""
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Dict, Optional, Tuple
import pandas as pd


class BaseMarketMakingStrategy(ABC):
    """Abstract base class for all market-making strategies.
    
    This class defines the common interface and shared functionality
    that all strategy variations must implement. Each concrete strategy
    should inherit from this class and implement the abstract methods.
    
    Attributes:
        config: Per-security configuration dictionary
        position: Current inventory position per security
        entry_price: Weighted average entry price per security
        pnl: Realized profit and loss per security
        trades: List of executed trades per security
        last_refill_time: Per-side last quote time per security
        quote_prices: Current quoted prices per security
        active_orders: Active order state per security
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the strategy with configuration.
        
        Args:
            config: Dictionary mapping security names to their parameters.
                   Each security config should contain:
                   - quote_size: Base quote size (shares)
                   - quote_size_bid/ask: Override for specific sides
                   - refill_interval_sec: Quote refresh interval
                   - max_position: Maximum inventory limit
                   - max_notional: Optional dollar cap
                   - min_local_currency_before_quote: Liquidity threshold
        """
        self.config = config or {}
        
        # Per-security state dictionaries
        self.position: Dict[str, float] = {}
        self.entry_price: Dict[str, float] = {}
        self.pnl: Dict[str, float] = {}
        self.trades: Dict[str, list] = {}
        self.last_refill_time: Dict[str, Dict[str, Optional[datetime]]] = {}
        self.quote_prices: Dict[str, dict] = {}
        self.active_orders: Dict[str, dict] = {}
    
    def get_config(self, security: str) -> dict:
        """Get configuration for security with defaults.
        
        Args:
            security: Security identifier
            
        Returns:
            Dictionary with all configuration parameters filled in
        """
        cfg = self.config.get(security, {})
        base_quote_size = cfg.get('quote_size', 50000)
        return {
            'quote_size_bid': cfg.get('quote_size_bid', base_quote_size),
            'quote_size_ask': cfg.get('quote_size_ask', base_quote_size),
            'refill_interval_sec': cfg.get('refill_interval_sec', 60),
            'max_position': cfg.get('max_position', 2000000),
            'min_local_currency_before_quote': cfg.get('min_local_currency_before_quote', 25000),
            'max_notional': cfg.get('max_notional'),
        }
    
    def initialize_security(self, security: str):
        """Initialize state for a new security.
        
        Args:
            security: Security identifier
        """
        if security not in self.position:
            self.position[security] = 0
            self.entry_price[security] = 0
            self.pnl[security] = 0.0
            self.trades[security] = []
            self.last_refill_time[security] = {'bid': None, 'ask': None}
            self.quote_prices[security] = {'bid': None, 'ask': None}
            self.active_orders[security] = {'bid': {}, 'ask': {}}
    
    # ==================== Abstract Methods ====================
    # These must be implemented by each concrete strategy
    
    @abstractmethod
    def generate_quotes(self, security: str, best_bid: Optional[Tuple[float, float]], 
                       best_ask: Optional[Tuple[float, float]]) -> dict:
        """Generate quote prices and sizes based on market state.
        
        This is a core method that defines how the strategy determines
        what prices and sizes to quote. Each variation can implement
        different logic here (e.g., skewing, spread requirements, etc.)
        
        Args:
            security: Security identifier
            best_bid: (price, quantity) of current best bid or None
            best_ask: (price, quantity) of current best ask or None
            
        Returns:
            Dictionary with keys:
            - bid_price: Price to quote on bid side (or None)
            - ask_price: Price to quote on ask side (or None)
            - bid_size: Quantity to bid (shares)
            - ask_size: Quantity to ask (shares)
        """
        pass
    
    @abstractmethod
    def should_refill_side(self, security: str, timestamp: datetime, side: str) -> bool:
        """Determine if it's time to update quotes on given side.
        
        Different strategies may have different refill logic:
        - Time-based (standard)
        - Distance-based (market moved away)
        - Volatility-based (wider spreads in volatile markets)
        - Inventory-based (more aggressive when skewed)
        
        Args:
            security: Security identifier
            timestamp: Current time
            side: 'bid' or 'ask'
            
        Returns:
            True if should place new quote, False otherwise
        """
        pass
    
    # ==================== Common Utility Methods ====================
    # These provide standard functionality used by all strategies
    
    def set_refill_time(self, security: str, side: str, timestamp: datetime):
        """Record when a quote was placed on given side.
        
        Args:
            security: Security identifier
            side: 'bid' or 'ask'
            timestamp: Time quote was placed
        """
        if security not in self.last_refill_time:
            self.last_refill_time[security] = {'bid': None, 'ask': None}
        self.last_refill_time[security][side] = timestamp
    
    def is_in_opening_auction(self, timestamp: datetime) -> bool:
        """Check if timestamp is during opening auction (9:30-10:00).
        
        Args:
            timestamp: Time to check
            
        Returns:
            True if in opening auction period
        """
        t = timestamp.time()
        return time(9, 30, 0) <= t < time(10, 0, 0)
    
    def is_in_silent_period(self, timestamp: datetime) -> bool:
        """Check if timestamp is during silent period (10:00-10:05).
        
        Args:
            timestamp: Time to check
            
        Returns:
            True if in silent period
        """
        t = timestamp.time()
        return time(10, 0, 0) <= t < time(10, 5, 0)
    
    def is_in_closing_auction(self, timestamp: datetime) -> bool:
        """Check if timestamp is during closing auction (14:45-15:00).
        
        Args:
            timestamp: Time to check
            
        Returns:
            True if in closing auction period
        """
        t = timestamp.time()
        return time(14, 45, 0) <= t <= time(15, 0, 0)
    
    def is_eod_close_time(self, timestamp: datetime) -> bool:
        """Check if timestamp is at/after EOD close time (14:55).
        
        Args:
            timestamp: Time to check
            
        Returns:
            True if should close positions
        """
        t = timestamp.time()
        return t >= time(14, 55, 0)
    
    def process_trade(self, security: str, timestamp: datetime, 
                     trade_price: float, trade_qty: float, orderbook=None):
        """Process market trade and check for fills using queue simulation.
        
        This method implements realistic fill logic by simulating FIFO queue
        execution. It checks if the trade price crosses our quotes and
        calculates partial fills based on queue position.
        
        Args:
            security: Security identifier
            timestamp: Trade time
            trade_price: Execution price
            trade_qty: Trade quantity
            orderbook: OrderBook instance (optional, for future use)
        """
        quotes = self.quote_prices.get(security, {})
        ask_price = quotes.get('ask')
        bid_price = quotes.get('bid')
        
        ao = self.active_orders.get(security, {})
        
        # Check ASK side: trade at/above our ask means we sold
        if ask_price is not None and trade_price >= ask_price:
            remaining = int(trade_qty)
            ask_side = ao.get('ask', {'ahead_qty': 0, 'our_remaining': 0})
            
            # Consume ahead quantity first (FIFO simulation)
            ahead = ask_side.get('ahead_qty', 0)
            consumed_ahead = min(ahead, remaining)
            ask_side['ahead_qty'] = ahead - consumed_ahead
            remaining -= consumed_ahead
            
            # Then consume our order
            our_rem = ask_side.get('our_remaining', 0)
            if remaining > 0 and our_rem > 0:
                consumed_ours = min(our_rem, remaining)
                ask_side['our_remaining'] = our_rem - consumed_ours
                
                # Record the fill
                self._record_fill(security, 'sell', trade_price, consumed_ours, timestamp)
                
                # If fully filled, clear the quote
                if ask_side['our_remaining'] == 0:
                    self.quote_prices[security]['ask'] = None
        
        # Check BID side: trade at/below our bid means we bought
        if bid_price is not None and trade_price <= bid_price:
            remaining = int(trade_qty)
            bid_side = ao.get('bid', {'ahead_qty': 0, 'our_remaining': 0})
            
            # Consume ahead quantity first
            ahead = bid_side.get('ahead_qty', 0)
            consumed_ahead = min(ahead, remaining)
            bid_side['ahead_qty'] = ahead - consumed_ahead
            remaining -= consumed_ahead
            
            # Then consume our order
            our_rem = bid_side.get('our_remaining', 0)
            if remaining > 0 and our_rem > 0:
                consumed_ours = min(our_rem, remaining)
                bid_side['our_remaining'] = our_rem - consumed_ours
                
                # Record the fill
                self._record_fill(security, 'buy', trade_price, consumed_ours, timestamp)
                
                # If fully filled, clear the quote
                if bid_side['our_remaining'] == 0:
                    self.quote_prices[security]['bid'] = None
    
    def _record_fill(self, security: str, side: str, price: float, qty: float, timestamp: datetime):
        """Record an executed fill with P&L calculation.
        
        This method handles position accounting with proper P&L tracking:
        - Closes opposite positions first (realizes P&L)
        - Opens/extends same-direction positions
        - Updates entry price using weighted average
        - Resets refill timer to start new cooldown
        
        Args:
            security: Security identifier
            side: 'buy' or 'sell'
            price: Fill price
            qty: Fill quantity
            timestamp: Fill time
        """
        # Don't record fills with zero quantity
        if qty == 0:
            return
        
        original_qty = qty  # Save original qty for trade record
        realized_pnl = 0.0
        
        if side == 'buy':
            # Close shorts first
            if self.position[security] < 0:
                close_qty = min(qty, abs(self.position[security]))
                realized_pnl += (self.entry_price[security] - price) * close_qty
                self.pnl[security] += realized_pnl
                self.position[security] += close_qty
                qty -= close_qty
            
            # Open/extend longs with remainder
            if qty > 0:
                if self.position[security] == 0:
                    self.entry_price[security] = price
                    self.position[security] = qty
                else:
                    # Weighted average entry
                    total_cost = self.entry_price[security] * self.position[security] + price * qty
                    self.position[security] += qty
                    self.entry_price[security] = total_cost / self.position[security]
        
        elif side == 'sell':
            # Close longs first
            if self.position[security] > 0:
                close_qty = min(qty, self.position[security])
                realized_pnl += (price - self.entry_price[security]) * close_qty
                self.pnl[security] += realized_pnl
                self.position[security] -= close_qty
                qty -= close_qty
            
            # Open/extend shorts with remainder
            if qty > 0:
                if self.position[security] == 0:
                    self.entry_price[security] = price
                    self.position[security] = -qty
                else:
                    # Weighted average entry
                    total_cost = self.entry_price[security] * abs(self.position[security]) + price * qty
                    self.position[security] -= qty
                    self.entry_price[security] = total_cost / abs(self.position[security])
        
        # Record trade (use original qty, not the reduced qty)
        self.trades[security].append({
            'timestamp': timestamp,
            'side': side,
            'fill_price': price,
            'fill_qty': original_qty,
            'realized_pnl': realized_pnl,
            'position': self.position[security],
            'pnl': self.pnl[security]
        })
        
        # Reset refill timer after fill
        # Map 'buy'/'sell' to 'bid'/'ask' for refill timer
        refill_side = 'bid' if side == 'buy' else 'ask'
        self.set_refill_time(security, refill_side, timestamp)
    
    def flatten_position(self, security: str, close_price: float, timestamp: datetime):
        """Force close all positions at given price (EOD flatten).
        
        Args:
            security: Security identifier
            close_price: Price to close at
            timestamp: Close time
        """
        if self.position[security] == 0:
            return
        
        if self.position[security] > 0:
            # Close long
            self._record_fill(security, 'sell', close_price, self.position[security], timestamp)
        else:
            # Close short
            self._record_fill(security, 'buy', close_price, abs(self.position[security]), timestamp)
    
    def get_total_pnl(self, security: str, mark_price: Optional[float] = None) -> float:
        """Get total P&L (realized + unrealized).
        
        Args:
            security: Security identifier
            mark_price: Current market price for unrealized P&L calculation
            
        Returns:
            Total P&L (realized + unrealized)
        """
        realized = self.pnl[security]
        unrealized = 0.0
        
        if mark_price is not None and self.position[security] != 0:
            unrealized = (mark_price - self.entry_price[security]) * self.position[security]
        
        return realized + unrealized
    
    def get_strategy_name(self) -> str:
        """Return the strategy name/version identifier.
        
        Returns:
            String identifying this strategy version
        """
        return self.__class__.__name__
    
    def get_strategy_description(self) -> str:
        """Return a brief description of this strategy.
        
        Returns:
            String describing the strategy's approach
        """
        return "Base market-making strategy"
