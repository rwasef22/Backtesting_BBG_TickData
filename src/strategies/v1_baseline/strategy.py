"""V1 Baseline Market-Making Strategy.

This is the original/baseline market-making strategy that:
- Quotes at best bid/ask with configurable size
- Refills orders at configurable time intervals
- Respects max position limits per security
- Skips opening auction (9:30-10:00) and silent period (10:00-10:05)
- Skips closing auction (14:45-15:00)
- Flattens position at EOD close (14:55) at closing price
- Uses simple time-based refill logic
- Position-aware quote sizing

This serves as the reference implementation that other variations
can be compared against.
"""
from datetime import datetime
from typing import Dict, Optional, Tuple
import sys
import os

# Add parent directory to path to import base_strategy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from strategies.base_strategy import BaseMarketMakingStrategy


class V1BaselineStrategy(BaseMarketMakingStrategy):
    """V1 Baseline: Simple time-based refill with position limits.
    
    Key characteristics:
    - Quote at best bid/ask (join the market)
    - Time-based refill every N seconds (default 180s)
    - Position-aware sizing (reduce size as inventory grows)
    - Independent bid/ask liquidity checks
    - FIFO queue simulation for realistic fills
    """
    
    def generate_quotes(self, security: str, best_bid: Optional[Tuple[float, float]], 
                       best_ask: Optional[Tuple[float, float]]) -> dict:
        """Generate quotes at best bid/ask with position-aware sizing.
        
        Logic:
        - Quote at current best bid/ask (market joining)
        - Size dynamically adjusted based on position and limits
        - Prevents violating max_position constraints
        - Supports max_notional cap for dynamic position limits
        
        Args:
            security: Security identifier
            best_bid: (price, quantity) of current best bid or None
            best_ask: (price, quantity) of current best ask or None
            
        Returns:
            Dictionary with bid_price, ask_price, bid_size, ask_size
        """
        # Allow quoting even if only one side available
        if best_bid is None and best_ask is None:
            return None
        
        cfg = self.get_config(security)
        bid_quote_size = cfg['quote_size_bid']
        ask_quote_size = cfg['quote_size_ask']
        max_pos = cfg['max_position']
        max_notional = cfg.get('max_notional')
        
        bid_price, bid_qty = (best_bid if best_bid is not None else (None, 0))
        ask_price, ask_qty = (best_ask if best_ask is not None else (None, 0))

        # Dynamic position limit based on max_notional if provided
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
        
        # Position-aware sizing
        current_pos = self.position[security]
        
        # Bid size: limited by headroom to +max_pos
        bid_size = 0 if bid_price is None else min(bid_quote_size, int(max_pos - current_pos))
        bid_size = max(0, bid_size)
        
        # Ask size: limited by headroom to -max_pos
        ask_size = 0 if ask_price is None else min(ask_quote_size, int(max_pos + current_pos))
        ask_size = max(0, ask_size)
        
        return {
            'bid_price': bid_price,
            'ask_price': ask_price,
            'bid_size': bid_size,
            'ask_size': ask_size,
        }
    
    def should_refill_side(self, security: str, timestamp: datetime, side: str) -> bool:
        """Time-based refill logic: update quotes every N seconds.
        
        Refill conditions:
        1. No previous quote on this side → TRUE (first time)
        2. Last quote was >= refill_interval ago → TRUE (cooldown expired)
        3. Otherwise → FALSE (quote still "sticking")
        
        This allows quotes to remain in the orderbook for the interval,
        accumulating queue priority and increasing fill probability.
        
        Args:
            security: Security identifier
            timestamp: Current time
            side: 'bid' or 'ask'
            
        Returns:
            True if should place new quote, False otherwise
        """
        cfg = self.get_config(security)
        interval_sec = cfg['refill_interval_sec']

        last = self.last_refill_time.get(security, {}).get(side)
        if last is None:
            return True  # First quote ever

        try:
            elapsed = (timestamp - last).total_seconds()
            return elapsed >= interval_sec
        except Exception:
            return True
    
    def get_strategy_name(self) -> str:
        """Return strategy identifier."""
        return "v1_baseline"
    
    def get_strategy_description(self) -> str:
        """Return strategy description."""
        return ("V1 Baseline: Time-based refill market maker. Quotes at best bid/ask "
                "with position-aware sizing. Refills every 180 seconds.")
