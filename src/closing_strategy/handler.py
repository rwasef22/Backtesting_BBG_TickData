"""
Closing Strategy Handler

Processes tick data and applies the closing strategy logic.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.closing_strategy.strategy import ClosingStrategy, Trade


def create_closing_strategy_handler(config: dict):
    """
    Factory function to create a closing strategy handler.
    
    Args:
        config: Strategy configuration dict
        
    Returns:
        Handler function for backtest framework
    """
    strategy = ClosingStrategy(config=config)
    
    def closing_handler(security: str, df: pd.DataFrame, state: dict) -> dict:
        """
        Process a chunk of data for one security.
        
        Args:
            security: Security symbol
            df: DataFrame with tick data (timestamp, type, price, volume)
            state: Current state dict
            
        Returns:
            Updated state dict
        """
        strategy.initialize_security(security)
        
        # Restore state from previous chunk if exists
        if state.get('exit_order'):
            strategy.exit_orders[security] = state['exit_order']
        if state.get('position'):
            strategy.position[security] = state['position']
        if state.get('pnl'):
            strategy.pnl[security] = state['pnl']
        if state.get('current_date'):
            strategy.current_date[security] = state['current_date']
        
        trades_this_chunk = []
        
        for row in df.itertuples(index=False):
            timestamp = row.timestamp if hasattr(row, 'timestamp') else row.Timestamp
            event_type = str(row.type if hasattr(row, 'type') else row.Type).lower()
            price = float(row.price if hasattr(row, 'price') else row.Price)
            volume = int(row.volume if hasattr(row, 'volume') else getattr(row, 'Volume', 0))
            
            # Check for date change
            current_date = timestamp.date()
            if strategy.current_date.get(security) != current_date:
                strategy.reset_daily_state(security, timestamp)
            
            # === Phase 1: Process exit orders from previous day ===
            # Only during regular trading hours (10:00 - 14:45)
            if (security in strategy.exit_orders and 
                strategy.is_regular_trading_hours(timestamp) and
                event_type == 'trade'):
                
                exit_trade = strategy.process_exit_order(
                    security, price, volume, timestamp
                )
                if exit_trade:
                    trades_this_chunk.append(exit_trade)
            
            # === Phase 2: VWAP Calculation Period (e.g., 14:31 - 14:46) ===
            if (strategy.is_in_vwap_period(security, timestamp) and 
                event_type == 'trade' and 
                not strategy.vwap_calculated.get(security, False)):
                
                strategy.update_vwap(security, price, volume)
            
            # === Phase 3: Place Auction Orders at 14:46 ===
            if (strategy.is_auction_order_time(timestamp) and 
                not strategy.auction_orders_placed.get(security, False)):
                
                vwap = strategy.calculate_vwap(security)
                if vwap is not None and vwap > 0:
                    strategy.place_auction_orders(security, vwap, timestamp)
                    strategy.vwap_calculated[security] = True
            
            # === Phase 4: Process Closing Auction (first trade >= 14:55) ===
            if (strategy.is_closing_auction_time(timestamp) and 
                event_type == 'trade' and
                not strategy.closing_price_processed.get(security, False)):
                
                # First trade at/after 14:55 is the closing price
                closing_trades = strategy.process_closing_price(
                    security, price, timestamp
                )
                trades_this_chunk.extend(closing_trades)
        
        # Update state for next chunk
        state['position'] = strategy.position.get(security, 0)
        state['pnl'] = strategy.pnl.get(security, 0)
        state['trades'] = strategy.trades.get(security, [])
        state['exit_order'] = strategy.exit_orders.get(security)
        state['current_date'] = strategy.current_date.get(security)
        state['summary'] = strategy.get_summary(security)
        
        return state
    
    return closing_handler


def process_security_closing_strategy(
    security: str,
    df: pd.DataFrame,
    config: dict
) -> dict:
    """
    Process an entire security's data with closing strategy.
    
    This is a simplified version for parallel processing where
    each security is processed independently.
    
    Args:
        security: Security symbol
        df: Full DataFrame for this security
        config: Strategy configuration
        
    Returns:
        Results dict with trades, P&L, etc.
    """
    handler = create_closing_strategy_handler(config)
    state = {}
    
    # Process all data
    state = handler(security, df, state)
    
    return {
        'security': security,
        'trades': state.get('trades', []),
        'pnl': state.get('pnl', 0),
        'position': state.get('position', 0),
        'summary': state.get('summary', {}),
    }
