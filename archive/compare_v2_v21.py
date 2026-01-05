"""Compare V2 baseline with V2.1 Stop Loss for EMAAR."""
import pandas as pd

print("=" * 80)
print("V2 vs V2.1 STOP LOSS COMPARISON (EMAAR)")
print("=" * 80)
print()

# Load V2 baseline (30s interval from comprehensive sweep)
v2_df = pd.read_csv('output/comprehensive_sweep/v2_30s/EMAAR_trades.csv')

# V2.1 results from test (just ran)
v21_pnl = 388737.05
v21_trades = 18646
v21_stop_loss_count = 140

# V2 metrics
v2_pnl = v2_df['pnl'].iloc[-1]
v2_trades = len(v2_df)
v2_buys = (v2_df['side'] == 'buy').sum()
v2_sells = (v2_df['side'] == 'sell').sum()

# V2.1 metrics (from test output)
v21_buys = 9559
v21_sells = 9087

# Calculate differences
pnl_diff = v21_pnl - v2_pnl
pnl_diff_pct = (pnl_diff / v2_pnl * 100) if v2_pnl != 0 else 0
trade_diff = v21_trades - v2_trades
trade_diff_pct = (trade_diff / v2_trades * 100) if v2_trades != 0 else 0

print(f"{'Metric':<30} {'V2 Baseline':>15} {'V2.1 Stop Loss':>18} {'Difference':>15}")
print("-" * 80)
print(f"{'Total P&L (AED)':<30} {v2_pnl:>15,.2f} {v21_pnl:>18,.2f} {pnl_diff:>15,.2f} ({pnl_diff_pct:+.1f}%)")
print(f"{'Total Trades':<30} {v2_trades:>15,} {v21_trades:>18,} {trade_diff:>15,} ({trade_diff_pct:+.1f}%)")
print(f"{'Buy Trades':<30} {v2_buys:>15,} {v21_buys:>18,}")
print(f"{'Sell Trades':<30} {v2_sells:>15,} {v21_sells:>18,}")
print(f"{'Stop Loss Triggers':<30} {'N/A':>15} {v21_stop_loss_count:>18,} {'-':>15}")
print(f"{'Avg P&L per Trade (AED)':<30} {v2_pnl/v2_trades:>15,.2f} {v21_pnl/v21_trades:>18,.2f}")
print()

# Analyze drawdowns
v2_df['cumulative_pnl'] = v2_df['pnl']
v2_df['running_max'] = v2_df['cumulative_pnl'].expanding().max()
v2_df['drawdown'] = v2_df['cumulative_pnl'] - v2_df['running_max']
v2_max_dd = v2_df['drawdown'].min()
v2_max_dd_pct = (v2_max_dd / v2_df['running_max'].max() * 100) if v2_df['running_max'].max() != 0 else 0

print("RISK METRICS")
print("-" * 80)
print(f"{'Max Drawdown (AED)':<30} {v2_max_dd:>15,.2f} {'TBD':>18} {'-':>15}")
print(f"{'Max Drawdown (%)':<30} {v2_max_dd_pct:>15,.2f} {'TBD':>18} {'-':>15}")
print()

print("=" * 80)
print("INTERPRETATION")
print("=" * 80)
if abs(pnl_diff_pct) < 5:
    print(f"✅ V2.1 P&L within 5% of V2 baseline ({pnl_diff_pct:+.1f}%)")
    print("   Stop loss protection with minimal impact on profitability")
elif pnl_diff_pct > 0:
    print(f"✅ V2.1 P&L HIGHER than V2 baseline by {pnl_diff_pct:.1f}%")
    print("   Stop loss may have prevented larger losing positions")
else:
    print(f"⚠️  V2.1 P&L LOWER than V2 baseline by {abs(pnl_diff_pct):.1f}%")
    print("   Stop loss cost: {abs(pnl_diff):,.2f} AED")
    print("   Consider adjusting threshold or analyzing stop loss triggers")

print()
print(f"Stop Loss Activity: {v21_stop_loss_count} triggers ({v21_stop_loss_count/v21_trades*100:.2f}% of trades)")
print()
