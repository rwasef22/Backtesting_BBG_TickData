import sys
sys.path.insert(0, '.')
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook
from src.market_making_strategy import MarketMakingStrategy
from src.config_loader import load_strategy_config
import pandas as pd

print("Diagnostic: Testing quote generation...")

mm_config = load_strategy_config('configs/mm_config.json')
strategy = MarketMakingStrategy(config=mm_config)
security = 'EMAAR'
strategy.initialize_security(security)

# Simulate processing a few market updates
ob = OrderBook()

# Add some book levels
ob.apply_update({'timestamp': pd.Timestamp('2025-05-20 10:00:00'), 'type': 'bid', 'price': 13.0, 'volume': 10000})
ob.apply_update({'timestamp': pd.Timestamp('2025-05-20 10:00:00'), 'type': 'ask', 'price': 13.1, 'volume': 10000})

best_bid = ob.get_best_bid()
best_ask = ob.get_best_ask()

print(f"Best bid: {best_bid}")
print(f"Best ask: {best_ask}")
print(f"Position: {strategy.position[security]}")

# Try to generate quotes
quotes = strategy.generate_quotes(security, best_bid, best_ask)
print(f"\nGenerated quotes: {quotes}")

if quotes:
    cfg = strategy.get_config(security)
    print(f"\nConfig:")
    print(f"  quote_size_bid: {cfg['quote_size_bid']}")
    print(f"  quote_size_ask: {cfg['quote_size_ask']}")
    print(f"  max_position: {cfg['max_position']}")
    print(f"  min_local_currency_before_quote: {cfg['min_local_currency_before_quote']}")
    
    # Check liquidity threshold
    bid_price = quotes['bid_price']
    bid_size = quotes['bid_size']
    ask_price = quotes['ask_price']
    ask_size = quotes['ask_size']
    
    bid_ahead = ob.bids.get(bid_price, 0)
    ask_ahead = ob.asks.get(ask_price, 0)
    
    bid_local = bid_price * bid_ahead if bid_price else 0
    ask_local = ask_price * ask_ahead if ask_price else 0
    
    threshold = cfg['min_local_currency_before_quote']
    
    print(f"\nLiquidity check:")
    print(f"  Bid: price={bid_price}, size={bid_size}, ahead={bid_ahead}, local_value={bid_local:.0f}, threshold={threshold}, OK={bid_local >= threshold and bid_size > 0}")
    print(f"  Ask: price={ask_price}, size={ask_size}, ahead={ask_ahead}, local_value={ask_local:.0f}, threshold={threshold}, OK={ask_local >= threshold and ask_size > 0}")
