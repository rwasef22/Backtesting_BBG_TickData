"""Minimal OrderBook for streaming backtest."""
from typing import Optional, Tuple


class OrderBook:
    def __init__(self):
        # price -> quantity
        self.bids = {}
        self.asks = {}
        self.last_trade = None

    def set_bid(self, price: float, quantity: float):
        if quantity <= 0:
            self.bids.pop(price, None)
        else:
            self.bids[price] = quantity

    def set_ask(self, price: float, quantity: float):
        if quantity <= 0:
            self.asks.pop(price, None)
        else:
            self.asks[price] = quantity

    def remove_bid(self, price: float, quantity: float):
        if price in self.bids:
            if self.bids[price] <= quantity:
                del self.bids[price]
            else:
                self.bids[price] -= quantity

    def remove_ask(self, price: float, quantity: float):
        if price in self.asks:
            if self.asks[price] <= quantity:
                del self.asks[price]
            else:
                self.asks[price] -= quantity

    def get_best_bid(self) -> Optional[Tuple[float, float]]:
        if not self.bids:
            return None
        # Filter out any invalid prices that may have slipped through
        valid_bids = {p: q for p, q in self.bids.items() if p > 0}
        if not valid_bids:
            return None
        price = max(valid_bids.keys())
        return price, valid_bids[price]

    def get_best_ask(self) -> Optional[Tuple[float, float]]:
        if not self.asks:
            return None
        # Filter out any invalid prices that may have slipped through
        valid_asks = {p: q for p, q in self.asks.items() if p > 0}
        if not valid_asks:
            return None
        price = min(valid_asks.keys())
        return price, valid_asks[price]

    def apply_update(self, update: dict):
        """Apply a market update: dict with keys 'timestamp','type','price','volume'."""
        utype = update.get('type')
        price = update.get('price')
        vol = update.get('volume', 0)
        if utype is None:
            return
        
        # Skip invalid prices
        if price is None or price <= 0:
            return

        t = str(utype).lower()
        if t == 'bid':
            self.set_bid(price, vol)
        elif t == 'ask':
            self.set_ask(price, vol)
        elif t == 'trade':
            self.last_trade = {'timestamp': update.get('timestamp'), 'price': price, 'volume': vol}

    def __str__(self):
        return f"Bids: {len(self.bids)} levels, Asks: {len(self.asks)} levels, Last trade: {self.last_trade}"
class OrderBook:
    def __init__(self):
        # price -> quantity
        self.bids = {}
        self.asks = {}
        self.last_trade = None

    def set_bid(self, price, quantity):
        if price is None or price <= 0:
            return
        if quantity <= 0:
            self.bids.pop(price, None)
        else:
            self.bids[price] = quantity

    def set_ask(self, price, quantity):
        if price is None or price <= 0:
            return
        if quantity <= 0:
            self.asks.pop(price, None)
        else:
            self.asks[price] = quantity

    def remove_bid(self, price, quantity):
        if price in self.bids:
            if self.bids[price] <= quantity:
                del self.bids[price]
            else:
                self.bids[price] -= quantity

    def remove_ask(self, price, quantity):
        if price in self.asks:
            if self.asks[price] <= quantity:
                del self.asks[price]
            else:
                self.asks[price] -= quantity

    def get_best_bid(self):
        if not self.bids:
            return None
        price = max(self.bids.keys())
        return (price, self.bids[price])

    def get_best_ask(self):
        if not self.asks:
            return None
        price = min(self.asks.keys())
        return (price, self.asks[price])

    def apply_update(self, update):
        """Apply a single update row (dict-like with keys 'timestamp','price','volume','type').

        - For 'bid'/'ask' updates: set the level to the provided volume (0 means remove)
        - For 'trade': record last_trade as a dict
        """
        utype = update.get('type')
        price = update.get('price')
        vol = update.get('volume', 0)

        if utype == 'bid':
            self.set_bid(price, vol)
        elif utype == 'ask':
            self.set_ask(price, vol)
        elif utype == 'trade':
            self.last_trade = {'timestamp': update.get('timestamp'), 'price': price, 'volume': vol}

    def __str__(self):
        return f"Bids: {self.bids}, Asks: {self.asks}, Last trade: {self.last_trade}"