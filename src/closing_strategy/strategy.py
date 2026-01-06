"""
Closing Strategy Implementation

Strategy Logic:
1. Calculate VWAP during pre-close period (default: 14:31 - 14:46, configurable)
2. At 14:46, place:
   - Buy order at VWAP * (1 - spread_vwap)
   - Sell order at VWAP * (1 + spread_vwap)
3. At closing auction (first trade >= 14:55):
   - If close price <= buy order price: buy executed
   - If close price >= sell order price: sell executed
4. Next trading day: exit at VWAP_preClose price
   - Execution when price crosses our order with sufficient volume
"""

import pandas as pd
from datetime import datetime, time, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field


@dataclass
class AuctionOrder:
    """Represents an order placed at the closing auction."""
    price: float
    quantity: int
    side: str  # 'buy' or 'sell'
    placed_time: datetime
    vwap_reference: float  # VWAP used to calculate this price


@dataclass
class ExitOrder:
    """Represents a pending exit order for the next day."""
    price: float
    quantity: int
    remaining_qty: int
    side: str  # 'buy' or 'sell' (opposite of entry)
    entry_price: float
    entry_time: datetime
    target_date: datetime  # The date when this order should be active


@dataclass
class Trade:
    """Represents an executed trade."""
    timestamp: datetime
    side: str
    price: float
    quantity: int
    realized_pnl: float
    trade_type: str  # 'auction_entry' or 'vwap_exit'
    vwap_reference: float


class ClosingStrategy:
    """
    Closing Auction Arbitrage Strategy.
    
    Places orders at the closing auction based on pre-close VWAP,
    then exits the next trading day at VWAP.
    """
    
    # UAE market hours
    PRECLOSE_END_TIME = time(14, 46, 0)  # When we place auction orders
    CLOSING_AUCTION_TIME = time(14, 55, 0)  # First trade at/after this is closing price
    TRADING_START_TIME = time(10, 0, 0)  # Regular trading starts
    TRADING_END_TIME = time(14, 45, 0)  # Regular trading ends
    
    def __init__(self, config: dict):
        """
        Initialize strategy with configuration.
        
        Config per security:
        {
            "SECURITY": {
                "vwap_preclose_period_min": 15,  # Minutes before 14:46 to calculate VWAP
                "spread_vwap_pct": 0.5,          # Spread around VWAP (%)
                "order_quantity": 50000,          # Quantity to trade
                "tick_size": 0.01                 # Tick size for rounding
            }
        }
        """
        self.config = config
        
        # Per-security state
        self.vwap_data: Dict[str, Dict] = {}  # {security: {sum_pv: float, sum_v: int}}
        self.auction_orders: Dict[str, Dict[str, AuctionOrder]] = {}  # {security: {buy: order, sell: order}}
        self.exit_orders: Dict[str, ExitOrder] = {}  # {security: exit_order}
        self.trades: Dict[str, List[Trade]] = {}  # {security: [trades]}
        self.pnl: Dict[str, float] = {}  # {security: realized_pnl}
        self.position: Dict[str, int] = {}  # {security: position}
        
        # Tracking
        self.current_date: Dict[str, datetime] = {}
        self.vwap_calculated: Dict[str, bool] = {}
        self.auction_orders_placed: Dict[str, bool] = {}
        self.closing_price_processed: Dict[str, bool] = {}
    
    def initialize_security(self, security: str):
        """Initialize state for a security."""
        if security not in self.trades:
            self.trades[security] = []
            self.pnl[security] = 0.0
            self.position[security] = 0
            self.vwap_data[security] = {'sum_pv': 0.0, 'sum_v': 0}
            self.auction_orders[security] = {}
            self.vwap_calculated[security] = False
            self.auction_orders_placed[security] = False
            self.closing_price_processed[security] = False
            self.current_date[security] = None
    
    def get_config(self, security: str) -> dict:
        """Get configuration for a security with defaults."""
        cfg = self.config.get(security, {})
        return {
            'vwap_preclose_period_min': cfg.get('vwap_preclose_period_min', 15),
            'spread_vwap_pct': cfg.get('spread_vwap_pct', 0.5),
            'order_quantity': cfg.get('order_quantity', 50000),
            'tick_size': cfg.get('tick_size', 0.01),
            'max_position': cfg.get('max_position', 100000),
        }
    
    def round_to_tick(self, price: float, tick_size: float) -> float:
        """Round price to nearest tick."""
        return round(price / tick_size) * tick_size
    
    def get_vwap_start_time(self, security: str) -> time:
        """Get the start time for VWAP calculation period."""
        cfg = self.get_config(security)
        period_min = cfg['vwap_preclose_period_min']
        # VWAP period ends at 14:46, starts period_min before
        end_dt = datetime.combine(datetime.today(), self.PRECLOSE_END_TIME)
        start_dt = end_dt - timedelta(minutes=period_min)
        return start_dt.time()
    
    def is_in_vwap_period(self, security: str, timestamp: datetime) -> bool:
        """Check if timestamp is in VWAP calculation period."""
        t = timestamp.time()
        vwap_start = self.get_vwap_start_time(security)
        return vwap_start <= t < self.PRECLOSE_END_TIME
    
    def is_auction_order_time(self, timestamp: datetime) -> bool:
        """Check if it's time to place auction orders (14:46)."""
        t = timestamp.time()
        return t >= self.PRECLOSE_END_TIME and t < self.CLOSING_AUCTION_TIME
    
    def is_closing_auction_time(self, timestamp: datetime) -> bool:
        """Check if timestamp is at/after closing auction (14:55+)."""
        return timestamp.time() >= self.CLOSING_AUCTION_TIME
    
    def is_regular_trading_hours(self, timestamp: datetime) -> bool:
        """Check if in regular trading hours (10:00 - 14:45)."""
        t = timestamp.time()
        return self.TRADING_START_TIME <= t < self.TRADING_END_TIME
    
    def reset_daily_state(self, security: str, new_date: datetime):
        """Reset daily state for a new trading day."""
        self.vwap_data[security] = {'sum_pv': 0.0, 'sum_v': 0}
        self.auction_orders[security] = {}
        self.vwap_calculated[security] = False
        self.auction_orders_placed[security] = False
        self.closing_price_processed[security] = False
        self.current_date[security] = new_date.date()
    
    def update_vwap(self, security: str, price: float, volume: int):
        """Update VWAP calculation with a trade."""
        if volume > 0 and price > 0:
            self.vwap_data[security]['sum_pv'] += price * volume
            self.vwap_data[security]['sum_v'] += volume
    
    def calculate_vwap(self, security: str) -> Optional[float]:
        """Calculate VWAP from accumulated data."""
        data = self.vwap_data[security]
        if data['sum_v'] > 0:
            return data['sum_pv'] / data['sum_v']
        return None
    
    def place_auction_orders(self, security: str, vwap: float, timestamp: datetime):
        """Place buy and sell orders for the closing auction."""
        cfg = self.get_config(security)
        spread_pct = cfg['spread_vwap_pct'] / 100.0
        tick_size = cfg['tick_size']
        quantity = cfg['order_quantity']
        
        # Calculate order prices
        buy_price = self.round_to_tick(vwap * (1 - spread_pct), tick_size)
        sell_price = self.round_to_tick(vwap * (1 + spread_pct), tick_size)
        
        # Check position limits before placing orders
        current_pos = self.position.get(security, 0)
        max_pos = cfg['max_position']
        
        # Only place buy order if we have room to go long
        if current_pos < max_pos:
            buy_qty = min(quantity, max_pos - current_pos)
            if buy_qty > 0:
                self.auction_orders[security]['buy'] = AuctionOrder(
                    price=buy_price,
                    quantity=buy_qty,
                    side='buy',
                    placed_time=timestamp,
                    vwap_reference=vwap
                )
        
        # Only place sell order if we have room to go short
        if current_pos > -max_pos:
            sell_qty = min(quantity, max_pos + current_pos)
            if sell_qty > 0:
                self.auction_orders[security]['sell'] = AuctionOrder(
                    price=sell_price,
                    quantity=sell_qty,
                    side='sell',
                    placed_time=timestamp,
                    vwap_reference=vwap
                )
        
        self.auction_orders_placed[security] = True
    
    def process_closing_price(self, security: str, close_price: float, 
                              timestamp: datetime) -> List[Trade]:
        """
        Process the closing auction price.
        
        If close price crosses our order price, we're executed.
        """
        executed_trades = []
        orders = self.auction_orders.get(security, {})
        
        # Check buy order execution
        if 'buy' in orders:
            buy_order = orders['buy']
            if close_price <= buy_order.price:
                # Buy order executed
                trade = self._execute_auction_trade(
                    security, buy_order, close_price, timestamp
                )
                executed_trades.append(trade)
                
                # Create exit order for next day
                self._create_exit_order(security, trade, timestamp)
        
        # Check sell order execution
        if 'sell' in orders:
            sell_order = orders['sell']
            if close_price >= sell_order.price:
                # Sell order executed
                trade = self._execute_auction_trade(
                    security, sell_order, close_price, timestamp
                )
                executed_trades.append(trade)
                
                # Create exit order for next day
                self._create_exit_order(security, trade, timestamp)
        
        self.closing_price_processed[security] = True
        return executed_trades
    
    def _execute_auction_trade(self, security: str, order: AuctionOrder,
                               execution_price: float, timestamp: datetime) -> Trade:
        """Execute an auction order."""
        # Update position
        if order.side == 'buy':
            self.position[security] = self.position.get(security, 0) + order.quantity
        else:
            self.position[security] = self.position.get(security, 0) - order.quantity
        
        trade = Trade(
            timestamp=timestamp,
            side=order.side,
            price=execution_price,
            quantity=order.quantity,
            realized_pnl=0.0,  # P&L realized on exit
            trade_type='auction_entry',
            vwap_reference=order.vwap_reference
        )
        self.trades[security].append(trade)
        return trade
    
    def _create_exit_order(self, security: str, entry_trade: Trade, 
                           timestamp: datetime):
        """Create exit order for the next trading day."""
        # Exit side is opposite of entry
        exit_side = 'sell' if entry_trade.side == 'buy' else 'buy'
        
        # Exit at the VWAP that was used for entry calculation
        exit_price = entry_trade.vwap_reference
        
        cfg = self.get_config(security)
        exit_price = self.round_to_tick(exit_price, cfg['tick_size'])
        
        # Next trading day (simplified - just next calendar day)
        # In production, would need proper trading calendar
        next_day = timestamp.date() + timedelta(days=1)
        
        self.exit_orders[security] = ExitOrder(
            price=exit_price,
            quantity=entry_trade.quantity,
            remaining_qty=entry_trade.quantity,
            side=exit_side,
            entry_price=entry_trade.price,
            entry_time=entry_trade.timestamp,
            target_date=next_day
        )
    
    def process_exit_order(self, security: str, trade_price: float, 
                           trade_volume: int, timestamp: datetime) -> Optional[Trade]:
        """
        Process potential exit order execution.
        
        Exit order executes when:
        - Price crosses our order price
        - Volume determines fill amount (partial or full)
        """
        if security not in self.exit_orders:
            return None
        
        exit_order = self.exit_orders[security]
        
        # Check if this is the right day
        if timestamp.date() < exit_order.target_date:
            return None
        
        # Check if order is already fully filled
        if exit_order.remaining_qty <= 0:
            return None
        
        # Check price crossing
        price_crossed = False
        if exit_order.side == 'sell':
            # Sell exit: price must be >= our ask
            price_crossed = trade_price >= exit_order.price
        else:
            # Buy exit: price must be <= our bid
            price_crossed = trade_price <= exit_order.price
        
        if not price_crossed:
            return None
        
        # Determine fill quantity
        fill_qty = min(exit_order.remaining_qty, trade_volume)
        if fill_qty <= 0:
            return None
        
        # Execute the fill
        exit_order.remaining_qty -= fill_qty
        
        # Calculate P&L
        if exit_order.side == 'sell':
            # We're selling what we bought
            realized_pnl = (trade_price - exit_order.entry_price) * fill_qty
            self.position[security] -= fill_qty
        else:
            # We're buying back what we sold short
            realized_pnl = (exit_order.entry_price - trade_price) * fill_qty
            self.position[security] += fill_qty
        
        self.pnl[security] = self.pnl.get(security, 0) + realized_pnl
        
        trade = Trade(
            timestamp=timestamp,
            side=exit_order.side,
            price=trade_price,
            quantity=fill_qty,
            realized_pnl=realized_pnl,
            trade_type='vwap_exit',
            vwap_reference=exit_order.price
        )
        self.trades[security].append(trade)
        
        # Remove exit order if fully filled
        if exit_order.remaining_qty <= 0:
            del self.exit_orders[security]
        
        return trade
    
    def get_strategy_name(self) -> str:
        return "closing_strategy"
    
    def get_summary(self, security: str) -> dict:
        """Get summary statistics for a security."""
        trades = self.trades.get(security, [])
        return {
            'security': security,
            'total_trades': len(trades),
            'auction_entries': len([t for t in trades if t.trade_type == 'auction_entry']),
            'vwap_exits': len([t for t in trades if t.trade_type == 'vwap_exit']),
            'realized_pnl': self.pnl.get(security, 0),
            'final_position': self.position.get(security, 0),
        }
