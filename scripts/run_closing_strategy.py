#!/usr/bin/env python
"""
Run Closing Strategy Backtest

A closing auction arbitrage strategy that:
1. Calculates VWAP during pre-close period (default: 14:30-14:45)
2. Places buy/sell orders at auction (14:45) with spread around VWAP
3. Executes at closing auction if price crosses order price
4. Exits positions the next day at VWAP price
5. Stop-loss protection (default: 2%) exits at best opposite price
6. SELL entry trend filter (default: enabled) skips SELL in uptrends >10 bps/hr

Usage:
    # Full backtest using Parquet data
    python scripts/run_closing_strategy.py
    
    # Quick test with 5 securities
    python scripts/run_closing_strategy.py --max-sheets 5
    
    # Custom spread
    python scripts/run_closing_strategy.py --spread 0.3
    
    # Custom VWAP period
    python scripts/run_closing_strategy.py --vwap-period 20
    
    # Custom stop-loss threshold
    python scripts/run_closing_strategy.py --stop-loss 3.0
    
    # Disable trend filter for SELL entries
    python scripts/run_closing_strategy.py --no-trend-filter
    
    # Custom trend filter threshold (bps/hour)
    python scripts/run_closing_strategy.py --trend-threshold 15.0

Output:
    output/closing_strategy/
    ├── {security}_trades.csv    # Per-security trade log
    └── backtest_summary.csv     # Aggregate metrics
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.closing_strategy.strategy import ClosingStrategy
from src.closing_strategy.handler import process_security_closing_strategy


def load_parquet_data(parquet_dir: str, max_sheets: int = None) -> dict:
    """Load data from Parquet files."""
    parquet_path = Path(parquet_dir)
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Parquet directory not found: {parquet_dir}\n"
            "Run: python scripts/convert_excel_to_parquet.py"
        )
    
    parquet_files = list(parquet_path.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in {parquet_dir}")
    
    if max_sheets:
        parquet_files = parquet_files[:max_sheets]
    
    data = {}
    for pf in parquet_files:
        security = pf.stem.upper()
        df = pd.read_parquet(pf)
        
        # Ensure timestamp column
        if 'timestamp' not in df.columns and 'Timestamp' in df.columns:
            df = df.rename(columns={'Timestamp': 'timestamp'})
        if 'type' not in df.columns and 'Type' in df.columns:
            df = df.rename(columns={'Type': 'type'})
        if 'price' not in df.columns and 'Price' in df.columns:
            df = df.rename(columns={'Price': 'price'})
        if 'volume' not in df.columns and 'Volume' in df.columns:
            df = df.rename(columns={'Volume': 'volume'})
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        data[security] = df
    
    return data


def load_exchange_mapping(mapping_path: str) -> dict:
    """
    Load exchange mapping from JSON file.
    
    The mapping file should map security names to exchange codes:
    {"EMAAR": "DFM", "ADCB": "ADX", ...}
    
    Args:
        mapping_path: Path to exchange mapping JSON file
        
    Returns:
        Dict mapping security -> exchange (ADX or DFM)
    """
    if not os.path.exists(mapping_path):
        print(f"Warning: Exchange mapping file not found at {mapping_path}")
        print("Using default exchange (ADX) for all securities")
        return {}
    
    with open(mapping_path, 'r') as f:
        return json.load(f)


def process_security_wrapper(args):
    """Wrapper for parallel processing."""
    security, df, config, exchange_mapping, auction_fill_pct = args
    try:
        result = process_security_closing_strategy(security, df, config, exchange_mapping, auction_fill_pct)
        return result
    except Exception as e:
        return {
            'security': security,
            'error': str(e),
            'trades': [],
            'pnl': 0,
            'position': 0,
            'summary': {},
        }


def run_closing_strategy_backtest(
    parquet_dir: str,
    config_path: str,
    output_dir: str,
    exchange_mapping_path: str = None,
    max_sheets: int = None,
    workers: int = None,
    spread_override: float = None,
    vwap_period_override: int = None,
    stop_loss_override: float = None,
    auction_fill_pct: float = 10.0,
    generate_plots: bool = True,
    trend_filter_sell_enabled: bool = True,
    trend_filter_sell_threshold: float = None,
    trend_filter_buy_enabled: bool = False,
    trend_filter_buy_threshold: float = None,
):
    """
    Run closing strategy backtest.
    
    Args:
        parquet_dir: Directory with Parquet files
        config_path: Path to config JSON
        output_dir: Output directory
        exchange_mapping_path: Path to exchange mapping JSON file
        max_sheets: Limit number of securities
        workers: Number of parallel workers
        spread_override: Override spread_vwap_pct for all securities
        vwap_period_override: Override vwap_preclose_period_min for all securities
        stop_loss_override: Override stop_loss_threshold_pct for all securities
        auction_fill_pct: Maximum fill as percentage of auction volume (default 10%)
        generate_plots: Whether to generate trade plots after backtest (default True)
        trend_filter_sell_enabled: Enable trend filter for SELL entries (default True)
        trend_filter_sell_threshold: Override trend_filter_sell_threshold_bps_hr
        trend_filter_buy_enabled: Enable trend filter for BUY entries (default False)
        trend_filter_buy_threshold: Override trend_filter_buy_threshold_bps_hr
    """
    print("=" * 60)
    print("CLOSING STRATEGY BACKTEST")
    print("=" * 60)
    print(f"Auction fill limit: {auction_fill_pct}% of auction volume")
    
    start_time = time.time()
    
    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Load exchange mapping
    if exchange_mapping_path:
        exchange_mapping = load_exchange_mapping(exchange_mapping_path)
        print(f"Loaded exchange mapping for {len(exchange_mapping)} securities")
    else:
        exchange_mapping = {}
        print("No exchange mapping provided, using ADX defaults")
    
    # Apply overrides
    if spread_override is not None or vwap_period_override is not None or stop_loss_override is not None or trend_filter_sell_threshold is not None or trend_filter_buy_threshold is not None:
        for security in config:
            if spread_override is not None:
                config[security]['spread_vwap_pct'] = spread_override
            if vwap_period_override is not None:
                config[security]['vwap_preclose_period_min'] = vwap_period_override
            if stop_loss_override is not None:
                config[security]['stop_loss_threshold_pct'] = stop_loss_override
            if trend_filter_sell_threshold is not None:
                config[security]['trend_filter_sell_threshold_bps_hr'] = trend_filter_sell_threshold
            if trend_filter_buy_threshold is not None:
                config[security]['trend_filter_buy_threshold_bps_hr'] = trend_filter_buy_threshold
    
    # Apply trend filter enabled/disabled per side
    for security in config:
        config[security]['trend_filter_sell_enabled'] = trend_filter_sell_enabled
        config[security]['trend_filter_buy_enabled'] = trend_filter_buy_enabled
    
    # Load data
    print(f"\nLoading data from {parquet_dir}...")
    data = load_parquet_data(parquet_dir, max_sheets)
    print(f"Loaded {len(data)} securities")
    
    # Prepare tasks (include exchange_mapping and auction_fill_pct)
    tasks = [(security, df, config, exchange_mapping, auction_fill_pct) for security, df in data.items()]
    
    # Process in parallel
    if workers is None:
        workers = min(os.cpu_count() or 4, len(tasks))
    
    print(f"\nProcessing with {workers} workers...")
    results = []
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_security_wrapper, task): task[0] 
                   for task in tasks}
        
        for future in as_completed(futures):
            security = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                if 'error' in result:
                    print(f"  ❌ {security}: {result['error']}")
                else:
                    summary = result.get('summary', {})
                    print(f"  ✓ {security}: {summary.get('total_trades', 0)} trades, "
                          f"P&L: {result.get('pnl', 0):,.2f} AED")
            except Exception as e:
                print(f"  ❌ {security}: {e}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save per-security trade logs
    all_trades = []
    for result in results:
        security = result['security']
        trades = result.get('trades', [])
        
        if trades:
            # Convert trades to DataFrame
            trade_records = []
            for t in trades:
                trade_records.append({
                    'timestamp': t.timestamp,
                    'side': t.side,
                    'price': t.price,
                    'quantity': t.quantity,
                    'realized_pnl': t.realized_pnl,
                    'trade_type': t.trade_type,
                    'vwap_reference': t.vwap_reference,
                })
            
            trades_df = pd.DataFrame(trade_records)
            trades_df['security'] = security
            
            # Save per-security
            output_path = os.path.join(output_dir, f"{security}_trades.csv")
            trades_df.to_csv(output_path, index=False)
            
            all_trades.append(trades_df)
    
    # Save summary
    summary_records = []
    for result in results:
        summary = result.get('summary', {})
        summary_records.append({
            'security': result['security'],
            'total_trades': summary.get('total_trades', 0),
            'auction_entries': summary.get('auction_entries', 0),
            'buy_entries': summary.get('buy_entries', 0),
            'sell_entries': summary.get('sell_entries', 0),
            'vwap_exits': summary.get('vwap_exits', 0),
            'stop_losses': summary.get('stop_losses', 0),
            'eod_flattens': summary.get('eod_flattens', 0),
            'filtered_sell_entries': summary.get('filtered_sell_entries', 0),
            'filtered_buy_entries': summary.get('filtered_buy_entries', 0),
            'realized_pnl': result.get('pnl', 0),
            'final_position': result.get('position', 0),
        })
    
    summary_df = pd.DataFrame(summary_records)
    summary_df.to_csv(os.path.join(output_dir, 'backtest_summary.csv'), index=False)
    
    # Print results
    elapsed = time.time() - start_time
    total_trades = sum(r.get('summary', {}).get('total_trades', 0) for r in results)
    total_pnl = sum(r.get('pnl', 0) for r in results)
    total_entries = sum(r.get('summary', {}).get('auction_entries', 0) for r in results)
    total_buy_entries = sum(r.get('summary', {}).get('buy_entries', 0) for r in results)
    total_sell_entries = sum(r.get('summary', {}).get('sell_entries', 0) for r in results)
    total_exits = sum(r.get('summary', {}).get('vwap_exits', 0) for r in results)
    total_stop_losses = sum(r.get('summary', {}).get('stop_losses', 0) for r in results)
    total_eod_flattens = sum(r.get('summary', {}).get('eod_flattens', 0) for r in results)
    total_filtered_sell = sum(r.get('summary', {}).get('filtered_sell_entries', 0) for r in results)
    total_filtered_buy = sum(r.get('summary', {}).get('filtered_buy_entries', 0) for r in results)
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Securities processed: {len(results)}")
    print(f"Trend filter SELL:    {'ENABLED' if trend_filter_sell_enabled else 'DISABLED'}")
    print(f"Trend filter BUY:     {'ENABLED' if trend_filter_buy_enabled else 'DISABLED'}")
    print(f"Total trades:         {total_trades:,}")
    print(f"  Auction entries:    {total_entries:,} (BUY: {total_buy_entries:,}, SELL: {total_sell_entries:,})")
    print(f"  VWAP exits:         {total_exits:,}")
    print(f"  Stop-losses:        {total_stop_losses:,}")
    print(f"  EOD flattens:       {total_eod_flattens:,}")
    if trend_filter_sell_enabled:
        print(f"  Filtered SELL:      {total_filtered_sell:,} (skipped due to uptrend)")
    if trend_filter_buy_enabled:
        print(f"  Filtered BUY:       {total_filtered_buy:,} (skipped due to downtrend)")
    print(f"Total P&L:            {total_pnl:,.2f} AED")
    print(f"Processing time:      {elapsed:.1f}s")
    print(f"\nOutput saved to: {output_dir}")
    
    # Show top/bottom performers
    if summary_records:
        print("\n" + "-" * 40)
        print("TOP 5 PERFORMERS:")
        sorted_results = sorted(summary_records, key=lambda x: x['realized_pnl'], reverse=True)
        for r in sorted_results[:5]:
            print(f"  {r['security']}: {r['realized_pnl']:,.2f} AED ({r['total_trades']} trades)")
        
        print("\nBOTTOM 5 PERFORMERS:")
        for r in sorted_results[-5:]:
            print(f"  {r['security']}: {r['realized_pnl']:,.2f} AED ({r['total_trades']} trades)")
    
    # Generate plots
    if generate_plots:
        print("\n" + "-" * 40)
        print("GENERATING PLOTS...")
        from scripts.plot_closing_strategy_trades import generate_all_plots
        plots_dir = os.path.join(output_dir, 'plots')
        generate_all_plots(
            parquet_dir=parquet_dir,
            trades_dir=output_dir,
            output_dir=plots_dir,
            config=config  # Pass config for parameter display
        )
    
    return {
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'results': results,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Run Closing Strategy Backtest',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_closing_strategy.py
    python scripts/run_closing_strategy.py --max-sheets 5
    python scripts/run_closing_strategy.py --spread 0.3 --vwap-period 20
        """
    )
    
    parser.add_argument(
        '--parquet-dir',
        default='data/parquet',
        help='Directory with Parquet files (default: data/parquet)'
    )
    parser.add_argument(
        '--config',
        default='configs/closing_strategy_config.json',
        help='Path to config JSON (default: configs/closing_strategy_config.json)'
    )
    parser.add_argument(
        '--output-dir',
        default='output/closing_strategy',
        help='Output directory (default: output/closing_strategy)'
    )
    parser.add_argument(
        '--max-sheets',
        type=int,
        help='Limit number of securities to process'
    )
    parser.add_argument(
        '--workers',
        type=int,
        help='Number of parallel workers (default: CPU count)'
    )
    parser.add_argument(
        '--spread',
        type=float,
        help='Override spread_vwap_pct for all securities (e.g., 0.5 for 0.5%%)'
    )
    parser.add_argument(
        '--vwap-period',
        type=int,
        help='Override VWAP pre-close period in minutes (default: 15)'
    )
    parser.add_argument(
        '--stop-loss',
        type=float,
        help='Override stop-loss threshold %% for all securities (default: 2.0)'
    )
    parser.add_argument(
        '--exchange-mapping',
        default='data/Exchange_mapping.json',
        help='Path to exchange mapping JSON (default: data/Exchange_mapping.json)'
    )
    parser.add_argument(
        '--auction-fill-pct',
        type=float,
        default=10.0,
        help='Max fill as percentage of auction volume (default: 10.0)'
    )
    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Skip generating plots after backtest'
    )
    parser.add_argument(
        '--no-trend-filter-sell',
        action='store_true',
        help='Disable trend filter for SELL entries (default: enabled)'
    )
    parser.add_argument(
        '--trend-threshold-sell',
        type=float,
        help='SELL trend filter threshold in bps/hour (default: 10.0). SELL entries skipped when uptrend > threshold.'
    )
    parser.add_argument(
        '--trend-filter-buy',
        action='store_true',
        help='Enable trend filter for BUY entries (default: disabled). BUY entries skipped when downtrend < -threshold.'
    )
    parser.add_argument(
        '--trend-threshold-buy',
        type=float,
        help='BUY trend filter threshold in bps/hour (default: 10.0). BUY entries skipped when downtrend < -threshold.'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    if not os.path.isabs(args.parquet_dir):
        args.parquet_dir = os.path.join(PROJECT_ROOT, args.parquet_dir)
    if not os.path.isabs(args.config):
        args.config = os.path.join(PROJECT_ROOT, args.config)
    if not os.path.isabs(args.output_dir):
        args.output_dir = os.path.join(PROJECT_ROOT, args.output_dir)
    if not os.path.isabs(args.exchange_mapping):
        args.exchange_mapping = os.path.join(PROJECT_ROOT, args.exchange_mapping)
    
    run_closing_strategy_backtest(
        parquet_dir=args.parquet_dir,
        config_path=args.config,
        output_dir=args.output_dir,
        exchange_mapping_path=args.exchange_mapping,
        max_sheets=args.max_sheets,
        workers=args.workers,
        spread_override=args.spread,
        vwap_period_override=args.vwap_period,
        stop_loss_override=args.stop_loss,
        auction_fill_pct=args.auction_fill_pct,
        generate_plots=not args.no_plots,
        trend_filter_sell_enabled=not args.no_trend_filter_sell,
        trend_filter_sell_threshold=args.trend_threshold_sell,
        trend_filter_buy_enabled=args.trend_filter_buy,
        trend_filter_buy_threshold=args.trend_threshold_buy,
    )


if __name__ == '__main__':
    main()
