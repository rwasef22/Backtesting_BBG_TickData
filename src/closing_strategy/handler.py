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


def create_closing_strategy_handler(config: dict, exchange_mapping: dict = None, 
                                    last_trade_date=None, auction_fill_pct: float = 10.0):
    """
    Factory function to create a closing strategy handler.
    
    Args:
        config: Strategy configuration dict
        exchange_mapping: Dict mapping security names to exchange (ADX/DFM)
        last_trade_date: Last trading date in data - skip auction entry on this day
        auction_fill_pct: Maximum fill as percentage of auction volume (default 10%)
        
    Returns:
        Handler function for backtest framework
    """
    strategy = ClosingStrategy(config=config, exchange_mapping=exchange_mapping, 
                               auction_fill_pct=auction_fill_pct)
    
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
        if state.get('entry_price'):
            strategy.entry_price[security] = state['entry_price']
        if state.get('best_bid'):
            strategy.best_bid[security] = state['best_bid']
        if state.get('best_ask'):
            strategy.best_ask[security] = state['best_ask']
        
        trades_this_chunk = []
        
        for row in df.itertuples(index=False):
            timestamp = row.timestamp if hasattr(row, 'timestamp') else row.Timestamp
            event_type = str(row.type if hasattr(row, 'type') else row.Type).lower()
            price = float(row.price if hasattr(row, 'price') else row.Price)
            volume = int(row.volume if hasattr(row, 'volume') else getattr(row, 'Volume', 0))
            
            # Check for date change - process pending auction BEFORE resetting
            current_date = timestamp.date()
            if strategy.current_date.get(security) != current_date:
                # Process any pending closing auction from previous day
                if (hasattr(strategy, '_closing_price') and 
                    security in strategy._closing_price and
                    not strategy.closing_price_processed.get(security, False)):
                    
                    close_price, close_timestamp = strategy._closing_price[security]
                    closing_trades = strategy.process_closing_price(
                        security, close_price, close_timestamp
                    )
                    trades_this_chunk.extend(closing_trades)
                    
                    # Flatten any remaining exit orders at closing price
                    flatten_trade = strategy.flatten_position_at_close(
                        security, close_price, close_timestamp
                    )
                    if flatten_trade:
                        trades_this_chunk.append(flatten_trade)
                    
                    # Clean up
                    del strategy._closing_price[security]
                
                # Now reset for new day
                strategy.reset_daily_state(security, timestamp)
            
            # Update orderbook with bid/ask quotes
            strategy.update_orderbook(security, event_type, price)
            
            # === Phase 0: Update trend data for SELL entry filter ===
            # Track all trades during regular hours for trend calculation
            if event_type == 'trade' and strategy.is_regular_trading_hours(timestamp):
                strategy.update_trend_data(security, timestamp, price)
            
            # === Phase 0.5: Check Stop-Loss ===
            # Only during regular trading hours when we have a position
            if strategy.is_regular_trading_hours(timestamp):
                stop_loss_trade = strategy.check_stop_loss(security, timestamp)
                if stop_loss_trade:
                    trades_this_chunk.append(stop_loss_trade)
            
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
            
            # === Phase 2: VWAP Calculation Period (e.g., 14:30 - 14:45) ===
            if (strategy.is_in_vwap_period(security, timestamp) and 
                event_type == 'trade' and 
                not strategy.vwap_calculated.get(security, False)):
                
                strategy.update_vwap(security, price, volume)
            
            # === Phase 3: Place Auction Orders at 14:45 ===
            # Skip on last trading day - no next day to exit
            # Skip if we have a pending exit order (unfilled position from previous day)
            is_last_day = last_trade_date and current_date == last_trade_date
            has_pending_exit = (security in strategy.exit_orders and 
                               strategy.exit_orders[security].remaining_qty > 0)
            if (strategy.is_auction_order_time(timestamp) and 
                not strategy.auction_orders_placed.get(security, False) and
                not is_last_day and
                not has_pending_exit):
                
                vwap = strategy.calculate_vwap(security)
                if vwap is not None and vwap > 0:
                    strategy.place_auction_orders(security, vwap, timestamp)
                    strategy.vwap_calculated[security] = True
            
            # === Phase 4: Accumulate Auction Volume and Track Closing Price ===
            # During auction time (14:55-15:00), accumulate all trade volume
            if (strategy.is_closing_auction_time(timestamp) and event_type == 'trade'):
                # Accumulate auction volume
                strategy.update_auction_volume(security, volume)
                
                # Track first trade as closing price (14:55:00 trade)
                if not strategy.closing_price_processed.get(security, False):
                    # Store closing price for later processing
                    if not hasattr(strategy, '_closing_price'):
                        strategy._closing_price = {}
                    if security not in strategy._closing_price:
                        strategy._closing_price[security] = (price, timestamp)
        
        # === End of Data: Process any pending closing auction ===
        if (hasattr(strategy, '_closing_price') and 
            security in strategy._closing_price and
            not strategy.closing_price_processed.get(security, False)):
            
            close_price, close_timestamp = strategy._closing_price[security]
            closing_trades = strategy.process_closing_price(
                security, close_price, close_timestamp
            )
            trades_this_chunk.extend(closing_trades)
            
            # Flatten any remaining exit orders at closing price
            flatten_trade = strategy.flatten_position_at_close(
                security, close_price, close_timestamp
            )
            if flatten_trade:
                trades_this_chunk.append(flatten_trade)
            
            # Clean up
            del strategy._closing_price[security]
        
        # Update state for next chunk
        state['position'] = strategy.position.get(security, 0)
        state['pnl'] = strategy.pnl.get(security, 0)
        state['trades'] = strategy.trades.get(security, [])
        state['exit_order'] = strategy.exit_orders.get(security)
        state['current_date'] = strategy.current_date.get(security)
        state['entry_price'] = strategy.entry_price.get(security, 0)
        state['best_bid'] = strategy.best_bid.get(security, 0)
        state['best_ask'] = strategy.best_ask.get(security, 0)
        state['summary'] = strategy.get_summary(security)
        
        return state
    
    return closing_handler


def process_security_closing_strategy(
    security: str,
    df: pd.DataFrame,
    config: dict,
    exchange_mapping: dict = None,
    auction_fill_pct: float = 10.0
) -> dict:
    """
    Process an entire security's data with closing strategy.
    
    This is a simplified version for parallel processing where
    each security is processed independently.
    
    Args:
        security: Security symbol
        df: Full DataFrame for this security
        config: Strategy configuration
        exchange_mapping: Dict mapping security names to exchange (ADX/DFM)
        auction_fill_pct: Maximum fill as percentage of auction volume (default 10%)
        
    Returns:
        Results dict with trades, P&L, etc.
    """
    # Determine the last trading day to avoid entering on final day
    timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'Timestamp'
    last_date = df[timestamp_col].max().date()
    
    handler = create_closing_strategy_handler(config, exchange_mapping, last_date, auction_fill_pct)
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
