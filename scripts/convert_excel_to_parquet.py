"""Convert TickData Excel file to Parquet format for faster I/O.

This script performs a one-time conversion of the Excel file to per-security
Parquet files, enabling much faster I/O (5-10x) and true parallel reads without
Excel sheet locking issues.

Benefits:
- 5-10x faster I/O than Excel
- Columnar format optimized for analytics
- No sheet locking (all workers can read simultaneously)
- Smaller file sizes (~50% compression)
- Direct pandas integration

Usage:
    # Convert entire Excel file
    python scripts/convert_excel_to_parquet.py
    
    # Specify custom paths
    python scripts/convert_excel_to_parquet.py --input data/raw/TickData.xlsx --output data/parquet
    
    # Test with limited sheets
    python scripts/convert_excel_to_parquet.py --max-sheets 5
"""
import argparse
import os
import sys
from pathlib import Path
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd


def convert_excel_to_parquet(
    excel_path: str,
    output_dir: str,
    max_sheets: int = None,
    compression: str = 'snappy',
    header_row: int = 3
):
    """Convert Excel sheets to per-security Parquet files.
    
    Args:
        excel_path: Path to TickData.xlsx
        output_dir: Output directory for Parquet files
        max_sheets: Limit number of sheets (for testing)
        compression: Parquet compression ('snappy', 'gzip', or 'none')
        header_row: Excel header row (1-based)
    """
    print("="*80)
    print("EXCEL TO PARQUET CONVERSION")
    print("="*80)
    print(f"Input:       {excel_path}")
    print(f"Output dir:  {output_dir}")
    print(f"Compression: {compression}")
    print(f"Header row:  {header_row}")
    print("="*80)
    print()
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load Excel file
    print("Loading Excel file...")
    start_time = time.time()
    
    try:
        xls = pd.ExcelFile(excel_path)
        load_time = time.time() - start_time
        print(f"  [OK] Loaded in {load_time:.1f}s")
        print(f"  Found {len(xls.sheet_names)} sheets")
        print()
    except Exception as e:
        print(f"  [X] Error loading Excel: {e}")
        return False
    
    # Process sheets
    sheet_names = xls.sheet_names[:max_sheets] if max_sheets else xls.sheet_names
    
    print(f"Converting {len(sheet_names)} sheets...")
    print()
    
    converted = 0
    failed = 0
    total_rows = 0
    
    for i, sheet_name in enumerate(sheet_names, 1):
        print(f"[{i}/{len(sheet_names)}] {sheet_name}")
        
        try:
            # Read sheet
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_row-1)
            
            # Normalize column names
            df.columns = [str(c).strip().lower() if c is not None else f'col_{i}' 
                         for i, c in enumerate(df.columns)]
            
            # Combine date and time if separate
            if 'date' in df.columns and 'time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + 
                                                 df['time'].astype(str), errors='coerce')
                df.drop(['date', 'time'], axis=1, inplace=True)
            elif 'dates' in df.columns:
                df.rename(columns={'dates': 'timestamp'}, inplace=True)
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            # Ensure timestamp is datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            # Normalize column names to standard format
            column_mapping = {
                'type': 'type',
                'types': 'type',
                'price': 'price',
                'prices': 'price',
                'volume': 'volume',
                'size': 'volume',
                'qty': 'volume'
            }
            
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df.rename(columns={old_col: new_col}, inplace=True)
            
            # Ensure required columns exist
            required_cols = ['timestamp', 'type', 'price', 'volume']
            missing = [col for col in required_cols if col not in df.columns]
            
            if missing:
                print(f"  [X] Missing columns: {missing}")
                failed += 1
                continue
            
            # Select only required columns (reduce file size)
            df = df[required_cols]
            
            # Drop rows with missing values
            initial_rows = len(df)
            df.dropna(subset=['timestamp', 'price'], inplace=True)
            dropped = initial_rows - len(df)
            
            # Extract security name
            security = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
            
            # Write Parquet file
            parquet_file = output_path / f"{security.lower()}.parquet"
            
            df.to_parquet(
                parquet_file,
                compression=compression,
                index=False,
                engine='pyarrow'
            )
            
            file_size_mb = parquet_file.stat().st_size / (1024 * 1024)
            
            print(f"  [OK] {security}: {len(df):,} rows -> {parquet_file.name} ({file_size_mb:.1f} MB)")
            if dropped > 0:
                print(f"    (Dropped {dropped:,} rows with missing data)")
            
            converted += 1
            total_rows += len(df)
            
        except Exception as e:
            print(f"  [X] Error: {e}")
            failed += 1
    
    # Summary
    total_time = time.time() - start_time
    
    print()
    print("="*80)
    print("CONVERSION COMPLETE")
    print("="*80)
    print(f"Time:      {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Converted: {converted}/{len(sheet_names)} sheets")
    if failed > 0:
        print(f"Failed:    {failed} sheets")
    print(f"Total rows: {total_rows:,}")
    print(f"Output:     {output_path}/")
    print("="*80)
    print()
    
    # List generated files
    parquet_files = sorted(output_path.glob("*.parquet"))
    print(f"Generated {len(parquet_files)} Parquet files:")
    for pf in parquet_files:
        size_mb = pf.stat().st_size / (1024 * 1024)
        print(f"  {pf.name:30s} {size_mb:8.1f} MB")
    
    print()
    print("Next steps:")
    print("  1. Test reading Parquet files:")
    print("     python -c \"import pandas as pd; df = pd.read_parquet('data/parquet/adnocgas.parquet'); print(df.head())\"")
    print()
    print("  2. Run parallel backtest with Parquet:")
    print("     python scripts/run_parallel_backtest.py --strategy v1_baseline --data-format parquet")
    print()
    
    return converted > 0


def main():
    parser = argparse.ArgumentParser(
        description='Convert TickData Excel to Parquet format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert entire Excel file
  python scripts/convert_excel_to_parquet.py
  
  # Test with limited sheets
  python scripts/convert_excel_to_parquet.py --max-sheets 5
  
  # Custom paths
  python scripts/convert_excel_to_parquet.py --input data/raw/TickData.xlsx --output data/parquet
  
  # Use different compression
  python scripts/convert_excel_to_parquet.py --compression gzip
        """
    )
    
    parser.add_argument('--input', '-i', default='data/raw/TickData.xlsx',
                       help='Input Excel file (default: data/raw/TickData.xlsx)')
    parser.add_argument('--output', '-o', default='data/parquet',
                       help='Output directory (default: data/parquet)')
    parser.add_argument('--max-sheets', type=int, default=None,
                       help='Limit to first N sheets (for testing)')
    parser.add_argument('--compression', '-c', default='snappy',
                       choices=['snappy', 'gzip', 'none'],
                       help='Parquet compression algorithm (default: snappy)')
    parser.add_argument('--header-row', type=int, default=3,
                       help='Excel header row, 1-based (default: 3)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)
    
    # Check if pyarrow is installed
    try:
        import pyarrow.parquet
    except ImportError:
        print("ERROR: pyarrow not installed")
        print("Install with: pip install pyarrow")
        sys.exit(1)
    
    # Run conversion
    success = convert_excel_to_parquet(
        excel_path=args.input,
        output_dir=args.output,
        max_sheets=args.max_sheets,
        compression=args.compression,
        header_row=args.header_row
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
