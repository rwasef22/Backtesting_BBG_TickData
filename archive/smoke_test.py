"""Quick smoke test of the streaming backtest."""
import sys
sys.path.insert(0, '.')

from src.market_making_backtest import MarketMakingBacktest

print("Running smoke test on sample TickData...\n")

backtest = MarketMakingBacktest()
results = backtest.run_streaming('data/raw/TickData_Sample.xlsx', chunk_size=1000, only_trades=False)

print("Backtest Results:")
for sec, state in results.items():
    rows = state.get('rows', 0)
    bids = state.get('bid_count', 0)
    asks = state.get('ask_count', 0)
    trades = state.get('trade_count', 0)
    last_price = state.get('last_price', 'N/A')
    print(f"  {sec:30} | Rows: {rows:>8,} | Bids: {bids:>6,} | Asks: {asks:>6,} | Trades: {trades:>6,} | Last price: {last_price}")

print("\n✓ Smoke test completed successfully!")
