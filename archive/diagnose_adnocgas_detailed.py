"""Detailed diagnostic for ADNOCGAS - trace strategy logic on non-trading days."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.market_making_backtest import MarketMakingBacktest
from src.mm_handler import create_mm_handler
from src.config_loader import load_strategy_config
from collections import defaultdict
from datetime import datetime

# Load config
mm_config = load_strategy_config('configs/mm_config.json')

# Diagnostic logging per day
daily_diagnostics = defaultdict(lambda: {
    'total_rows': 0,
    'valid_trading_window_rows': 0,
    'best_bid_available': 0,
    'best_ask_available': 0,
    'both_available': 0,
    'generate_quotes_called': 0,
    'generate_quotes_returned_none': 0,
    'quotes_generated': 0,
    'bid_should_refill': 0,
    'ask_should_refill': 0,
    'bid_liquidity_ok': 0,
    'ask_liquidity_ok': 0,
    'bid_liquidity_fail': 0,
    'ask_liquidity_fail': 0,
    'bid_quotes_placed': 0,
    'ask_quotes_placed': 0,
    'trades_processed': 0,
    'sample_bid_values': [],
    'sample_ask_values': [],
    'sample_timestamps': []
})

# Wrap the original handler
original_handler = create_mm_handler(config=mm_config)

def diagnostic_handler(security, df, orderbook, state):
    """Handler with detailed logging for ADNOCGAS."""
    if security != 'ADNOCGAS':
        return original_handler(security, df, orderbook, state)
    
    # Get strategy from closure
    import src.mm_handler as mm_module
    strategy = None
    for key, value in mm_module.__dict__.items():
        if hasattr(value, 'position'):
            strategy = value
            break
    
    if strategy is None:
        return original_handler(security, df, orderbook, state)
    
    # Initialize state if needed
    if 'rows' not in state:
        state['rows'] = 0
        state['bid_count'] = 0
        state['ask_count'] = 0
        state['trade_count'] = 0
        state['trades'] = []
        state['position'] = 0
        state['pnl'] = 0.0
        state['last_price'] = None
        state['closed_at_eod'] = False
        state['last_flatten_date'] = None
        state['market_dates'] = set()
        state['strategy_dates'] = set()
        state['last_date'] = None
    
    strategy.initialize_security(security)
    
    # Process each row with diagnostics
    for row in df.itertuples(index=False):
        timestamp = row.timestamp
        event_type = row.type
        price = row.price
        volume = row.volume
        
        current_date = timestamp.date()
        
        # Clear orderbook if new trading day
        if state.get('last_date') is not None and state['last_date'] != current_date:
            orderbook.bids.clear()
            orderbook.asks.clear()
            orderbook.last_trade = None
            if security in strategy.last_refill_time:
                strategy.last_refill_time[security] = {'bid': None, 'ask': None}
        state['last_date'] = current_date
        
        daily_diagnostics[current_date]['total_rows'] += 1
        
        # Track market trade dates
        if event_type == 'trade':
            state['market_dates'].add(current_date)
        
        if state.get('last_flatten_date') is not None and state['last_flatten_date'] != current_date:
            state['closed_at_eod'] = False
        
        # EOD flatten
        if strategy.is_eod_close_time(timestamp) and not state['closed_at_eod']:
            if strategy.position[security] != 0:
                close_price = price if price is not None else state.get('last_price', price)
                strategy.flatten_position(security, close_price, timestamp)
            state['closed_at_eod'] = True
            state['last_flatten_date'] = current_date
            state['trades'] = strategy.trades[security]
            continue
        
        # Check time windows
        is_opening_auction = strategy.is_in_opening_auction(timestamp)
        
        if strategy.is_in_silent_period(timestamp):
            continue
        
        if strategy.is_in_closing_auction(timestamp):
            continue
        
        # Valid trading window
        daily_diagnostics[current_date]['valid_trading_window_rows'] += 1
        
        # Apply orderbook update
        orderbook.apply_update({
            'timestamp': timestamp,
            'type': event_type,
            'price': price,
            'volume': volume
        })
        
        state['rows'] += 1
        if event_type == 'bid':
            state['bid_count'] += 1
        elif event_type == 'ask':
            state['ask_count'] += 1
        elif event_type == 'trade':
            state['trade_count'] += 1
            state['last_price'] = price
        
        # === DIAGNOSTIC LOGGING ===
        best_bid = orderbook.get_best_bid()
        best_ask = orderbook.get_best_ask()
        
        if best_bid is not None:
            daily_diagnostics[current_date]['best_bid_available'] += 1
        if best_ask is not None:
            daily_diagnostics[current_date]['best_ask_available'] += 1
        if best_bid is not None and best_ask is not None:
            daily_diagnostics[current_date]['both_available'] += 1
            
            # Sample first few for inspection
            if len(daily_diagnostics[current_date]['sample_timestamps']) < 5:
                daily_diagnostics[current_date]['sample_timestamps'].append(timestamp.time())
                bid_value = best_bid[0] * best_bid[1]
                ask_value = best_ask[0] * best_ask[1]
                daily_diagnostics[current_date]['sample_bid_values'].append(bid_value)
                daily_diagnostics[current_date]['sample_ask_values'].append(ask_value)
        
        # Generate quotes
        quotes = strategy.generate_quotes(security, best_bid, best_ask)
        daily_diagnostics[current_date]['generate_quotes_called'] += 1
        
        if quotes is None:
            daily_diagnostics[current_date]['generate_quotes_returned_none'] += 1
            continue
        
        daily_diagnostics[current_date]['quotes_generated'] += 1
        
        if quotes:
            strategy.active_orders.setdefault(security, {'bid': {'price': None, 'ahead_qty': 0, 'our_remaining': 0},
                                                       'ask': {'price': None, 'ahead_qty': 0, 'our_remaining': 0}})
            strategy.quote_prices.setdefault(security, {'bid': None, 'ask': None})
            
            cfg = strategy.get_config(security)
            threshold = cfg.get('min_local_currency_before_quote', 25000)
            
            # BID side
            if best_bid is not None and strategy.should_refill_side(security, timestamp, 'bid'):
                daily_diagnostics[current_date]['bid_should_refill'] += 1
                
                bid_price = quotes['bid_price']
                bid_size = quotes['bid_size']
                bid_ahead = orderbook.bids.get(bid_price, 0) if bid_price is not None else 0
                bid_local = (bid_price * bid_ahead) if bid_price is not None else 0
                bid_ok = bid_local >= threshold and bid_size > 0
                
                strategy.set_refill_time(security, 'bid', timestamp)
                
                if bid_ok:
                    daily_diagnostics[current_date]['bid_liquidity_ok'] += 1
                    daily_diagnostics[current_date]['bid_quotes_placed'] += 1
                    strategy.active_orders[security]['bid'] = {
                        'price': bid_price,
                        'ahead_qty': int(bid_ahead),
                        'our_remaining': int(bid_size)
                    }
                    strategy.quote_prices[security]['bid'] = bid_price
                else:
                    daily_diagnostics[current_date]['bid_liquidity_fail'] += 1
                    strategy.active_orders[security]['bid'] = {
                        'price': bid_price,
                        'ahead_qty': int(bid_ahead),
                        'our_remaining': 0
                    }
                    strategy.quote_prices[security]['bid'] = None
            
            # ASK side
            if best_ask is not None and strategy.should_refill_side(security, timestamp, 'ask'):
                daily_diagnostics[current_date]['ask_should_refill'] += 1
                
                ask_price = quotes['ask_price']
                ask_size = quotes['ask_size']
                ask_ahead = orderbook.asks.get(ask_price, 0) if ask_price is not None else 0
                ask_local = (ask_price * ask_ahead) if ask_price is not None else 0
                ask_ok = ask_local >= threshold and ask_size > 0
                
                strategy.set_refill_time(security, 'ask', timestamp)
                
                if ask_ok:
                    daily_diagnostics[current_date]['ask_liquidity_ok'] += 1
                    daily_diagnostics[current_date]['ask_quotes_placed'] += 1
                    strategy.active_orders[security]['ask'] = {
                        'price': ask_price,
                        'ahead_qty': int(ask_ahead),
                        'our_remaining': int(ask_size)
                    }
                    strategy.quote_prices[security]['ask'] = ask_price
                else:
                    daily_diagnostics[current_date]['ask_liquidity_fail'] += 1
                    strategy.active_orders[security]['ask'] = {
                        'price': ask_price,
                        'ahead_qty': int(ask_ahead),
                        'our_remaining': 0
                    }
                    strategy.quote_prices[security]['ask'] = None
        
        # Process trade
        if event_type == 'trade' and not is_opening_auction:
            strategy.process_trade(security, timestamp, price, volume, orderbook=orderbook)
            daily_diagnostics[current_date]['trades_processed'] += 1
    
    # Update state
    state['position'] = strategy.position[security]
    state['pnl'] = strategy.get_total_pnl(security, state.get('last_price'))
    state['trades'] = strategy.trades[security]
    
    for trade in strategy.trades[security]:
        trade_date = trade['timestamp'].date() if hasattr(trade['timestamp'], 'date') else trade['timestamp']
        state['strategy_dates'].add(trade_date)
    
    return state

# Run backtest
print(f"\n{'='*80}")
print("ADNOCGAS Detailed Diagnostic Backtest")
print(f"{'='*80}\n")

backtest = MarketMakingBacktest()
results = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=diagnostic_handler,
    max_sheets=None,
    only_trades=False
)

# Analyze results
print(f"\n{'='*80}")
print("DIAGNOSTIC RESULTS - NON-TRADING DAYS ANALYSIS")
print(f"{'='*80}\n")

adnocgas_result = results.get('ADNOCGAS', {})
strategy_dates = adnocgas_result.get('strategy_dates', set())

# Identify non-trading days
all_dates = sorted(daily_diagnostics.keys())
trading_days = [d for d in all_dates if d in strategy_dates]
non_trading_days = [d for d in all_dates if d not in strategy_dates]

print(f"Total days in data: {len(all_dates)}")
print(f"Trading days: {len(trading_days)}")
print(f"Non-trading days: {len(non_trading_days)}\n")

# Analyze non-trading days
print(f"Detailed analysis of NON-TRADING days:\n")
print(f"{'Date':<12} {'Rows':<6} {'Valid':<6} {'BidAvail':<9} {'AskAvail':<9} {'QuoteCalls':<11} {'QuotesGen':<10} "
      f"{'BidRefill':<10} {'AskRefill':<10} {'BidLiqOK':<9} {'AskLiqOK':<9}")
print("="*140)

for date in non_trading_days[:30]:  # First 30 non-trading days
    diag = daily_diagnostics[date]
    print(f"{date} {diag['total_rows']:>5} {diag['valid_trading_window_rows']:>5} "
          f"{diag['best_bid_available']:>8} {diag['best_ask_available']:>8} "
          f"{diag['generate_quotes_called']:>10} {diag['quotes_generated']:>9} "
          f"{diag['bid_should_refill']:>9} {diag['ask_should_refill']:>9} "
          f"{diag['bid_liquidity_ok']:>8} {diag['ask_liquidity_ok']:>8}")
    
    # Show sample values if available
    if diag['sample_bid_values']:
        avg_bid = sum(diag['sample_bid_values']) / len(diag['sample_bid_values'])
        avg_ask = sum(diag['sample_ask_values']) / len(diag['sample_ask_values'])
        print(f"  → Sample avg bid value: ${avg_bid:,.0f}, ask value: ${avg_ask:,.0f}, threshold: $13,000")

if len(non_trading_days) > 30:
    print(f"\n... and {len(non_trading_days) - 30} more non-trading days")

# Save detailed report
with open('output/adnocgas_detailed_diagnostic.txt', 'w') as f:
    f.write("ADNOCGAS Non-Trading Days Detailed Diagnostic\n")
    f.write("="*80 + "\n\n")
    f.write(f"Total days: {len(all_dates)}\n")
    f.write(f"Trading days: {len(trading_days)}\n")
    f.write(f"Non-trading days: {len(non_trading_days)}\n\n")
    
    for date in non_trading_days:
        diag = daily_diagnostics[date]
        f.write(f"\n{date}:\n")
        f.write(f"  Total rows: {diag['total_rows']}\n")
        f.write(f"  Valid trading window rows: {diag['valid_trading_window_rows']}\n")
        f.write(f"  Best bid available: {diag['best_bid_available']}\n")
        f.write(f"  Best ask available: {diag['best_ask_available']}\n")
        f.write(f"  Both bid & ask available: {diag['both_available']}\n")
        f.write(f"  generate_quotes() called: {diag['generate_quotes_called']}\n")
        f.write(f"  generate_quotes() returned None: {diag['generate_quotes_returned_none']}\n")
        f.write(f"  Quotes generated: {diag['quotes_generated']}\n")
        f.write(f"  Bid should refill: {diag['bid_should_refill']}\n")
        f.write(f"  Ask should refill: {diag['ask_should_refill']}\n")
        f.write(f"  Bid liquidity OK: {diag['bid_liquidity_ok']}\n")
        f.write(f"  Ask liquidity OK: {diag['ask_liquidity_ok']}\n")
        f.write(f"  Bid liquidity FAIL: {diag['bid_liquidity_fail']}\n")
        f.write(f"  Ask liquidity FAIL: {diag['ask_liquidity_fail']}\n")
        f.write(f"  Bid quotes placed: {diag['bid_quotes_placed']}\n")
        f.write(f"  Ask quotes placed: {diag['ask_quotes_placed']}\n")
        f.write(f"  Trades processed: {diag['trades_processed']}\n")
        
        if diag['sample_timestamps']:
            f.write(f"  Sample times: {[str(t) for t in diag['sample_timestamps']]}\n")
            f.write(f"  Sample bid values: {['${:,.0f}'.format(v) for v in diag['sample_bid_values']]}\n")
            f.write(f"  Sample ask values: {['${:,.0f}'.format(v) for v in diag['sample_ask_values']]}\n")

print(f"\n{'='*80}")
print(f"Full diagnostic saved to: output/adnocgas_detailed_diagnostic.txt")
print(f"{'='*80}")
