"""Comprehensive validation script to compare backtest outputs.

This script compares results from different backtest implementations
(sequential vs parallel vs Parquet) to ensure they produce identical results.

Usage:
    # Compare two output directories
    python scripts/validate_backtest_results.py output/sequential output/parallel
    
    # Compare specific securities
    python scripts/validate_backtest_results.py output/v1_baseline output/v1_parallel --securities ADNOCGAS EMAAR
    
    # Detailed comparison with full trade-by-trade analysis
    python scripts/validate_backtest_results.py output/ref output/test --detailed
"""
import argparse
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class BacktestValidator:
    """Validates backtest results across different implementations."""
    
    def __init__(self, tolerance_pnl=0.01, tolerance_price=0.0001):
        """Initialize validator with tolerance levels.
        
        Args:
            tolerance_pnl: Acceptable P&L difference (AED)
            tolerance_price: Acceptable price difference (price units)
        """
        self.tolerance_pnl = tolerance_pnl
        self.tolerance_price = tolerance_price
        self.results = {
            'securities_compared': 0,
            'perfect_matches': 0,
            'acceptable_differences': 0,
            'failures': 0,
            'details': []
        }
    
    def compare_directories(self, dir1: str, dir2: str, securities=None, detailed=False):
        """Compare all securities between two output directories.
        
        Args:
            dir1: First directory (reference)
            dir2: Second directory (test)
            securities: Optional list of securities to compare
            detailed: If True, perform trade-by-trade comparison
        """
        dir1_path = Path(dir1)
        dir2_path = Path(dir2)
        
        if not dir1_path.exists():
            print(f"❌ ERROR: Directory not found: {dir1}")
            return False
        
        if not dir2_path.exists():
            print(f"❌ ERROR: Directory not found: {dir2}")
            return False
        
        # Find all trade CSV files
        csv_files_1 = {f.stem.replace('_trades_timeseries', ''): f 
                      for f in dir1_path.glob('*_trades_timeseries.csv')}
        csv_files_2 = {f.stem.replace('_trades_timeseries', ''): f 
                      for f in dir2_path.glob('*_trades_timeseries.csv')}
        
        # Filter to requested securities
        if securities:
            csv_files_1 = {k: v for k, v in csv_files_1.items() if k.upper() in [s.upper() for s in securities]}
            csv_files_2 = {k: v for k, v in csv_files_2.items() if k.upper() in [s.upper() for s in securities]}
        
        # Find common securities
        common_securities = set(csv_files_1.keys()) & set(csv_files_2.keys())
        only_in_dir1 = set(csv_files_1.keys()) - set(csv_files_2.keys())
        only_in_dir2 = set(csv_files_2.keys()) - set(csv_files_1.keys())
        
        print("="*80)
        print("BACKTEST RESULTS COMPARISON")
        print("="*80)
        print(f"Reference dir:  {dir1}")
        print(f"Test dir:       {dir2}")
        print(f"Common securities: {len(common_securities)}")
        if only_in_dir1:
            print(f"Only in reference: {sorted(only_in_dir1)}")
        if only_in_dir2:
            print(f"Only in test:      {sorted(only_in_dir2)}")
        print("="*80)
        print()
        
        if not common_securities:
            print("❌ No common securities found to compare!")
            return False
        
        # Compare each security
        for i, security in enumerate(sorted(common_securities), 1):
            print(f"[{i}/{len(common_securities)}] Comparing {security.upper()}...")
            
            file1 = csv_files_1[security]
            file2 = csv_files_2[security]
            
            result = self.compare_security(security, file1, file2, detailed)
            self.results['details'].append(result)
            
            if result['status'] == 'PERFECT':
                self.results['perfect_matches'] += 1
                print(f"  ✓ PERFECT MATCH")
            elif result['status'] == 'ACCEPTABLE':
                self.results['acceptable_differences'] += 1
                print(f"  ⚠ ACCEPTABLE (within tolerance)")
                print(f"    Max P&L diff: {result['max_pnl_diff']:.4f} AED")
            else:
                self.results['failures'] += 1
                print(f"  ❌ FAILED")
                for issue in result['issues']:
                    print(f"    - {issue}")
            print()
            
            self.results['securities_compared'] += 1
        
        # Summary
        self.print_summary()
        
        return self.results['failures'] == 0
    
    def compare_security(self, security: str, file1: Path, file2: Path, detailed: bool):
        """Compare trade files for a single security.
        
        Returns:
            Dict with comparison results
        """
        result = {
            'security': security,
            'status': 'UNKNOWN',
            'issues': [],
            'trade_count_ref': 0,
            'trade_count_test': 0,
            'max_pnl_diff': 0.0,
            'max_price_diff': 0.0,
            'timestamp_mismatches': 0
        }
        
        try:
            # Read both files
            df1 = pd.read_csv(file1)
            df2 = pd.read_csv(file2)
            
            result['trade_count_ref'] = len(df1)
            result['trade_count_test'] = len(df2)
            
            # Check 1: Trade count
            if len(df1) != len(df2):
                result['issues'].append(f"Trade count mismatch: {len(df1)} vs {len(df2)}")
                result['status'] = 'FAILED'
                return result
            
            if len(df1) == 0:
                result['status'] = 'PERFECT'
                result['issues'].append("No trades (both empty)")
                return result
            
            # Normalize column names
            df1.columns = [c.lower().strip() for c in df1.columns]
            df2.columns = [c.lower().strip() for c in df2.columns]
            
            # Check 2: Required columns present
            required_cols = ['timestamp', 'side', 'fill_price', 'fill_qty', 'realized_pnl', 'position', 'pnl']
            
            for col in required_cols:
                if col not in df1.columns or col not in df2.columns:
                    result['issues'].append(f"Missing column: {col}")
                    result['status'] = 'FAILED'
                    return result
            
            # Sort both by timestamp for alignment
            df1 = df1.sort_values('timestamp').reset_index(drop=True)
            df2 = df2.sort_values('timestamp').reset_index(drop=True)
            
            # Check 3: Timestamps match
            timestamp_matches = (df1['timestamp'] == df2['timestamp']).sum()
            if timestamp_matches < len(df1):
                result['timestamp_mismatches'] = len(df1) - timestamp_matches
                if detailed:
                    result['issues'].append(f"Timestamp mismatches: {result['timestamp_mismatches']}")
            
            # Check 4: Side matches
            side_matches = (df1['side'] == df2['side']).sum()
            if side_matches < len(df1):
                result['issues'].append(f"Side mismatches: {len(df1) - side_matches}")
                result['status'] = 'FAILED'
                return result
            
            # Check 5: Fill prices (with tolerance)
            price_diff = np.abs(df1['fill_price'] - df2['fill_price'])
            result['max_price_diff'] = price_diff.max()
            
            if result['max_price_diff'] > self.tolerance_price:
                result['issues'].append(f"Price difference: {result['max_price_diff']:.6f} (tolerance: {self.tolerance_price})")
                result['status'] = 'FAILED'
                return result
            
            # Check 6: Fill quantities (exact match required)
            qty_diff = np.abs(df1['fill_qty'] - df2['fill_qty'])
            if qty_diff.sum() > 0:
                result['issues'].append(f"Quantity mismatches: {(qty_diff > 0).sum()} trades")
                result['status'] = 'FAILED'
                return result
            
            # Check 7: Cumulative P&L (final value most important)
            pnl_diff = np.abs(df1['pnl'] - df2['pnl'])
            result['max_pnl_diff'] = pnl_diff.max()
            
            final_pnl_ref = df1['pnl'].iloc[-1]
            final_pnl_test = df2['pnl'].iloc[-1]
            final_pnl_diff = abs(final_pnl_ref - final_pnl_test)
            
            if final_pnl_diff > self.tolerance_pnl:
                result['issues'].append(f"Final P&L diff: {final_pnl_diff:.2f} AED (tolerance: {self.tolerance_pnl})")
                result['status'] = 'FAILED'
                return result
            
            # Check 8: Position matches
            position_diff = np.abs(df1['position'] - df2['position'])
            if position_diff.sum() > 0:
                result['issues'].append(f"Position mismatches: {(position_diff > 0).sum()} trades")
                result['status'] = 'FAILED'
                return result
            
            # Detailed trade-by-trade comparison if requested
            if detailed:
                for idx in range(len(df1)):
                    if pnl_diff.iloc[idx] > self.tolerance_pnl:
                        result['issues'].append(
                            f"Trade {idx}: P&L diff {pnl_diff.iloc[idx]:.4f} at {df1['timestamp'].iloc[idx]}"
                        )
            
            # Determine final status
            if result['max_pnl_diff'] < 0.001 and result['max_price_diff'] < 0.00001:
                result['status'] = 'PERFECT'
            else:
                result['status'] = 'ACCEPTABLE'
            
        except Exception as e:
            result['issues'].append(f"Error reading files: {e}")
            result['status'] = 'FAILED'
        
        return result
    
    def print_summary(self):
        """Print comparison summary."""
        print("="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"Securities compared: {self.results['securities_compared']}")
        print(f"Perfect matches:     {self.results['perfect_matches']}")
        print(f"Acceptable diffs:    {self.results['acceptable_differences']}")
        print(f"Failures:            {self.results['failures']}")
        print("="*80)
        
        if self.results['failures'] > 0:
            print("\n❌ VALIDATION FAILED")
            print("\nFailed securities:")
            for detail in self.results['details']:
                if detail['status'] == 'FAILED':
                    print(f"\n{detail['security'].upper()}:")
                    for issue in detail['issues']:
                        print(f"  - {issue}")
        elif self.results['acceptable_differences'] > 0:
            print("\n⚠ VALIDATION PASSED WITH MINOR DIFFERENCES")
            print("\nSecurities with acceptable differences:")
            for detail in self.results['details']:
                if detail['status'] == 'ACCEPTABLE':
                    print(f"  {detail['security'].upper()}: Max P&L diff = {detail['max_pnl_diff']:.4f} AED")
        else:
            print("\n✅ VALIDATION PASSED - PERFECT MATCH")
        
        print("="*80)
    
    def export_report(self, output_file: str):
        """Export detailed comparison report to CSV."""
        report_data = []
        for detail in self.results['details']:
            report_data.append({
                'security': detail['security'],
                'status': detail['status'],
                'trade_count_ref': detail['trade_count_ref'],
                'trade_count_test': detail['trade_count_test'],
                'max_pnl_diff': detail['max_pnl_diff'],
                'max_price_diff': detail['max_price_diff'],
                'timestamp_mismatches': detail['timestamp_mismatches'],
                'issues': '; '.join(detail['issues']) if detail['issues'] else 'None'
            })
        
        df = pd.DataFrame(report_data)
        df.to_csv(output_file, index=False)
        print(f"\n✓ Detailed report exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Validate backtest results across implementations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare two output directories
  python scripts/validate_backtest_results.py output/sequential output/parallel
  
  # Compare specific securities
  python scripts/validate_backtest_results.py output/v1_baseline output/v1_parallel --securities ADNOCGAS EMAAR
  
  # Detailed comparison
  python scripts/validate_backtest_results.py output/ref output/test --detailed
  
  # Export report
  python scripts/validate_backtest_results.py output/ref output/test --report validation_report.csv
        """
    )
    
    parser.add_argument('dir1', help='Reference output directory')
    parser.add_argument('dir2', help='Test output directory')
    parser.add_argument('--securities', nargs='+', default=None,
                       help='Specific securities to compare (default: all)')
    parser.add_argument('--detailed', action='store_true',
                       help='Perform detailed trade-by-trade comparison')
    parser.add_argument('--tolerance-pnl', type=float, default=0.01,
                       help='P&L tolerance in AED (default: 0.01)')
    parser.add_argument('--tolerance-price', type=float, default=0.0001,
                       help='Price tolerance (default: 0.0001)')
    parser.add_argument('--report', '-r', default=None,
                       help='Export detailed report to CSV file')
    
    args = parser.parse_args()
    
    # Create validator
    validator = BacktestValidator(
        tolerance_pnl=args.tolerance_pnl,
        tolerance_price=args.tolerance_price
    )
    
    # Run comparison
    success = validator.compare_directories(
        args.dir1,
        args.dir2,
        securities=args.securities,
        detailed=args.detailed
    )
    
    # Export report if requested
    if args.report:
        validator.export_report(args.report)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
