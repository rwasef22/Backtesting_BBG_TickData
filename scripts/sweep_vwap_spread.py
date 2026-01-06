#!/usr/bin/env python3
"""
Sweep VWAP parameters per security to find optimal values.
Can sweep spread_vwap_pct or vwap_preclose_period_min.
"""

import sys
import os
import json
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.closing_strategy.handler import process_security_closing_strategy


def load_parquet_data(parquet_dir: str) -> dict:
    """Load data from Parquet files."""
    parquet_path = Path(parquet_dir)
    parquet_files = list(parquet_path.glob("*.parquet"))
    
    data = {}
    for pf in parquet_files:
        security = pf.stem.upper()
        df = pd.read_parquet(pf)
        
        # Normalize column names
        col_map = {'Timestamp': 'timestamp', 'Type': 'type', 'Price': 'price', 'Volume': 'volume'}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df = df.sort_values('timestamp').reset_index(drop=True)
        data[security] = df
    
    return data


def load_exchange_mapping(mapping_path: str) -> dict:
    """Load exchange mapping from JSON file."""
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r') as f:
            return json.load(f)
    return {}


def run_single_security_param(args):
    """Run backtest for a single security with specific parameters."""
    security, param_name, param_value, sec_config, df, exchange_mapping, auction_fill_pct = args
    
    # Create config with this parameter value
    config = {security: sec_config.copy()}
    config[security][param_name] = param_value
    
    try:
        result = process_security_closing_strategy(
            security, df, config, exchange_mapping, auction_fill_pct
        )
        
        summary = result.get('summary', {})
        return {
            'security': security,
            'param_value': param_value,
            'pnl': result.get('pnl', 0),
            'trades': summary.get('total_trades', 0),
            'auction_entries': summary.get('auction_entries', 0),
            'vwap_exits': summary.get('vwap_exits', 0),
            'stop_losses': summary.get('stop_losses', 0),
            'eod_flattens': summary.get('eod_flattens', 0),
        }
    except Exception as e:
        print(f"  Error {security} @ {param_value}: {e}")
    
    return {
        'security': security,
        'param_value': param_value,
        'pnl': 0,
        'trades': 0,
        'auction_entries': 0,
        'vwap_exits': 0,
        'stop_losses': 0,
        'eod_flattens': 0,
    }


def main():
    # Configuration - VWAP PRE-CLOSE PERIOD SWEEP
    param_name = 'vwap_preclose_period_min'
    param_values = [15, 30, 45, 60]
    fixed_spread = 0.5  # Keep spread constant at 0.5%
    
    data_dir = Path("data/parquet")
    config_path = Path("configs/closing_strategy_config_1m_cap.json")
    exchange_mapping_path = Path("configs/exchange_mapping.json")
    output_dir = Path("output/vwap_period_sweep_1m_cap")
    auction_fill_pct = 10.0
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load base config
    with open(config_path) as f:
        base_config = json.load(f)
    
    # Load exchange mapping
    exchange_mapping = load_exchange_mapping(str(exchange_mapping_path))
    
    # Load all data once
    print("Loading data...")
    all_data = load_parquet_data(str(data_dir))
    
    securities = list(base_config.keys())
    
    print("=" * 70)
    print(f"VWAP PARAMETER SWEEP: {param_name}")
    print("=" * 70)
    print(f"Securities: {len(securities)}")
    print(f"Parameter values: {param_values}")
    if param_name == 'vwap_preclose_period_min':
        print(f"Fixed spread_vwap_pct: {fixed_spread}%")
    print(f"Total runs: {len(securities) * len(param_values)}")
    print()
    
    # Build task list - pass actual dataframes
    tasks = []
    for security in securities:
        if security in all_data:
            sec_config = base_config[security].copy()
            # Apply fixed spread if sweeping period
            if param_name == 'vwap_preclose_period_min':
                sec_config['spread_vwap_pct'] = fixed_spread
            
            for param_value in param_values:
                tasks.append((
                    security, 
                    param_name,
                    param_value, 
                    sec_config,
                    all_data[security],
                    exchange_mapping,
                    auction_fill_pct
                ))
    
    # Run all combinations in parallel
    results = []
    print("Running sweep...")
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        for i, result in enumerate(executor.map(run_single_security_param, tasks)):
            results.append(result)
            if (i + 1) % 10 == 0:
                print(f"  Completed {i + 1}/{len(tasks)} runs...")
    
    print(f"\nCompleted all {len(tasks)} runs")
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Find optimal parameter per security
    print("\n" + "=" * 70)
    print(f"OPTIMAL {param_name} PER SECURITY (by P&L)")
    print("=" * 70)
    
    optimal_results = []
    
    for security in securities:
        sec_df = df[df['security'] == security]
        best_row = sec_df.loc[sec_df['pnl'].idxmax()]
        
        # Get all results for this security to show comparison
        param_pnl = sec_df.set_index('param_value')['pnl'].to_dict()
        
        result_row = {
            'security': security,
            'optimal_value': best_row['param_value'],
            'best_pnl': best_row['pnl'],
            'best_trades': best_row['trades'],
        }
        # Add P&L for each parameter value
        for pv in param_values:
            result_row[f'pnl_{pv}'] = param_pnl.get(pv, 0)
        
        optimal_results.append(result_row)
        
        print(f"\n{security}:")
        print(f"  Optimal {param_name}: {best_row['param_value']} -> P&L: {best_row['pnl']:,.2f} AED")
        for pv in param_values:
            pnl = param_pnl.get(pv, 0)
            marker = " <-- BEST" if pv == best_row['param_value'] else ""
            print(f"    {pv}: {pnl:>12,.2f} AED{marker}")
    
    # Create summary DataFrames
    optimal_df = pd.DataFrame(optimal_results)
    
    # Save results
    df.to_csv(output_dir / "sweep_all_results.csv", index=False)
    optimal_df.to_csv(output_dir / "optimal_per_security.csv", index=False)
    
    # Create optimal config
    optimal_config = {}
    for row in optimal_results:
        security = row['security']
        optimal_config[security] = base_config[security].copy()
        optimal_config[security][param_name] = row['optimal_value']
        if param_name == 'vwap_preclose_period_min':
            optimal_config[security]['spread_vwap_pct'] = fixed_spread
    
    with open(output_dir / "closing_strategy_config_optimal.json", 'w') as f:
        json.dump(optimal_config, f, indent=2)
    
    # Print summary table
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    
    # Build header
    header = f"{'Security':<12} {'Optimal':<8}"
    for pv in param_values:
        header += f" {'P&L ' + str(pv):>12}"
    print(f"\n{header}")
    print("-" * (24 + 13 * len(param_values)))
    
    total_by_param = {pv: 0 for pv in param_values}
    total_optimal = 0
    
    for row in optimal_results:
        line = f"{row['security']:<12} {row['optimal_value']:<8}"
        for pv in param_values:
            line += f" {row[f'pnl_{pv}']:>12,.0f}"
            total_by_param[pv] += row[f'pnl_{pv}']
        print(line)
        total_optimal += row['best_pnl']
    
    print("-" * (24 + 13 * len(param_values)))
    totals_line = f"{'TOTAL':<12} {'Mixed':<8}"
    for pv in param_values:
        totals_line += f" {total_by_param[pv]:>12,.0f}"
    print(totals_line)
    print(f"{'OPTIMAL':<12} {'Best/Sec':<8} {total_optimal:>12,.0f} (using best {param_name} per security)")
    
    # Find single best uniform parameter
    best_uniform = max(total_by_param, key=total_by_param.get)
    print(f"\nBest UNIFORM {param_name}: {best_uniform} -> Total P&L: {total_by_param[best_uniform]:,.0f} AED")
    print(f"OPTIMAL (per-security): Total P&L: {total_optimal:,.0f} AED")
    if total_by_param[best_uniform] > 0:
        print(f"Improvement over uniform: {total_optimal - total_by_param[best_uniform]:,.0f} AED "
              f"({(total_optimal / total_by_param[best_uniform] - 1) * 100:.1f}%)")
    
    print(f"\nResults saved to: {output_dir}")
    print(f"  - sweep_all_results.csv (all {len(df)} runs)")
    print(f"  - optimal_per_security.csv (summary)")
    print(f"  - closing_strategy_config_optimal.json (optimized config)")


if __name__ == "__main__":
    main()