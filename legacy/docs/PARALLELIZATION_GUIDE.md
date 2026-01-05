# Parallelization Architecture Guide

## Current Architecture Analysis

### Sequential Flow

```
Current: Single-threaded sequential processing
┌─────────────────────────────────────────────────────────┐
│ stream_sheets() Generator                               │
│  ↓                                                      │
│ Security 1 → Chunk 1 → Chunk 2 → ... → Chunk N        │
│  ↓                                                      │
│ Security 2 → Chunk 1 → Chunk 2 → ... → Chunk N        │
│  ↓                                                      │
│ Security 3 → Chunk 1 → Chunk 2 → ... → Chunk N        │
│  ↓                                                      │
│ ...                                                     │
│  ↓                                                      │
│ Security 16 → Chunk 1 → Chunk 2 → ... → Chunk N       │
└─────────────────────────────────────────────────────────┘
Total Time: ~8-10 minutes (673k rows, 16 securities)
```

### Parallelization Potential

**Key Insight**: Securities are completely independent!
- Each has its own OrderBook instance
- Separate state dictionaries (position, pnl, trades)
- No shared mutable state between securities
- Perfect candidate for process-level parallelization

## Parallel Architecture Design

### Option 1: Process Pool (RECOMMENDED)

**Best for**: Full dataset runs, production backtests

```
Parallel: Multi-process with shared data loading
┌────────────────────────────────────────────────────────────┐
│ Main Process: Load Excel, identify sheets                  │
└────────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
   Process 1         Process 2         Process 3
 Security 1,5,9    Security 2,6,10   Security 3,7,11
 Security 4,8,12   Security 13       Security 14,15,16
        ↓                 ↓                 ↓
   [Results]         [Results]         [Results]
        └─────────────────┼─────────────────┘
                          ↓
              ┌───────────────────────┐
              │ Merge & Write Results │
              └───────────────────────┘

Expected Speedup: 3-4x on 4-core CPU, 6-8x on 8-core CPU
```

**Implementation**:

```python
# File: src/parallel_backtest.py
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import openpyxl
from typing import Dict, List, Callable
from pathlib import Path

from src.market_making_backtest import MarketMakingBacktest
from src.data_loader import stream_sheets


def process_single_security(
    sheet_name: str,
    file_path: str,
    handler_factory: Callable,
    config: dict,
    chunk_size: int = 100000,
    header_row: int = 3
) -> tuple:
    """Process a single security in isolation.
    
    This function runs in a separate process, so all state is local.
    
    Args:
        sheet_name: Excel sheet name (e.g., 'ADNOCGAS UH Equity')
        file_path: Path to TickData.xlsx
        handler_factory: Function that creates handler with config
        config: Configuration dict for all securities
        chunk_size: Rows per chunk
        header_row: Excel header row (1-based)
    
    Returns:
        Tuple of (security_name, results_dict)
    """
    # Create handler in this process
    handler = handler_factory(config)
    
    # Create backtest instance (process-local)
    backtest = MarketMakingBacktest(config=config)
    
    # Process only this sheet
    results = backtest.run_streaming(
        file_path=file_path,
        handler=handler,
        sheet_names_filter=[sheet_name],
        chunk_size=chunk_size,
        header_row=header_row,
        write_csv=False  # Don't write per-process, aggregate later
    )
    
    # Extract security name
    security = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
    
    return (security, results.get(security, {}))


def run_parallel_backtest(
    file_path: str,
    handler_factory: Callable,
    config: dict,
    max_workers: int = None,
    max_sheets: int = None,
    chunk_size: int = 100000,
    output_dir: str = 'output'
) -> Dict:
    """Run backtest with per-security parallelization.
    
    Args:
        file_path: Path to TickData.xlsx
        handler_factory: Function that creates handler with config
        config: Configuration dict
        max_workers: Number of parallel processes (default: CPU count)
        max_sheets: Limit number of securities (for testing)
        chunk_size: Rows per chunk
        output_dir: Output directory for results
        
    Returns:
        Combined results dict mapping security -> state
    """
    if max_workers is None:
        max_workers = cpu_count()
    
    print(f"Starting parallel backtest with {max_workers} workers")
    
    # Get sheet names from Excel
    wb = openpyxl.load_workbook(file_path, read_only=True)
    sheet_names = wb.sheetnames[:max_sheets] if max_sheets else wb.sheetnames
    wb.close()
    
    print(f"Processing {len(sheet_names)} securities: {sheet_names}")
    
    # Submit all securities to process pool
    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_sheet = {
            executor.submit(
                process_single_security,
                sheet_name,
                file_path,
                handler_factory,
                config,
                chunk_size
            ): sheet_name
            for sheet_name in sheet_names
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_sheet):
            sheet_name = future_to_sheet[future]
            try:
                security, result = future.result()
                results[security] = result
                print(f"✓ Completed {security}: {len(result.get('trades', []))} trades")
            except Exception as e:
                print(f"✗ Error processing {sheet_name}: {e}")
                import traceback
                traceback.print_exc()
    
    print(f"\n✓ All {len(results)} securities processed")
    
    # Write results
    if output_dir:
        write_results(results, output_dir)
    
    return results


def write_results(results: Dict, output_dir: str):
    """Write aggregated results to disk."""
    import pandas as pd
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Write per-security trade files
    for security, data in results.items():
        trades = data.get('trades', [])
        if trades:
            df = pd.DataFrame(trades)
            csv_path = output_path / f"{security.lower()}_trades_timeseries.csv"
            df.to_csv(csv_path, index=False)
            print(f"Saved: {csv_path}")
    
    # Write summary
    summary_rows = []
    for security, data in results.items():
        trades = data.get('trades', [])
        summary_rows.append({
            'security': security,
            'trades': len(trades),
            'realized_pnl': data.get('pnl', 0),
            'market_dates': len(data.get('market_dates', set())),
            'strategy_dates': len(data.get('strategy_dates', set()))
        })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_path / 'backtest_summary.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"Saved: {summary_path}")
```

### Option 2: Thread Pool (Simpler, Less Speedup)

**Best for**: I/O-bound operations, simple testing

```python
from concurrent.futures import ThreadPoolExecutor

# Same pattern as ProcessPoolExecutor but with threads
# Works if GIL not a bottleneck (mostly I/O bound)
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_single_security, ...) 
               for sheet in sheets]
    results = [f.result() for f in futures]
```

**Pros**: Lighter weight, shared memory
**Cons**: Python GIL limits CPU parallelism

## Usage Examples

### Basic Parallel Run

```python
# scripts/run_parallel_backtest.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parallel_backtest import run_parallel_backtest
from src.config_loader import load_strategy_config
from src.strategies.v1_baseline.handler import create_v1_handler

if __name__ == '__main__':
    config = load_strategy_config('configs/v1_baseline_config.json')
    
    results = run_parallel_backtest(
        file_path='data/raw/TickData.xlsx',
        handler_factory=lambda cfg: create_v1_handler(cfg),
        config=config,
        max_workers=4,  # Use 4 CPU cores
        output_dir='output/v1_baseline_parallel'
    )
    
    print(f"\n✓ Backtest complete: {len(results)} securities")
    total_trades = sum(len(r.get('trades', [])) for r in results.values())
    print(f"Total trades: {total_trades}")
```

### Quick Test (Limited Securities)

```python
results = run_parallel_backtest(
    file_path='data/raw/TickData.xlsx',
    handler_factory=lambda cfg: create_v1_handler(cfg),
    config=config,
    max_workers=2,
    max_sheets=5,  # Only first 5 securities
    output_dir='output/test_parallel'
)
```

### Benchmark Comparison

```python
import time

# Sequential baseline
start = time.time()
backtest = MarketMakingBacktest(config=config)
results_seq = backtest.run_streaming(
    file_path='data/raw/TickData.xlsx',
    handler=create_v1_handler(config)
)
time_seq = time.time() - start

# Parallel version
start = time.time()
results_par = run_parallel_backtest(
    file_path='data/raw/TickData.xlsx',
    handler_factory=lambda cfg: create_v1_handler(cfg),
    config=config,
    max_workers=4
)
time_par = time.time() - start

print(f"Sequential: {time_seq:.1f}s")
print(f"Parallel:   {time_par:.1f}s")
print(f"Speedup:    {time_seq/time_par:.2f}x")
```

## Implementation Considerations

### Pickle-ability Requirements

For `ProcessPoolExecutor`, all arguments must be pickle-able:

**✅ Safe:**
- Built-in types (str, int, dict, list)
- Module-level functions
- Classes defined at module level

**❌ Unsafe:**
- Lambda functions (use `def` instead)
- Local functions
- Objects with unpicklable state

**Solution**: Use factory functions

```python
# BAD: Lambda can't be pickled
handler_factory = lambda cfg: create_v1_handler(cfg)

# GOOD: Module-level function
def make_v1_handler(cfg):
    return create_v1_handler(cfg)

handler_factory = make_v1_handler
```

### Memory Considerations

Each process has its own memory space:
- **Benefit**: No shared state conflicts
- **Cost**: Memory usage scales with workers (each loads data)
- **Mitigation**: Limit `max_workers` based on available RAM

**Rule of thumb**: 
- 16GB RAM: max_workers = 4
- 32GB RAM: max_workers = 8

### Error Handling

Handle per-security failures gracefully:

```python
for future in as_completed(future_to_sheet):
    sheet_name = future_to_sheet[future]
    try:
        security, result = future.result()
        results[security] = result
    except Exception as e:
        print(f"✗ Error processing {sheet_name}: {e}")
        # Log but continue with other securities
        results[sheet_name] = {'error': str(e)}
```

## Performance Expectations

### Theoretical Speedup

| CPU Cores | Workers | Expected Speedup | 8min → |
|-----------|---------|------------------|--------|
| 2         | 2       | 1.8x            | 4.4min |
| 4         | 4       | 3.5x            | 2.3min |
| 8         | 8       | 6.5x            | 1.2min |
| 16        | 16      | 12x             | 40sec  |

**Note**: Assumes I/O is not bottleneck and overhead is minimal

### Profiling Points

Add timing to identify actual bottlenecks:

```python
import time

# Time data loading
t0 = time.time()
wb = openpyxl.load_workbook(file_path, read_only=True)
sheet_names = wb.sheetnames
wb.close()
print(f"Sheet discovery: {time.time() - t0:.2f}s")

# Time processing
t0 = time.time()
results = run_parallel_backtest(...)
print(f"Processing: {time.time() - t0:.2f}s")

# Time I/O
t0 = time.time()
write_results(results, output_dir)
print(f"Writing results: {time.time() - t0:.2f}s")
```

## Migration Path

### Phase 1: Create Parallel Module
1. Create `src/parallel_backtest.py` with functions above
2. Add `scripts/run_parallel_backtest.py` wrapper
3. Test with `max_sheets=5` to validate

### Phase 2: Validate Results
1. Run sequential and parallel versions
2. Compare outputs (trade counts, P&L, positions)
3. Verify results are identical

### Phase 3: Integrate
1. Update `run_strategy.py` with `--parallel` flag
2. Update `comprehensive_sweep.py` for parallel sweeps
3. Add to documentation

### Phase 4: Optimize
1. Profile to find remaining bottlenecks
2. Consider pre-converting Excel to Parquet
3. Fine-tune worker count for your hardware

## Alternative: Data Preprocessing

For maximum performance, convert Excel once:

```python
# scripts/convert_excel_to_parquet.py
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

def convert_excel_to_parquet(excel_path: str, output_dir: str):
    """Convert Excel sheets to per-security Parquet files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    xls = pd.ExcelFile(excel_path)
    for sheet_name in xls.sheet_names:
        print(f"Converting {sheet_name}...")
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
        
        security = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
        parquet_file = output_path / f"{security.lower()}.parquet"
        df.to_parquet(parquet_file, compression='snappy', index=False)
        print(f"  → {parquet_file}")

# Usage:
convert_excel_to_parquet('data/raw/TickData.xlsx', 'data/parquet/')

# Then in backtest:
df = pd.read_parquet(f'data/parquet/{security.lower()}.parquet')
```

**Benefits**:
- 5-10x faster I/O than Excel
- Direct parallel read (no sheet conflicts)
- Columnar format optimized for analytics

## Summary

**Best approach for this codebase**: Per-security process parallelization

**Implementation steps**:
1. Create `src/parallel_backtest.py` (2-3 hours)
2. Test with small dataset (30 min)
3. Validate against sequential (1 hour)
4. Benchmark and tune (1 hour)

**Expected outcome**: 3-4x speedup on typical hardware (8-10 min → 2-3 min)

**Next-level optimization**: Pre-convert Excel to Parquet → 10-20x total speedup
