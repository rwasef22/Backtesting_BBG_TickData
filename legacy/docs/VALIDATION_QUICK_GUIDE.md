# Quick Validation Guide

**Fast reference for validating backtest implementations**

## 🚀 Quick Start (5 minutes)

### 1. Run Automated Test
```bash
# This will run both sequential and parallel, then compare
python scripts/test_parallel_backtest.py
```

**Expected Output**:
- ✅ ALL TESTS PASSED
- Trade counts match
- P&L matches
- ~2-4x speedup reported

---

### 2. Detailed Comparison
```bash
# Per-security validation with logging
python scripts/test_parallel_backtest.py --detailed --max-sheets 5

# Check log file for details
cat test_parallel_backtest.log
```

---

### 3. Compare Existing Results
```bash
# If you already have output directories
python scripts/validate_backtest_results.py output/sequential output/parallel

# Export detailed report
python scripts/validate_backtest_results.py output/sequential output/parallel --report comparison.csv
```

---

## 📊 What Gets Validated

### Automatic Checks
- ✓ Trade count (exact match required)
- ✓ P&L values (0.01 AED tolerance)
- ✓ Positions (0.1 share tolerance)
- ✓ Trade sides (buy/sell exact match)
- ✓ Timestamps (millisecond precision)
- ✓ Fill prices (0.0001 tolerance)
- ✓ Fill quantities (exact match)

### Performance Checks
- ⚡ Runtime (parallel should be 2-4x faster)
- 💾 Memory usage (should not exceed 2GB)
- 📈 Scalability (speedup increases with more securities)

---

## 🔍 Interpreting Results

### Perfect Match ✅
```
✓ ADNOCGAS: 1,234 trades, P&L=15,432.50
✓ EMAAR: 987 trades, P&L=8,901.23
✓ ALL TESTS PASSED
```
**Action**: Approved for production use

---

### Acceptable Differences ⚠️
```
⚠ ADNOCGAS: ACCEPTABLE (within tolerance)
    Max P&L diff: 0.0087 AED
```
**Reason**: Floating-point rounding in parallel aggregation
**Action**: Acceptable if < 0.01 AED per security

---

### Failed Validation ❌
```
❌ ADNOCGAS: FAILED
    - Trade count mismatch: 1234 vs 1235
    - Position mismatch at trade 567
```
**Reason**: Logic bug or state management issue
**Action**: Fix code, re-validate

---

## 🛠️ Common Issues & Fixes

### Issue: "Trade count mismatch"
**Cause**: Different handling of edge cases (time windows, liquidity checks)
**Fix**: Review handler logic, ensure identical conditions

### Issue: "Timestamp mismatches"
**Cause**: Different chunk boundaries or processing order
**Fix**: Verify orderbook state is identical at each chunk

### Issue: "P&L difference > tolerance"
**Cause**: Accumulation of floating-point errors or different fill sequencing
**Fix**: Check queue simulation logic, ensure FIFO order preserved

### Issue: "Parallel slower than sequential"
**Cause**: Too few securities, overhead dominates, or disk I/O bottleneck
**Fix**: Test with more securities (10+), consider Parquet for I/O

---

## 📁 Output Files

### Test Script Generates:
- `test_parallel_backtest.log` - Detailed execution log
- `output/test_seq/` - Sequential results (if --export-sequential)
- `output/test_par/` - Parallel results (if --export-parallel)

### Validation Script Generates:
- `validation_report.csv` - Per-security comparison (if --report)
- Terminal output with summary statistics

---

## ⚙️ Advanced Validation

### Export Results for Manual Review
```bash
# Run tests with export
python scripts/test_parallel_backtest.py \
  --detailed \
  --max-sheets 10 \
  --export-sequential output/seq_test \
  --export-parallel output/par_test

# Then compare manually
diff output/seq_test/adnocgas_trades_timeseries.csv output/par_test/adnocgas_trades_timeseries.csv
```

### Test Specific Securities
```bash
python scripts/validate_backtest_results.py \
  output/sequential output/parallel \
  --securities ADNOCGAS EMAAR FAB \
  --detailed
```

### Custom Tolerances
```bash
# Stricter validation (production)
python scripts/validate_backtest_results.py \
  output/seq output/par \
  --tolerance-pnl 0.001 \
  --tolerance-price 0.00001

# Looser validation (development)
python scripts/validate_backtest_results.py \
  output/seq output/par \
  --tolerance-pnl 1.0 \
  --tolerance-price 0.01
```

---

## 🎯 Validation Workflow

```
1. Quick Smoke Test (3 securities, 2 min)
   ↓ PASS
2. Automated Test (5 securities, 5 min)
   ↓ PASS
3. Full Validation (16 securities, 20 min)
   ↓ PASS
4. Performance Benchmark
   ↓ 2-4x speedup confirmed
5. ✅ APPROVED FOR PRODUCTION
```

---

## 📞 Troubleshooting Checklist

If tests fail:

1. [ ] Check log file: `test_parallel_backtest.log`
2. [ ] Verify same config used for both runs
3. [ ] Ensure data file hasn't changed
4. [ ] Check Python environment (same packages)
5. [ ] Run on smaller dataset to isolate issue
6. [ ] Enable detailed logging in handlers
7. [ ] Compare orderbook state at failure point
8. [ ] Verify no threading/race conditions

---

## 📚 Related Documentation

- **Full Checklist**: [`VALIDATION_CHECKLIST.md`](VALIDATION_CHECKLIST.md)
- **Parallel Guide**: [`PARALLELIZATION_GUIDE.md`](PARALLELIZATION_GUIDE.md)
- **Parquet Guide**: [`PARQUET_GUIDE.md`](PARQUET_GUIDE.md)
- **Technical Docs**: [`STRATEGY_TECHNICAL_DOCUMENTATION.md`](STRATEGY_TECHNICAL_DOCUMENTATION.md)

---

## ✅ Sign-Off Template

After validation, document results:

```
Validation Date: ______
Version: Sequential + Parallel + Parquet
Test Coverage: Level 1-3 (smoke + automated + deep)
Result: ✅ PASS / ❌ FAIL
Speedup: ___x
Issues: None / Minor / Major
Approved By: ______
```

**Ready for production if**:
- All tests PASS
- Speedup ≥ 2x
- No critical issues
- Full checklist complete
