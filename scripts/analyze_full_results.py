"""Analyze full backtest results and provide summary statistics."""

import pandas as pd
from pathlib import Path

def analyze_results():
    """Load and analyze backtest summary results."""
    
    summary_file = Path('output/backtest_summary.csv')
    
    if not summary_file.exists():
        print("ERROR: backtest_summary.csv not found!")
        print("Please run the backtest first.")
        return
    
    df = pd.read_csv(summary_file)
    
    print("=" * 80)
    print("FULL BACKTEST RESULTS ANALYSIS")
    print("=" * 80)
    print()
    
    # Overall statistics
    total_trades = df['trades'].sum()
    total_pnl = df['realized_pnl'].sum()
    successful_securities = len(df[df['trades'] > 0])
    failed_securities = len(df[df['error'].notna()]) if 'error' in df.columns else 0
    
    print(f"Total Securities: {len(df)}")
    print(f"Successful: {successful_securities}")
    print(f"Failed: {failed_securities}")
    print()
    print(f"Total Trades: {total_trades:,}")
    print(f"Total Realized P&L: {total_pnl:,.2f} AED")
    print()
    
    # Per-security breakdown
    print("Per-Security Results:")
    print("-" * 80)
    print(f"{'Security':<15} {'Trades':>10} {'P&L (AED)':>15} {'Position':>10} {'Days':>8}")
    print("-" * 80)
    
    for _, row in df.iterrows():
        if row['trades'] > 0:
            print(f"{row['security']:<15} {row['trades']:>10,} {row['realized_pnl']:>15,.2f} "
                  f"{row['position']:>10,.0f} {row['market_dates']:>8}")
    
    print("-" * 80)
    print(f"{'TOTAL':<15} {total_trades:>10,} {total_pnl:>15,.2f}")
    print("=" * 80)
    
    # Check for errors
    if 'error' in df.columns:
        errors = df[df['error'].notna()]
        if len(errors) > 0:
            print()
            print("ERRORS DETECTED:")
            print("-" * 80)
            for _, row in errors.iterrows():
                print(f"{row['security']}: {row['error']}")
            print("=" * 80)
    
    # Statistics
    if total_trades > 0:
        print()
        print("PERFORMANCE STATISTICS:")
        print("-" * 80)
        print(f"Average Trades per Security: {total_trades / successful_securities:,.1f}")
        print(f"Average P&L per Security: {total_pnl / successful_securities:,.2f} AED")
        print(f"Average P&L per Trade: {total_pnl / total_trades:,.2f} AED")
        
        # Best/worst performers
        if len(df[df['trades'] > 0]) > 0:
            print()
            best_pnl = df.loc[df['realized_pnl'].idxmax()]
            worst_pnl = df.loc[df['realized_pnl'].idxmin()]
            most_trades = df.loc[df['trades'].idxmax()]
            
            print(f"Best P&L: {best_pnl['security']} ({best_pnl['realized_pnl']:,.2f} AED)")
            print(f"Worst P&L: {worst_pnl['security']} ({worst_pnl['realized_pnl']:,.2f} AED)")
            print(f"Most Trades: {most_trades['security']} ({most_trades['trades']:,} trades)")
        
        print("=" * 80)

if __name__ == '__main__':
    analyze_results()
