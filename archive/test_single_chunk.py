"""Test ADNOCGAS with single large chunk (all data at once)."""

from scripts.run_mm_backtest import run_mm_backtest

print("Testing ADNOCGAS with SINGLE LARGE CHUNK (1,000,000 rows)...")
print("=" * 80)
print("This will process all ADNOCGAS data in one chunk, avoiding mid-day splits")
print("=" * 80 + "\n")

result = run_mm_backtest(
    excel_file='data/raw/TickData.xlsx',
    config_file='configs/mm_config.json',
    generate_plots=False,
    chunk_size=1000000,  # Large enough to get all ADNOCGAS (617k rows) in one chunk
    max_sheets=4  # Stop after ADNOCGAS
)

adnocgas = result.get('ADNOCGAS', {})
market_days = len(adnocgas.get('market_dates', set()))
trading_days = len(set(t['timestamp'].date() for t in adnocgas.get('trades', [])))
total_trades = len(adnocgas.get('trades', []))
coverage = (trading_days / market_days * 100) if market_days > 0 else 0

print("\n" + "=" * 80)
print("ADNOCGAS RESULT WITH SINGLE CHUNK:")
print("  Market days:", market_days)
print("  Trading days:", trading_days)
print(f"  Coverage: {coverage:.1f}%")
print("  Total trades:", total_trades)
print("=" * 80)
print("\nCompare to chunked result (100k rows): 76/136 days = 55.9%, 1050 trades")
