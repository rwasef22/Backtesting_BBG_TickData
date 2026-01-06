"""
Closing Strategy Module

A closing auction arbitrage strategy that:
1. Calculates VWAP during pre-close period
2. Places buy/sell orders at auction with spread around VWAP
3. Exits positions the next day at VWAP price
"""

from .strategy import ClosingStrategy
from .handler import create_closing_strategy_handler

__all__ = ['ClosingStrategy', 'create_closing_strategy_handler']
