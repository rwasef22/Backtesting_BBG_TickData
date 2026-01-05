import pandas as pd
import glob
from pathlib import Path

# Process all trade CSV files in comprehensive sweep output
csv_files = glob.glob('output/comprehensive_sweep/**/*_trades.csv', recursive=True)

print(f"Found {len(csv_files)} CSV files to process")

for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file)
        
        # Round PNL and position columns if they exist
        modified = False
        if 'realized_pnl' in df.columns:
            df['realized_pnl'] = df['realized_pnl'].round(0).astype(int)
            modified = True
        if 'pnl' in df.columns:
            df['pnl'] = df['pnl'].round(0).astype(int)
            modified = True
        if 'position' in df.columns:
            df['position'] = df['position'].round(0).astype(int)
            modified = True
        
        if modified:
            df.to_csv(csv_file, index=False)
            print(f"✓ Processed: {csv_file}")
    except Exception as e:
        print(f"✗ Error processing {csv_file}: {e}")

# Process per_security_summary.csv files
summary_files = glob.glob('output/comprehensive_sweep/**/per_security_summary.csv', recursive=True)

print(f"\nFound {len(summary_files)} summary files to process")

for summary_file in summary_files:
    try:
        df = pd.read_csv(summary_file)
        
        # Round PNL and position columns if they exist
        modified = False
        if 'pnl' in df.columns:
            df['pnl'] = df['pnl'].round(0).astype(int)
            modified = True
        if 'position' in df.columns:
            df['position'] = df['position'].round(0).astype(int)
            modified = True
        
        if modified:
            df.to_csv(summary_file, index=False)
            print(f"✓ Processed: {summary_file}")
    except Exception as e:
        print(f"✗ Error processing {summary_file}: {e}")

print("\nDone!")
