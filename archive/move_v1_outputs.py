"""Move v1 baseline output files to organized folder."""
import os
import shutil
from pathlib import Path

output_dir = Path("output")
v1_baseline_dir = output_dir / "v1_baseline"

# Ensure destination exists
v1_baseline_dir.mkdir(exist_ok=True)

# Files to move
patterns = [
    "*_inventory_pnl.png",
    "*_trades_timeseries.csv",
]
specific_files = [
    "backtest_summary.csv",
    "performance_summary.csv", 
    "run_log.txt"
]

moved_count = 0

# Move files matching patterns
for pattern in patterns:
    for file_path in output_dir.glob(pattern):
        if file_path.is_file():
            dest = v1_baseline_dir / file_path.name
            shutil.move(str(file_path), str(dest))
            print(f"Moved: {file_path.name}")
            moved_count += 1

# Move specific files
for filename in specific_files:
    file_path = output_dir / filename
    if file_path.exists():
        dest = v1_baseline_dir / filename
        shutil.move(str(file_path), str(dest))
        print(f"Moved: {filename}")
        moved_count += 1

print(f"\nTotal files moved: {moved_count}")
