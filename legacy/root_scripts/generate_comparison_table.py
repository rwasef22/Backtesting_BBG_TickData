import pandas as pd
from pathlib import Path

# Load the saved results
metrics_df = pd.read_csv("output/comprehensive_sweep/comprehensive_results.csv")
print("Loaded metrics:")
print(metrics_df[['strategy', 'interval_sec', 'total_pnl', 'total_trades', 'sharpe_ratio']].to_string())

# Now generate the comparison table
available_strategies = sorted(metrics_df["strategy"].unique())
print(f"\nAvailable strategies: {available_strategies}")

if len(available_strategies) >= 2:
    intervals = sorted(metrics_df["interval_sec"].unique())
    comparison_data = {"Interval (sec)": intervals}
    
    for strategy in available_strategies:
        strat_df = metrics_df[metrics_df["strategy"] == strategy].sort_values("interval_sec")
        
        # Create a complete series aligned with all intervals
        pnl_series = pd.Series(index=intervals, dtype=float)
        trades_series = pd.Series(index=intervals, dtype=int)
        sharpe_series = pd.Series(index=intervals, dtype=float)
        dd_series = pd.Series(index=intervals, dtype=float)
        win_series = pd.Series(index=intervals, dtype=float)
        
        # Fill in available data
        for _, row in strat_df.iterrows():
            interval = row["interval_sec"]
            pnl_series[interval] = row["total_pnl"]
            trades_series[interval] = row["total_trades"]
            sharpe_series[interval] = row["sharpe_ratio"]
            dd_series[interval] = row["max_drawdown_pct"]
            win_series[interval] = row["win_rate"]
        
        def format_strategy_name(s):
            return s.replace("_", ".").upper()
        
        comparison_data[f"{format_strategy_name(strategy)} P&L"] = pnl_series.values
        comparison_data[f"{format_strategy_name(strategy)} Trades"] = trades_series.values
        comparison_data[f"{format_strategy_name(strategy)} Sharpe"] = sharpe_series.values
        comparison_data[f"{format_strategy_name(strategy)} Max DD%"] = dd_series.values
        comparison_data[f"{format_strategy_name(strategy)} Win%"] = win_series.values
    
    comparison = pd.DataFrame(comparison_data)
    print("\n=== Strategy Comparison ===")
    print(comparison.to_string(index=False))
    comparison.to_csv("output/comprehensive_sweep/comparison_table.csv", index=False)
    print("\n✓ Saved comparison_table.csv")
