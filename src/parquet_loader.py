"""Parquet data loader for streaming backtest.

This module provides a Parquet-compatible version of the data loader that reads
from per-security Parquet files instead of Excel sheets, providing 5-10x faster I/O.

Usage:
    from src.parquet_loader import stream_parquet_files
    
    for security, chunk in stream_parquet_files('data/parquet/', chunk_size=100000):
        # Process chunk
        pass
"""
from typing import Generator, Tuple, Optional, List
from pathlib import Path
import pandas as pd


def stream_parquet_files(
    parquet_dir: str,
    chunk_size: int = 100000,
    max_files: Optional[int] = None,
    only_trades: bool = False,
    file_filter: Optional[List[str]] = None
) -> Generator[Tuple[str, pd.DataFrame], None, None]:
    """Stream Parquet files as chunks.
    
    This is the Parquet equivalent of stream_sheets() from data_loader.py.
    Each Parquet file represents one security.
    
    Args:
        parquet_dir: Directory containing Parquet files
        chunk_size: Rows per chunk
        max_files: Limit to first N files (for testing)
        only_trades: Filter to trade events only
        file_filter: Optional list of security names to process (e.g., ['adnocgas', 'emaar'])
    
    Yields:
        Tuple of (security_name, chunk_df)
    """
    parquet_path = Path(parquet_dir)
    
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet directory not found: {parquet_dir}")
    
    # Find all Parquet files
    parquet_files = sorted(parquet_path.glob("*.parquet"))
    
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in {parquet_dir}")
    
    # Apply file filter
    if file_filter:
        parquet_files = [f for f in parquet_files 
                        if f.stem.lower() in [s.lower() for s in file_filter]]
    
    # Limit files if requested
    if max_files:
        parquet_files = parquet_files[:max_files]
    
    # Stream each file
    for parquet_file in parquet_files:
        security = parquet_file.stem.upper()  # Convert filename to security name
        
        # Read Parquet file
        try:
            df = pd.read_parquet(parquet_file)
        except Exception as e:
            print(f"Warning: Failed to read {parquet_file.name}: {e}")
            continue
        
        # Filter to trades if requested
        if only_trades and 'type' in df.columns:
            df = df[df['type'].astype(str).str.lower() == 'trade']
        
        # Yield in chunks
        total_rows = len(df)
        for start_idx in range(0, total_rows, chunk_size):
            end_idx = min(start_idx + chunk_size, total_rows)
            chunk = df.iloc[start_idx:end_idx].copy()
            
            # Add sheet_name format for compatibility with existing code
            sheet_name = f"{security} UH Equity"
            
            yield sheet_name, chunk


def read_single_parquet(parquet_dir: str, security: str) -> pd.DataFrame:
    """Read a single security's Parquet file.
    
    Args:
        parquet_dir: Directory containing Parquet files
        security: Security name (e.g., 'ADNOCGAS' or 'adnocgas')
    
    Returns:
        DataFrame with all data for the security
    """
    parquet_path = Path(parquet_dir)
    parquet_file = parquet_path / f"{security.lower()}.parquet"
    
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_file}")
    
    return pd.read_parquet(parquet_file)


def list_available_securities(parquet_dir: str) -> List[str]:
    """List all available securities in Parquet directory.
    
    Args:
        parquet_dir: Directory containing Parquet files
    
    Returns:
        List of security names
    """
    parquet_path = Path(parquet_dir)
    
    if not parquet_path.exists():
        return []
    
    parquet_files = sorted(parquet_path.glob("*.parquet"))
    return [f.stem.upper() for f in parquet_files]


def get_parquet_info(parquet_dir: str) -> dict:
    """Get information about Parquet files in directory.
    
    Args:
        parquet_dir: Directory containing Parquet files
    
    Returns:
        Dictionary with file info
    """
    parquet_path = Path(parquet_dir)
    
    if not parquet_path.exists():
        return {'exists': False}
    
    parquet_files = sorted(parquet_path.glob("*.parquet"))
    
    info = {
        'exists': True,
        'num_files': len(parquet_files),
        'securities': [],
        'total_size_mb': 0,
        'files': {}
    }
    
    for pf in parquet_files:
        security = pf.stem.upper()
        size_mb = pf.stat().st_size / (1024 * 1024)
        
        # Try to read metadata
        try:
            df = pd.read_parquet(pf)
            rows = len(df)
            cols = len(df.columns)
            
            # Get date range if timestamp column exists
            date_range = None
            if 'timestamp' in df.columns:
                date_range = (df['timestamp'].min(), df['timestamp'].max())
        except Exception as e:
            rows = None
            cols = None
            date_range = None
        
        info['securities'].append(security)
        info['total_size_mb'] += size_mb
        info['files'][security] = {
            'filename': pf.name,
            'size_mb': size_mb,
            'rows': rows,
            'cols': cols,
            'date_range': date_range
        }
    
    return info


def preprocess_parquet_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocess Parquet chunk for consistency with Excel loader.
    
    This ensures Parquet chunks have the same format as Excel chunks
    for compatibility with existing handlers.
    
    Args:
        df: Raw Parquet chunk
    
    Returns:
        Preprocessed DataFrame
    """
    # Ensure timestamp is datetime
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    # Ensure type is lowercase string
    if 'type' in df.columns:
        df['type'] = df['type'].astype(str).str.lower()
    
    # Ensure numeric types
    if 'price' in df.columns:
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
    
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    
    # Drop rows with critical missing values
    df.dropna(subset=['timestamp', 'price'], inplace=True)
    
    return df
