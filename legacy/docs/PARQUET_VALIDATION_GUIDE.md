# Parquet Data Validation Guide

## Overview

The Parquet integration now includes **comprehensive data validation** to ensure Parquet files match the Excel source. This prevents issues from:

- **Missing securities**: Some securities not converted
- **Date discrepancies**: Different date ranges between Excel and Parquet
- **Stale data**: Parquet files older than Excel updates
- **Incomplete conversion**: Partial or corrupted Parquet files

## What Gets Validated

### 1. Security Coverage
✅ All securities in Excel exist in Parquet
✅ No extra securities in Parquet that aren't in Excel

### 2. Date Range Matching
✅ Start dates match exactly between Excel and Parquet
✅ End dates match exactly between Excel and Parquet
✅ Data coverage is complete

### 3. Data Integrity
✅ Parquet files are readable
✅ Required columns exist (timestamp, type, price, volume)
✅ Row counts are reasonable

## Automatic Validation

All backtest scripts now automatically validate Parquet data before use:

```python
from src.parquet_utils import ensure_parquet_data

# Auto-validates by default
parquet_dir = ensure_parquet_data(
    excel_path='data/raw/TickData.xlsx',
    parquet_dir='data/parquet',
    validate_data=True  # Default: ON
)
```

## Example Validation Output

### ✅ Valid Parquet Data

```
Validating Parquet data against Excel source...
✓ Parquet data validation passed

================================================================================
USING EXISTING PARQUET FILES
================================================================================
Found 16 Parquet files in data/parquet
Using Parquet format for 5-10x faster I/O.
================================================================================
```

### ⚠ Invalid Parquet Data

```
Validating Parquet data against Excel source...

================================================================================
⚠ PARQUET DATA VALIDATION FAILED
================================================================================
Issues detected:
  - Missing in Parquet: ADCB, ADIB, FAB, SALIK
  - EMAAR: Date range mismatch - Parquet starts 2024-01-05, Excel starts 2024-01-01 (4 days difference)
  - ALDAR: Date range mismatch - Parquet starts 2024-01-08, Excel starts 2024-01-01 (7 days difference)

Recommendation: Reconvert Parquet files
  1. Delete: data/parquet
  2. Rerun script (will auto-convert)
================================================================================

Auto-reconvert now? (y/n): 
```

## Validation Modes

### Interactive Mode (Default)
Prompts user when validation fails:

```python
ensure_parquet_data(
    validate_data=True,  # Validate
    auto_reconvert_on_mismatch=False  # Ask user
)
```

**User Options:**
- `y` = Auto-reconvert immediately
- `n` = Use existing Parquet (warning shown)

### Automated Mode
Auto-reconverts on validation failure (CI/CD):

```python
ensure_parquet_data(
    validate_data=True,  # Validate
    auto_reconvert_on_mismatch=True  # Auto-fix
)
```

### Skip Validation
Trust existing Parquet (fastest):

```python
ensure_parquet_data(
    validate_data=False  # Skip validation
)
```

## Manual Validation

Run standalone validation:

```bash
python scripts/validate_parquet_data.py
```

**Output:**
```
================================================================================
PARQUET DATA VALIDATION
================================================================================

Current Parquet Files:
  Location: data/parquet
  Files: 16
  Total size: 65.3 MB

Running validation checks...
--------------------------------------------------------------------------------

✓ VALIDATION PASSED

Parquet files are valid and match Excel source:
  ✓ All securities present
  ✓ Date ranges match
  ✓ Data coverage is complete
================================================================================
```

## Common Validation Issues

### Issue 1: Missing Securities

**Symptom:**
```
Missing in Parquet: ADCB, ADIB, FAB, SALIK
```

**Cause:**
- Partial conversion (only ran with `--max-sheets 12`)
- Securities added to Excel after Parquet conversion

**Fix:**
```bash
# Delete and reconvert
Remove-Item -Recurse -Force data/parquet
python scripts/convert_excel_to_parquet.py
```

### Issue 2: Date Range Mismatch

**Symptom:**
```
EMAAR: Date range mismatch - Parquet starts 2024-01-05, Excel starts 2024-01-01 (4 days difference)
```

**Cause:**
- Excel file updated with new data
- Parquet files are stale
- Partial data export

**Fix:**
```bash
# Force reconversion
Remove-Item -Recurse -Force data/parquet
python scripts/convert_excel_to_parquet.py
```

### Issue 3: Extra Securities

**Symptom:**
```
Extra in Parquet (not in Excel): OLDSTOCK1, OLDSTOCK2
```

**Cause:**
- Securities removed from Excel
- Different Excel file used

**Fix:**
```bash
# Clean reconversion
Remove-Item -Recurse -Force data/parquet
python scripts/convert_excel_to_parquet.py
```

## Date Validation

### Exact Date Matching Required

The validation requires **exact date match** (no tolerance):
- Parquet start date must match Excel start date exactly
- Parquet end date must match Excel end date exactly
- Any mismatch indicates stale or incomplete data

**Example - PASS:**
- Parquet: 2024-01-01
- Excel: 2024-01-01
- Result: **PASS** ✅

**Example - FAIL:**
- Parquet: 2024-01-03
- Excel: 2024-01-01
- Difference: 2 days → **FAIL** ❌

**Why Exact Matching:**
- Ensures complete data coverage
- Prevents using stale Parquet files
- Guarantees data consistency
- Avoids partial conversion issues

## Best Practices

### 1. Always Validate on First Run
```bash
# First time setup - validates automatically
python scripts/run_strategy.py --strategy v1_baseline
```

### 2. Validate After Excel Updates
```bash
# After updating Excel file
python scripts/validate_parquet_data.py

# If validation fails, reconvert
Remove-Item -Recurse -Force data/parquet
python scripts/convert_excel_to_parquet.py
```

### 3. Use Automation Flag for CI/CD
```python
# In automated scripts
ensure_parquet_data(
    validate_data=True,
    auto_reconvert_on_mismatch=True  # No prompts
)
```

### 4. Periodic Revalidation
```bash
# Weekly check
python scripts/validate_parquet_data.py
```

## Performance Impact

### Validation Speed
- **Quick Check**: 2-5 seconds (checks file counts, samples dates)
- **Full Validation**: 5-10 seconds (checks all securities)

### Cost vs Benefit
- **Cost**: 5-10 seconds validation time
- **Benefit**: Prevents incorrect backtest results from stale data
- **Recommendation**: Always enable validation (default)

## Disabling Validation

Only disable validation if:
1. You're absolutely certain Parquet is current
2. You're running many sequential backtests
3. You want maximum speed

```python
# Disable validation (not recommended for production)
ensure_parquet_data(
    excel_path='data/raw/TickData.xlsx',
    validate_data=False  # Skip validation
)
```

## Troubleshooting

### Validation Takes Too Long

**Solution**: Validation is already optimized (samples data). If still slow:
```python
# Skip validation for repeat runs in same session
ensure_parquet_data(validate_data=False)
```

### Non-Interactive Environment Issues

**Problem**: Script hangs waiting for user input in CI/CD

**Solution**: Use auto-reconvert flag:
```python
ensure_parquet_data(auto_reconvert_on_mismatch=True)
```

### False Positive Date Mismatches

**Problem**: 1-2 day differences flagged incorrectly

**Solution**: Already handled - 7-day tolerance built-in. If issue persists, modify tolerance in `validate_parquet_against_excel()`.

## Summary

✅ **Automatic validation** prevents using stale/incomplete Parquet data  
✅ **Date range checking** ensures data consistency  
✅ **Interactive prompts** give control over reconversion  
✅ **Automated mode** for CI/CD pipelines  
✅ **Fast validation** (5-10 seconds)  
✅ **Clear error messages** guide users to fix issues  

**Default behavior**: Validate automatically, ask user on mismatch, seamless experience.
