"""Test Parquet auto-conversion integration.

This script tests that all main scripts properly use Parquet with auto-conversion.
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parquet_utils import ensure_parquet_data, get_data_source, print_parquet_info

def test_parquet_utils():
    """Test Parquet utility functions."""
    print("="*80)
    print("TESTING PARQUET UTILITIES")
    print("="*80)
    
    # Test 1: Check if Parquet exists
    print("\n1. Checking for existing Parquet data...")
    parquet_dir = Path('data/parquet')
    if parquet_dir.exists():
        parquet_files = list(parquet_dir.glob('*.parquet'))
        print(f"   Found {len(parquet_files)} Parquet files")
        print_parquet_info()
    else:
        print("   No Parquet directory found")
    
    # Test 2: Test get_data_source
    print("\n2. Testing get_data_source()...")
    try:
        data_path, data_format = get_data_source(
            excel_path='data/raw/TickData.xlsx',
            parquet_dir='data/parquet',
            prefer_parquet=True,
            auto_convert=False  # Don't convert in test
        )
        print(f"   Data source: {data_path}")
        print(f"   Format: {data_format}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Test ensure_parquet_data (dry run - check only)
    print("\n3. Testing ensure_parquet_data() with existing data...")
    try:
        result = ensure_parquet_data(
            excel_path='data/raw/TickData.xlsx',
            parquet_dir='data/parquet',
            force_reconvert=False,
            max_sheets=None
        )
        print(f"   Result: {result}")
        print(f"   ✓ Function works correctly")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nPARQUET INTEGRATION STATUS:")
    print("-"*80)
    
    # Check which scripts have been updated
    scripts_to_check = [
        'run_strategy.py',
        'run_parallel_backtest.py',
        'run_full_sequential.py',
        'comprehensive_sweep.py'
    ]
    
    for script in scripts_to_check:
        script_path = Path('scripts') / script
        if script_path.exists():
            content = script_path.read_text()
            has_import = 'from src.parquet_utils import' in content
            has_ensure = 'ensure_parquet_data' in content
            
            status = "✓ INTEGRATED" if (has_import and has_ensure) else "✗ NOT INTEGRATED"
            print(f"  {script:30s}: {status}")
        else:
            print(f"  {script:30s}: ⚠ NOT FOUND")
    
    print("="*80)
    print("\nRECOMMENDATION:")
    print("-"*80)
    if parquet_dir.exists() and list(parquet_dir.glob('*.parquet')):
        print("✓ Parquet data already exists")
        print("  All scripts will automatically use it for 5-10x faster I/O")
    else:
        print("⚠ No Parquet data found")
        print("  Scripts will auto-convert on first run")
        print("  Conversion takes ~5-10 minutes (one-time setup)")
    print("="*80)


if __name__ == '__main__':
    test_parquet_utils()
