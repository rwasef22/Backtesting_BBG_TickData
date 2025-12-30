"""Minimal test to see why v2 generates no quotes"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.config_loader import load_strategy_config
from src.strategies.v2_price_follow_qty_cooldown.strategy import V2PriceFollowQtyCooldownStrategy
from src.orderbook import OrderBook
from datetime import datetime

# Load config
config = load_strategy_config('configs/mm_config.json')

# Create strategy
strategy = V2PriceFollowQtyCooldownStrategy(config=config)
strategy.initialize_security('EMAAR')

print("="*80)
print("V2 STRATEGY QUOTE GENERATION TEST")
print("="*80)

# Create orderbook
orderbook = OrderBook()

# Simulate a BID update
orderbook.set_bid(12.00, 100000)
orderbook.set_ask(12.15, 50000)

print("\nOrderbook after updates:")
print(f"  Best bid: {orderbook.get_best_bid()}")
print(f"  Best ask: {orderbook.get_best_ask()}")

# Try to generate quotes
timestamp = datetime(2025, 4, 14, 10, 30, 0)
best_bid = orderbook.get_best_bid()
best_ask = orderbook.get_best_ask()

print(f"\nGenerating quotes at {timestamp}...")
quotes = strategy.generate_quotes('EMAAR', best_bid, best_ask, timestamp)

print(f"\nQuotes generated:")
print(f"  {quotes}")

if quotes:
    bid_price = quotes['bid_price']
    bid_size = quotes['bid_size']
    ask_price = quotes['ask_price']
    ask_size = quotes['ask_size']
    
    print(f"\nBid quote: {bid_size} @ {bid_price}")
    print(f"Ask quote: {ask_size} @ {ask_price}")
    
    # Check liquidity
    cfg = config.get('EMAAR', {})
    threshold = cfg.get('min_local_currency_before_quote', 6460)
    
    bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price else 0
    bid_local = bid_price * bid_ahead if bid_price and bid_ahead > 0 else 0
    bid_ok = bid_local >= threshold and bid_size > 0
    
    ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price else 0
    ask_local = ask_price * ask_ahead if ask_price and ask_ahead > 0 else 0
    ask_ok = ask_local >= threshold and ask_size > 0
    
    print(f"\nBid liquidity check:")
    print(f"  ahead_qty: {bid_ahead}")
    print(f"  local_value: {bid_local:,.2f}")
    print(f"  threshold: {threshold:,.2f}")
    print(f"  bid_ok: {bid_ok}")
    
    print(f"\nAsk liquidity check:")
    print(f"  ahead_qty: {ask_ahead}")
    print(f"  local_value: {ask_local:,.2f}")
    print(f"  threshold: {threshold:,.2f}")
    print(f"  ask_ok: {ask_ok}")
else:
    print("  ERROR: No quotes generated!")
