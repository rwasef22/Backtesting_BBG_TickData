"""
Closing Strategy Implementation

Strategy Logic:
1. Calculate VWAP during pre-close period (default: 14:30 - 14:45, configurable)
2. At 14:45, place:
   - Buy order at VWAP * (1 - spread_vwap)
   - Sell order at VWAP * (1 + spread_vwap)
3. At closing auction (first trade >= 14:55):
   - If close price <= buy order price: buy executed
   - If close price >= sell order price: sell executed
4. Next trading day: exit at VWAP_preClose price
   - Execution when price crosses our order with sufficient volume
"""

import pandas as pd
import json
import os
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
    PRECLOSE_END_TIME = time(14, 45, 0)  # When VWAP calculation ends and we place auction orders
    CLOSING_AUCTION_TIME = time(14, 55, 0)  # First trade at/after this is closing price
    TRADING_START_TIME = time(10, 0, 0)  # Regular trading starts
    TRADING_END_TIME = time(14, 45, 0)  # Regular trading ends
    STOP_LOSS_START_TIME = time(10, 10, 0)  # Stop-loss monitoring starts
    STOP_LOSS_END_TIME = time(14, 44, 0)  # Stop-loss monitoring ends
    
    def __init__(self, config: dict, exchange_mapping: Dict[str, str] = None,
                 auction_fill_pct: float = 10.0):
        """
        Initialize strategy with configuration.
        
        Config per security:
        {
            "SECURITY": {
                "vwap_preclose_period_min": 15,  # Minutes before 14:45 to calculate VWAP
                "spread_vwap_pct": 0.5,          # Spread around VWAP (%)
                "order_notional": 250000,         # Local currency value for orders
                "stop_loss_threshold_pct": 2.0,  # Stop-loss threshold (%)
                "trend_filter_sell_enabled": True,     # Enable trend filter for SELL entries
                "trend_filter_sell_threshold_bps_hr": 10.0,  # Skip SELL if uptrend > threshold
                "trend_filter_buy_enabled": False,     # Enable trend filter for BUY entries
                "trend_filter_buy_threshold_bps_hr": 10.0   # Skip BUY if downtrend < -threshold
            }
        }
        
        Exchange mapping: {"SECURITY": "ADX" or "DFM"}
        auction_fill_pct: Maximum fill as percentage of auction volume (default 10%)
        """
        self.config = config
        self.exchange_mapping = exchange_mapping or {}
        self.auction_fill_pct = auction_fill_pct / 100.0  # Convert to decimal
        
        # Per-security state
        self.vwap_data: Dict[str, Dict] = {}  # {security: {sum_pv: float, sum_v: int}}
        self.auction_orders: Dict[str, Dict[str, AuctionOrder]] = {}  # {security: {buy: order, sell: order}}
        self.exit_orders: Dict[str, ExitOrder] = {}  # {security: exit_order}
        self.trades: Dict[str, List[Trade]] = {}  # {security: [trades]}
        self.pnl: Dict[str, float] = {}  # {security: realized_pnl}
        self.position: Dict[str, int] = {}  # {security: position}
        self.entry_price: Dict[str, float] = {}  # {security: avg_entry_price}
        
        # Best bid/ask tracking for stop-loss execution
        self.best_bid: Dict[str, float] = {}  # {security: best_bid}
        self.best_ask: Dict[str, float] = {}  # {security: best_ask}
        
        # Tracking
        self.current_date: Dict[str, datetime] = {}
        self.vwap_calculated: Dict[str, bool] = {}
        self.auction_orders_placed: Dict[str, bool] = {}
        self.closing_price_processed: Dict[str, bool] = {}
        
        # Auction volume tracking for execution probability
        self.auction_volume: Dict[str, int] = {}  # {security: total_auction_volume}
        
        # Trend tracking for entry filter
        self.trend_data: Dict[str, List[Tuple[float, float]]] = {}  # {security: [(time_hours, price)]}
        self.daily_trend_slope: Dict[str, float] = {}  # {security: slope_bps_per_hour}
        self.filtered_sell_entries: Dict[str, int] = {}  # {security: count of filtered SELL entries}
        self.filtered_buy_entries: Dict[str, int] = {}  # {security: count of filtered BUY entries}
    
    def initialize_security(self, security: str):
        """Initialize state for a security."""
        if security not in self.trades:
            self.trades[security] = []
            self.pnl[security] = 0.0
            self.position[security] = 0
            self.entry_price[security] = 0.0
            self.best_bid[security] = 0.0
            self.best_ask[security] = 0.0
            self.vwap_data[security] = {'sum_pv': 0.0, 'sum_v': 0}
            self.auction_orders[security] = {}
            self.vwap_calculated[security] = False
            self.auction_orders_placed[security] = False
            self.closing_price_processed[security] = False
            self.current_date[security] = None
            self.auction_volume[security] = 0
            self.trend_data[security] = []
            self.daily_trend_slope[security] = 0.0
            self.filtered_sell_entries[security] = 0
            self.filtered_buy_entries[security] = 0
    
    def get_config(self, security: str) -> dict:
        """Get configuration for a security with defaults."""
        cfg = self.config.get(security, {})
        return {
            'vwap_preclose_period_min': cfg.get('vwap_preclose_period_min', 15),
            'spread_vwap_pct': cfg.get('spread_vwap_pct', 0.5),
            'order_notional': cfg.get('order_notional', 250000),  # Local currency value for orders
            'stop_loss_threshold_pct': cfg.get('stop_loss_threshold_pct', 2.0),
            'trend_filter_sell_enabled': cfg.get('trend_filter_sell_enabled', True),  # Filter SELL in uptrends
            'trend_filter_sell_threshold_bps_hr': cfg.get('trend_filter_sell_threshold_bps_hr', 10.0),
            'trend_filter_buy_enabled': cfg.get('trend_filter_buy_enabled', False),  # Filter BUY in downtrends (off by default)
            'trend_filter_buy_threshold_bps_hr': cfg.get('trend_filter_buy_threshold_bps_hr', 10.0),
        }
    
    def get_exchange(self, security: str) -> str:
        """Get exchange for a security from mapping. Defaults to ADX."""
        return self.exchange_mapping.get(security, 'ADX')
    
    def get_tick_size(self, security: str, price: float) -> float:
        """
        Get tick size based on price and exchange.
        
        ADX tick sizes:
        - price < 1: 0.001
        - 1 <= price < 10: 0.01
        - 10 <= price < 50: 0.02
        - 50 <= price < 100: 0.05
        - price >= 100: 0.1
        
        DFM tick sizes:
        - price < 1: 0.001
        - 1 <= price < 10: 0.01
        - price >= 10: 0.05
        """
        exchange = self.get_exchange(security)
        
        if exchange == 'DFM':
            if price < 1:
                return 0.001
            elif price < 10:
                return 0.01
            else:
                return 0.05
        else:  # ADX (default)
            if price < 1:
                return 0.001
            elif price < 10:
                return 0.01
            elif price < 50:
                return 0.02
            elif price < 100:
                return 0.05
            else:
                return 0.1
    
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
        """Check if it's time to place auction orders (14:45 - 14:55)."""
        t = timestamp.time()
        return t >= self.PRECLOSE_END_TIME and t < self.CLOSING_AUCTION_TIME
    
    def is_closing_auction_time(self, timestamp: datetime) -> bool:
        """Check if timestamp is at/after closing auction (14:55+)."""
        return timestamp.time() >= self.CLOSING_AUCTION_TIME
    
    def is_regular_trading_hours(self, timestamp: datetime) -> bool:
        """Check if in regular trading hours (10:00 - 14:45)."""
        t = timestamp.time()
        return self.TRADING_START_TIME <= t < self.TRADING_END_TIME
    
    def update_orderbook(self, security: str, event_type: str, price: float):
        """Update best bid/ask from quote events."""
        if event_type == 'bid' and price > 0:
            self.best_bid[security] = price
        elif event_type == 'ask' and price > 0:
            self.best_ask[security] = price
    
    def check_stop_loss(self, security: str, timestamp: datetime) -> Optional[Trade]:
        """
        Check if stop-loss should trigger and execute if needed.
        
        Stop-loss triggers when unrealized P&L exceeds threshold.
        - Long position: sell at best bid
        - Short position: buy at best ask
        - Only active between 10:10 and 14:44
        
        Returns:
            Trade if stop-loss executed, None otherwise
        """
        # Check if within stop-loss monitoring window (10:10 - 14:44)
        t = timestamp.time()
        if not (self.STOP_LOSS_START_TIME <= t < self.STOP_LOSS_END_TIME):
            return None
        
        position = self.position.get(security, 0)
        if position == 0:
            return None
        
        entry_price = self.entry_price.get(security, 0)
        if entry_price <= 0:
            return None
        
        cfg = self.get_config(security)
        stop_loss_pct = cfg['stop_loss_threshold_pct']
        
        # Calculate unrealized P&L percentage
        if position > 0:
            # Long: mark-to-market at best bid
            mark_price = self.best_bid.get(security, 0)
            if mark_price <= 0:
                return None
            unrealized_pnl_pct = ((mark_price - entry_price) / entry_price) * 100
        else:
            # Short: mark-to-market at best ask
            mark_price = self.best_ask.get(security, 0)
            if mark_price <= 0:
                return None
            unrealized_pnl_pct = ((entry_price - mark_price) / entry_price) * 100
        
        # Check if loss exceeds threshold (negative unrealized P&L)
        if unrealized_pnl_pct >= -stop_loss_pct:
            return None
        
        # Execute stop-loss
        if position > 0:
            # Long position: sell at best bid
            exit_price = self.best_bid[security]
            exit_qty = position
            exit_side = 'sell'
            realized_pnl = (exit_price - entry_price) * exit_qty
        else:
            # Short position: buy at best ask
            exit_price = self.best_ask[security]
            exit_qty = abs(position)
            exit_side = 'buy'
            realized_pnl = (entry_price - exit_price) * exit_qty
        
        # Update state
        self.position[security] = 0
        self.entry_price[security] = 0.0
        self.pnl[security] = self.pnl.get(security, 0) + realized_pnl
        
        # Cancel any pending exit order
        if security in self.exit_orders:
            del self.exit_orders[security]
        
        trade = Trade(
            timestamp=timestamp,
            side=exit_side,
            price=exit_price,
            quantity=exit_qty,
            realized_pnl=realized_pnl,
            trade_type='stop_loss',
            vwap_reference=entry_price
        )
        self.trades[security].append(trade)
        return trade
    
    def reset_daily_state(self, security: str, new_date: datetime):
        """Reset daily state for a new trading day."""
        self.vwap_data[security] = {'sum_pv': 0.0, 'sum_v': 0}
        self.auction_orders[security] = {}
        self.vwap_calculated[security] = False
        self.auction_orders_placed[security] = False
        self.closing_price_processed[security] = False
        self.current_date[security] = new_date.date()
        self.auction_volume[security] = 0  # Reset auction volume for new day
        self.trend_data[security] = []  # Reset trend data for new day
        self.daily_trend_slope[security] = 0.0
    
    def update_trend_data(self, security: str, timestamp: datetime, price: float):
        """
        Update trend data with a trade price during regular hours.
        Called for each trade to build trend slope calculation.
        """
        # Only track during regular trading hours (10:00 - 14:45)
        if not self.is_regular_trading_hours(timestamp):
            return
        
        # Convert timestamp to hours since 10:00
        t = timestamp.time()
        hours_since_open = (t.hour - 10) + t.minute / 60.0 + t.second / 3600.0
        
        if security not in self.trend_data:
            self.trend_data[security] = []
        
        self.trend_data[security].append((hours_since_open, price))
    
    def calculate_trend_slope(self, security: str) -> float:
        """
        Calculate trend slope in basis points per hour using linear regression.
        
        Returns:
            Slope in bps/hour (positive = uptrend, negative = downtrend)
        """
        data = self.trend_data.get(security, [])
        if len(data) < 10:  # Need minimum data points
            return 0.0
        
        # Simple linear regression
        n = len(data)
        sum_x = sum(d[0] for d in data)
        sum_y = sum(d[1] for d in data)
        sum_xy = sum(d[0] * d[1] for d in data)
        sum_x2 = sum(d[0] ** 2 for d in data)
        
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0
        
        # Slope in price units per hour
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Convert to basis points per hour (relative to mean price)
        mean_price = sum_y / n
        if mean_price == 0:
            return 0.0
        
        slope_bps_per_hour = (slope / mean_price) * 10000
        
        return slope_bps_per_hour
    
    def should_filter_sell_entry(self, security: str) -> bool:
        """
        Check if SELL entry should be filtered based on trend.
        
        Returns True if:
        - trend_filter_sell_enabled is True
        - Daily trend slope exceeds trend_filter_sell_threshold_bps_hr (uptrend)
        
        The analysis showed SELL entries in uptrends (>10 bps/hr) have
        only 65% win rate vs 86% in downtrends, losing ~1,668 AED per trade.
        """
        cfg = self.get_config(security)
        
        if not cfg.get('trend_filter_sell_enabled', True):
            return False
        
        threshold = cfg.get('trend_filter_sell_threshold_bps_hr', 10.0)
        
        # Calculate current trend slope
        slope = self.calculate_trend_slope(security)
        self.daily_trend_slope[security] = slope
        
        # Filter if slope exceeds threshold (strong uptrend)
        if slope > threshold:
            self.filtered_sell_entries[security] = self.filtered_sell_entries.get(security, 0) + 1
            return True
        
        return False
    
    def should_filter_buy_entry(self, security: str) -> bool:
        """
        Check if BUY entry should be filtered based on trend.
        
        Returns True if:
        - trend_filter_buy_enabled is True
        - Daily trend slope is below -trend_filter_buy_threshold_bps_hr (downtrend)
        
        This is the mirror of should_filter_sell_entry - filters BUY in downtrends.
        """
        cfg = self.get_config(security)
        
        if not cfg.get('trend_filter_buy_enabled', False):
            return False
        
        threshold = cfg.get('trend_filter_buy_threshold_bps_hr', 10.0)
        
        # Calculate current trend slope (may already be calculated)
        slope = self.calculate_trend_slope(security)
        self.daily_trend_slope[security] = slope
        
        # Filter if slope is below negative threshold (strong downtrend)
        if slope < -threshold:
            self.filtered_buy_entries[security] = self.filtered_buy_entries.get(security, 0) + 1
            return True
        
        return False
    
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
        """
        Place buy and sell orders for the closing auction.
        
        Entry filtering based on trend (if trend_filter_enabled=True):
        - SELL filtered if trend > threshold (uptrend) 
        - BUY filtered if trend < -threshold (downtrend) AND trend_filter_sell_only=False
        
        Based on analysis: SELL entries in uptrends (>10 bps/hr) have 65% win rate 
        vs 86% in downtrends, losing ~1,668 AED per filtered trade.
        """
        cfg = self.get_config(security)
        spread_pct = cfg['spread_vwap_pct'] / 100.0
        
        # Calculate quantity from notional value (default 250,000 AED)
        order_notional = cfg['order_notional']
        quantity = round(order_notional / vwap)  # Round to closest share
        
        # Calculate order prices with dynamic tick size based on price and exchange
        buy_price_raw = vwap * (1 - spread_pct)
        sell_price_raw = vwap * (1 + spread_pct)
        
        buy_tick_size = self.get_tick_size(security, buy_price_raw)
        sell_tick_size = self.get_tick_size(security, sell_price_raw)
        
        buy_price = self.round_to_tick(buy_price_raw, buy_tick_size)
        sell_price = self.round_to_tick(sell_price_raw, sell_tick_size)
        
        # Check if entries should be filtered based on trend
        filter_sell = self.should_filter_sell_entry(security)
        filter_buy = self.should_filter_buy_entry(security)
        
        # Place buy order (if not filtered)
        if quantity > 0 and not filter_buy:
            self.auction_orders[security]['buy'] = AuctionOrder(
                price=buy_price,
                quantity=quantity,
                side='buy',
                placed_time=timestamp,
                vwap_reference=vwap
            )
        
        # Place sell order (if not filtered)
        if quantity > 0 and not filter_sell:
            self.auction_orders[security]['sell'] = AuctionOrder(
                price=sell_price,
                quantity=quantity,
                side='sell',
                placed_time=timestamp,
                vwap_reference=vwap
            )
        
        self.auction_orders_placed[security] = True
    
    def update_auction_volume(self, security: str, volume: int):
        """Update auction volume accumulator."""
        self.auction_volume[security] = self.auction_volume.get(security, 0) + volume
    
    def get_max_fill_quantity(self, security: str, order_quantity: int) -> int:
        """
        Get maximum fill quantity based on auction volume.
        
        Execution probability: We can only fill up to auction_fill_pct of total auction volume.
        This ensures we're not assuming unrealistic fills.
        """
        auction_vol = self.auction_volume.get(security, 0)
        max_fill = int(auction_vol * self.auction_fill_pct)
        return min(order_quantity, max_fill)
    
    def process_closing_price(self, security: str, close_price: float, 
                              timestamp: datetime) -> List[Trade]:
        """
        Process the closing auction price.
        
        If close price crosses our order price, we're executed.
        Fill quantity is limited to auction_fill_pct of auction volume.
        """
        executed_trades = []
        orders = self.auction_orders.get(security, {})
        
        # Check buy order execution
        if 'buy' in orders:
            buy_order = orders['buy']
            if close_price <= buy_order.price:
                # Calculate fill quantity (limited by auction volume)
                fill_qty = self.get_max_fill_quantity(security, buy_order.quantity)
                if fill_qty > 0:
                    # Buy order executed (possibly partial)
                    trade = self._execute_auction_trade(
                        security, buy_order, close_price, timestamp, fill_qty
                    )
                    executed_trades.append(trade)
                    
                    # Create exit order for next day
                    self._create_exit_order(security, trade, timestamp)
        
        # Check sell order execution
        if 'sell' in orders:
            sell_order = orders['sell']
            if close_price >= sell_order.price:
                # Calculate fill quantity (limited by auction volume)
                fill_qty = self.get_max_fill_quantity(security, sell_order.quantity)
                if fill_qty > 0:
                    # Sell order executed (possibly partial)
                    trade = self._execute_auction_trade(
                        security, sell_order, close_price, timestamp, fill_qty
                    )
                    executed_trades.append(trade)
                    
                    # Create exit order for next day
                    self._create_exit_order(security, trade, timestamp)
        
        self.closing_price_processed[security] = True
        return executed_trades
    
    def _execute_auction_trade(self, security: str, order: AuctionOrder,
                               execution_price: float, timestamp: datetime,
                               fill_quantity: int = None) -> Trade:
        """Execute an auction order (possibly partial fill)."""
        # Use fill_quantity if provided, otherwise full order quantity
        qty = fill_quantity if fill_quantity is not None else order.quantity
        
        # Update position and entry price
        if order.side == 'buy':
            self.position[security] = self.position.get(security, 0) + qty
            self.entry_price[security] = execution_price
        else:
            self.position[security] = self.position.get(security, 0) - qty
            self.entry_price[security] = execution_price
        
        trade = Trade(
            timestamp=timestamp,
            side=order.side,
            price=execution_price,
            quantity=qty,
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
        
        # Round to appropriate tick size based on price and exchange
        tick_size = self.get_tick_size(security, exit_price)
        exit_price = self.round_to_tick(exit_price, tick_size)
        
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
    
    def flatten_position_at_close(self, security: str, close_price: float, 
                                   timestamp: datetime) -> Optional[Trade]:
        """
        Flatten any remaining position at the closing price.
        
        Called at end of day if exit order hasn't fully filled.
        This ensures we don't carry positions overnight beyond one day.
        
        Only flattens exit orders whose target_date is TODAY (meaning they
        were created yesterday). Newly created exit orders (target_date = tomorrow)
        should not be flattened yet - they need a chance to fill tomorrow.
        
        Args:
            security: Security symbol
            close_price: Closing auction price
            timestamp: Timestamp of closing
            
        Returns:
            Trade if position was flattened, None otherwise
        """
        # Check if we have a pending exit order with remaining quantity
        if security not in self.exit_orders:
            return None
        
        exit_order = self.exit_orders[security]
        if exit_order.remaining_qty <= 0:
            return None
        
        # Only flatten exit orders that were targeted for TODAY
        # If target_date is in the future (tomorrow), this is a newly created
        # exit order that should have a chance to fill tomorrow
        if exit_order.target_date > timestamp.date():
            return None
        
        # Flatten the remaining position at closing price
        fill_qty = exit_order.remaining_qty
        
        # Calculate P&L
        if exit_order.side == 'sell':
            # We're selling what we bought
            realized_pnl = (close_price - exit_order.entry_price) * fill_qty
            self.position[security] -= fill_qty
        else:
            # We're buying back what we sold short
            realized_pnl = (exit_order.entry_price - close_price) * fill_qty
            self.position[security] += fill_qty
        
        self.pnl[security] = self.pnl.get(security, 0) + realized_pnl
        
        trade = Trade(
            timestamp=timestamp,
            side=exit_order.side,
            price=close_price,
            quantity=fill_qty,
            realized_pnl=realized_pnl,
            trade_type='eod_flatten',
            vwap_reference=exit_order.price
        )
        self.trades[security].append(trade)
        
        # Remove the exit order
        del self.exit_orders[security]
        
        return trade
    
    def get_strategy_name(self) -> str:
        return "closing_strategy"
    
    def get_summary(self, security: str) -> dict:
        """Get summary statistics for a security."""
        trades = self.trades.get(security, [])
        
        # Count buy vs sell entries
        buy_entries = len([t for t in trades if t.trade_type == 'auction_entry' and t.side == 'buy'])
        sell_entries = len([t for t in trades if t.trade_type == 'auction_entry' and t.side == 'sell'])
        
        return {
            'security': security,
            'total_trades': len(trades),
            'auction_entries': len([t for t in trades if t.trade_type == 'auction_entry']),
            'buy_entries': buy_entries,
            'sell_entries': sell_entries,
            'vwap_exits': len([t for t in trades if t.trade_type == 'vwap_exit']),
            'stop_losses': len([t for t in trades if t.trade_type == 'stop_loss']),
            'eod_flattens': len([t for t in trades if t.trade_type == 'eod_flatten']),
            'filtered_sell_entries': self.filtered_sell_entries.get(security, 0),
            'filtered_buy_entries': self.filtered_buy_entries.get(security, 0),
            'realized_pnl': self.pnl.get(security, 0),
            'final_position': self.position.get(security, 0),
        }
