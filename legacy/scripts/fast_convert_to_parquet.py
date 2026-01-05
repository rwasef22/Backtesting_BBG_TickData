"""Fast Excel to Parquet conversion using streaming reader.

Uses openpyxl streaming for memory efficiency.
"""
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from src.data_loader import stream_sheets


def fast_convert_to_parquet(
    excel_path: str = 'data/raw/TickData.xlsx',
    output_dir: str = 'data/parquet',
    max_sheets: int = None
):
    """Convert Excel to Parquet using streaming reader."""
    print("="*80)
    print("FAST EXCEL TO PARQUET CONVERSION")
    print("="*80)
    print(f"Input:  {excel_path}")
    print(f"Output: {output_dir}")
    print("="*80)
    print()
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    # Use streaming reader to process each sheet
    current_sheet = None
    current_data = []
    converted = 0
    total_rows = 0
    
    print("Processing sheets...")
    
    for sheet_name, chunk_df in stream_sheets(excel_path, header_row=3, chunk_size=100000, max_sheets=max_sheets):
        # Accumulate chunks for same sheet
        if current_sheet != sheet_name:
            # Save previous sheet if exists
            if current_sheet and current_data:
                df = pd.concat(current_data, ignore_index=True)
                security = current_sheet.replace(' UH Equity', '').replace(' DH Equity', '').lower()
                parquet_file = output_path / f"{security}.parquet"
                
                # Preprocess - ensure timestamp
                df = preprocess_df(df)
                
                if df is not None and len(df) > 0:
                    df.to_parquet(parquet_file, compression='snappy', index=False)
                    size_mb = parquet_file.stat().st_size / (1024 * 1024)
                    print(f"  [OK] {security}: {len(df):,} rows -> {parquet_file.name} ({size_mb:.1f} MB)")
                    converted += 1
                    total_rows += len(df)
            
            # Start new sheet
            current_sheet = sheet_name
            current_data = []
            print(f"\n[{converted + 1}] {sheet_name}")
        
        current_data.append(chunk_df)
    
    # Save last sheet
    if current_sheet and current_data:
        df = pd.concat(current_data, ignore_index=True)
        security = current_sheet.replace(' UH Equity', '').replace(' DH Equity', '').lower()
        parquet_file = output_path / f"{security}.parquet"
        
        df = preprocess_df(df)
        
        if df is not None and len(df) > 0:
            df.to_parquet(parquet_file, compression='snappy', index=False)
            size_mb = parquet_file.stat().st_size / (1024 * 1024)
            print(f"  [OK] {security}: {len(df):,} rows -> {parquet_file.name} ({size_mb:.1f} MB)")
            converted += 1
            total_rows += len(df)
    
    elapsed = time.time() - start_time
    
    print()
    print("="*80)
    print("CONVERSION COMPLETE")
    print("="*80)
    print(f"Time:       {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Converted:  {converted} sheets")
    print(f"Total rows: {total_rows:,}")
    print("="*80)
    
    # List files
    print()
    print("Generated files:")
    for pf in sorted(output_path.glob("*.parquet")):
        size_mb = pf.stat().st_size / (1024 * 1024)
        print(f"  {pf.name:25s} {size_mb:6.1f} MB")


def preprocess_df(df):
    """Preprocess chunk to standard format."""
    # Normalize column names
    df.columns = [str(c).strip().lower() if c is not None else f'col_{i}' 
                  for i, c in enumerate(df.columns)]
    
    # Combine date and time if separate
    if 'date' in df.columns and 'time' in df.columns:
        df['timestamp'] = pd.to_datetime(
            df['date'].astype(str) + ' ' + df['time'].astype(str), 
            errors='coerce'
        )
        df = df.drop(['date', 'time'], axis=1)
    
    # Rename columns to standard
    renames = {}
    if 'type' in df.columns:
        renames['type'] = 'type'
    if 'price' in df.columns:
        renames['price'] = 'price'
    if 'volume' in df.columns:
        renames['volume'] = 'volume'
    elif 'size' in df.columns:
        renames['size'] = 'volume'
    
    if renames:
        df = df.rename(columns=renames)
    
    # Keep only required columns
    required = ['timestamp', 'type', 'price', 'volume']
    available = [c for c in required if c in df.columns]
    
    if len(available) < 4:
        print(f"    Warning: Missing columns. Have: {list(df.columns)}")
        return None
    
    df = df[available]
    
    # Drop nulls
    df = df.dropna(subset=['timestamp', 'price'])
    
    return df


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/raw/TickData.xlsx')
    parser.add_argument('--output', default='data/parquet')
    parser.add_argument('--max-sheets', type=int, default=None)
    args = parser.parse_args()
    
    fast_convert_to_parquet(args.input, args.output, args.max_sheets)
