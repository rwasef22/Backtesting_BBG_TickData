"""Comprehensive Parquet validation script.

This script validates Parquet files against the Excel source to ensure:
1. Same securities exist in both
2. Same date ranges
3. Similar row counts
4. Data integrity
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parquet_utils import validate_parquet_against_excel, print_parquet_info


def main():
    print("="*80)
    print("PARQUET DATA VALIDATION")
    print("="*80)
    
    excel_path = 'data/raw/TickData.xlsx'
    parquet_dir = 'data/parquet'
    
    # Check if files exist
    if not Path(excel_path).exists():
        print(f"\n✗ ERROR: Excel file not found: {excel_path}")
        return
    
    if not Path(parquet_dir).exists() or not list(Path(parquet_dir).glob('*.parquet')):
        print(f"\n✗ ERROR: No Parquet files found in {parquet_dir}")
        print("\nRun conversion first:")
        print("  python scripts/convert_excel_to_parquet.py")
        return
    
    # Show Parquet info
    print("\nCurrent Parquet Files:")
    print_parquet_info(parquet_dir)
    
    # Run validation
    print("\nRunning validation checks...")
    print("-"*80)
    
    is_valid, issues = validate_parquet_against_excel(
        excel_path=excel_path,
        parquet_dir=parquet_dir,
        max_sheets=None  # Check all sheets
    )
    
    if is_valid:
        print("\n" + "="*80)
        print("✓ VALIDATION PASSED")
        print("="*80)
        print("\nParquet files are valid and match Excel source:")
        print("  ✓ All securities present")
        print("  ✓ Date ranges match")
        print("  ✓ Data coverage is complete")
        print("\nSafe to use Parquet files for backtesting.")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("✗ VALIDATION FAILED")
        print("="*80)
        print(f"\nFound {len(issues)} issue(s):\n")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
        
        print("\n" + "="*80)
        print("RECOMMENDED ACTIONS:")
        print("="*80)
        print("\n1. Delete Parquet directory:")
        print(f"   Remove-Item -Recurse -Force {parquet_dir}")
        print("\n2. Reconvert from Excel:")
        print("   python scripts/convert_excel_to_parquet.py")
        print("\n3. Rerun validation:")
        print("   python scripts/validate_parquet_data.py")
        print("\nOR run any backtest script - it will auto-reconvert if needed.")
        print("="*80)


if __name__ == '__main__':
    main()
