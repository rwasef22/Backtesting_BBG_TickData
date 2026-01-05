# Backtest Validation Checklist

This checklist ensures comprehensive validation of backtest implementations (parallel, Parquet, etc.) against the sequential baseline.

## Pre-Validation Setup

### Environment Check
- [ ] Python environment activated
- [ ] All dependencies installed (`pandas`, `openpyxl`, `pyarrow` if using Parquet)
- [ ] Data files accessible (`data/raw/TickData.xlsx` or `data/parquet/`)
- [ ] Config files present (`configs/v1_baseline_config.json`, etc.)

### Baseline Reference
- [ ] Sequential backtest runs successfully
- [ ] Sequential results saved to known location (e.g., `output/sequential_reference/`)
- [ ] Sequential log files reviewed for any warnings/errors

---

## Level 1: Quick Smoke Test (5 minutes)

**Purpose**: Verify basic functionality before deep validation

### Run Commands
```bash
# Sequential reference (3 securities)
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 3

# Parallel test
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 3

# Parquet test (if converted)
python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 3
```

### Checks
- [ ] All versions complete without errors
- [ ] All versions process same securities (check output)
- [ ] Runtime as expected (parallel ~50% of sequential with 2 cores)
- [ ] Output directories created with expected files

**Status**: PASS / FAIL
**Notes**: _____________

---

## Level 2: Automated Test Suite (10 minutes)

**Purpose**: Automated comparison of results

### Run Test Script
```bash
# Basic test (5 securities, aggregate comparison)
python scripts/test_parallel_backtest.py

# Detailed test (per-security comparison)
python scripts/test_parallel_backtest.py --detailed --max-sheets 5

# Export for manual review
python scripts/test_parallel_backtest.py --export-sequential output/test_seq --export-parallel output/test_par
```

### Checks
- [ ] Test script completes successfully
- [ ] Trade counts match between versions
- [ ] P&L totals match (within tolerance)
- [ ] No errors in log file (`test_parallel_backtest.log`)
- [ ] Per-security results match (if `--detailed` used)

**Test Output Summary**:
- Trade count match: YES / NO
- P&L match: YES / NO (tolerance: 1 AED)
- Speedup achieved: ___x
- Securities with issues: ___

**Status**: PASS / FAIL
**Notes**: _____________

---

## Level 3: Deep Validation (30 minutes)

**Purpose**: Comprehensive comparison of all output files

### 3.1 Trade-Level Comparison

**Run Validation Script**:
```bash
# Compare full output directories
python scripts/validate_backtest_results.py output/sequential_reference output/parallel_test

# Detailed trade-by-trade
python scripts/validate_backtest_results.py output/sequential_reference output/parallel_test --detailed

# Export report
python scripts/validate_backtest_results.py output/sequential_reference output/parallel_test --report validation_report.csv
```

### Checks for Each Security
- [ ] Exact trade count match
- [ ] Timestamp alignment (all trades at same times)
- [ ] Side match (buy/sell) for every trade
- [ ] Fill price match (within 0.0001 tolerance)
- [ ] Fill quantity exact match (no partial trade differences)
- [ ] Realized P&L match per trade (within 0.01 AED)
- [ ] Cumulative P&L trajectory match
- [ ] Position match at every trade
- [ ] Entry price tracking consistent

**Validation Report Summary**:
- Perfect matches: ___ / ___
- Acceptable differences: ___ / ___
- Failures: ___ / ___

**Status**: PASS / FAIL
**Notes**: _____________

---

### 3.2 Summary Metrics Comparison

**Manual Check**:
```bash
# If backtest_summary.csv exists
# Compare: Total P&L, trade counts, dates traded
```

### Metrics to Compare
- [ ] Total realized P&L (aggregate)
- [ ] Total trades (aggregate)
- [ ] Number of trading days per security
- [ ] Average trades per day
- [ ] Max position reached per security
- [ ] Final position (should be 0 for all)

**Status**: PASS / FAIL
**Notes**: _____________

---

### 3.3 Edge Cases & Special Scenarios

**Check Specific Situations**:
- [ ] Securities with zero trades (both should have 0)
- [ ] EOD position flattening (position = 0 at end of day)
- [ ] Date boundary handling (orderbook cleared between dates)
- [ ] High-frequency securities (ADNOCGAS, EMAAR) match
- [ ] Low-frequency securities match
- [ ] Partial fills handled identically
- [ ] Queue simulation consistency

**Status**: PASS / FAIL
**Notes**: _____________

---

## Level 4: Performance Validation (15 minutes)

**Purpose**: Verify performance gains are as expected

### 4.1 Timing Benchmarks

**Run Benchmarks**:
```bash
# Sequential baseline
time python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5

# Parallel version
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 5 --benchmark
```

### Performance Metrics
- Sequential time: ___ seconds
- Parallel time: ___ seconds
- Speedup: ___x (expected: 2-4x with 4 cores)
- Throughput: ___ rows/sec
- Memory usage: ___ MB

### Checks
- [ ] Speedup within expected range (2-4x for 4 cores)
- [ ] Memory usage reasonable (< 2GB)
- [ ] No excessive disk I/O
- [ ] CPU utilization ~100% during processing

**Status**: PASS / FAIL
**Notes**: _____________

---

### 4.2 Scalability Test

**Test with Increasing Load**:
```bash
# 3 securities
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 3

# 5 securities
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 5

# 10 securities
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 10

# All 16 securities
python scripts/run_parallel_backtest.py --strategy v1_baseline
```

### Checks
- [ ] Speedup scales with number of securities
- [ ] No degradation with larger datasets
- [ ] Memory usage grows linearly (not exponentially)
- [ ] No resource exhaustion

**Status**: PASS / FAIL
**Notes**: _____________

---

## Level 5: Parquet Validation (if applicable)

**Purpose**: Validate Parquet conversion and processing

### 5.1 Conversion Validation

**Run Conversion**:
```bash
pip install pyarrow
python scripts/convert_excel_to_parquet.py --max-sheets 5
```

### Checks
- [ ] All sheets converted successfully
- [ ] Parquet files created in `data/parquet/`
- [ ] File sizes reasonable (~50% of Excel)
- [ ] No data loss during conversion (row counts match)
- [ ] Column names normalized correctly
- [ ] Date/time handling correct

**Status**: PASS / FAIL
**Notes**: _____________

---

### 5.2 Parquet Backtest Validation

**Run Parquet Backtest**:
```bash
python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5
```

**Compare Against Excel Baseline**:
```bash
# Export both
python scripts/run_strategy.py --strategy v1_baseline --max-sheets 5  # Excel sequential
python scripts/run_parquet_backtest.py --strategy v1_baseline --max-sheets 5  # Parquet

# Compare
python scripts/validate_backtest_results.py output/v1_baseline output/v1_baseline --detailed
```

### Checks
- [ ] Parquet results identical to Excel
- [ ] All trade counts match
- [ ] All P&L values match
- [ ] Performance gain achieved (5-10x I/O improvement)
- [ ] No missing data in Parquet files

**Performance**:
- Excel parallel time: ___ seconds
- Parquet parallel time: ___ seconds
- Speedup: ___x (expected: 5-10x I/O + 3-4x parallel = 8-15x total)

**Status**: PASS / FAIL
**Notes**: _____________

---

## Level 6: Stress & Reliability Testing

**Purpose**: Ensure robustness under various conditions

### 6.1 Repeated Runs

**Run Multiple Times**:
```bash
# Run 3 times, verify deterministic results
python scripts/run_parallel_backtest.py --strategy v1_baseline --max-sheets 3
```

### Checks
- [ ] Results identical across multiple runs
- [ ] No random variation in trade execution
- [ ] Deterministic orderbook updates
- [ ] Consistent P&L calculation

**Status**: PASS / FAIL
**Notes**: _____________

---

### 6.2 Error Handling

**Test Error Scenarios**:
```bash
# Invalid strategy
python scripts/run_parallel_backtest.py --strategy invalid_strategy

# Missing data file
python scripts/run_parallel_backtest.py --strategy v1_baseline --data-file nonexistent.xlsx

# Invalid config
# (temporarily rename config file and run)
```

### Checks
- [ ] Graceful error messages (no cryptic stack traces)
- [ ] Proper cleanup on error
- [ ] No partial/corrupted output files
- [ ] Clear user guidance on fixing errors

**Status**: PASS / FAIL
**Notes**: _____________

---

## Final Checklist Summary

| Level | Test | Status | Issues |
|-------|------|--------|--------|
| 1 | Quick Smoke Test | ☐ PASS ☐ FAIL | |
| 2 | Automated Test Suite | ☐ PASS ☐ FAIL | |
| 3.1 | Trade-Level Comparison | ☐ PASS ☐ FAIL | |
| 3.2 | Summary Metrics | ☐ PASS ☐ FAIL | |
| 3.3 | Edge Cases | ☐ PASS ☐ FAIL | |
| 4.1 | Timing Benchmarks | ☐ PASS ☐ FAIL | |
| 4.2 | Scalability Test | ☐ PASS ☐ FAIL | |
| 5.1 | Parquet Conversion | ☐ PASS ☐ FAIL | |
| 5.2 | Parquet Backtest | ☐ PASS ☐ FAIL | |
| 6.1 | Repeated Runs | ☐ PASS ☐ FAIL | |
| 6.2 | Error Handling | ☐ PASS ☐ FAIL | |

---

## Overall Validation Result

**Status**: ☐ APPROVED FOR PRODUCTION ☐ NEEDS FIXES ☐ MAJOR ISSUES

**Confidence Level**: ☐ HIGH ☐ MEDIUM ☐ LOW

**Approval**: _______________  **Date**: _______________

---

## Known Issues / Limitations

_Document any known issues, acceptable differences, or limitations:_

1. ____________________________________________________________
2. ____________________________________________________________
3. ____________________________________________________________

---

## Recommendations

**Immediate Actions**:
- [ ] _______________________________________________________
- [ ] _______________________________________________________

**Future Improvements**:
- [ ] _______________________________________________________
- [ ] _______________________________________________________

---

## Sign-Off

**Validated By**: _______________
**Date**: _______________
**Version**: Sequential + Parallel + Parquet
**Commit Hash**: _______________

**Notes**: 
_____________________________________________________________________
_____________________________________________________________________
_____________________________________________________________________
