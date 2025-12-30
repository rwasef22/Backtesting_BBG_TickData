"""Monitor parameter sweep progress and run comparison when both complete."""

import time
from pathlib import Path
import subprocess
import sys


def check_sweep_complete(sweep_dir: Path, strategy_name: str) -> bool:
    """Check if a parameter sweep has completed."""
    if strategy_name == 'v1':
        comparison_file = sweep_dir / 'interval_comparison.csv'
    else:
        comparison_file = sweep_dir / 'v2_interval_comparison.csv'
    
    return comparison_file.exists()


def main():
    print("="*80)
    print("MONITORING PARAMETER SWEEPS")
    print("="*80)
    print("\nWaiting for both v1 and v2 sweeps to complete...")
    print("This typically takes 30-40 minutes per sweep.")
    print("\nChecking every 30 seconds...")
    
    v1_dir = Path('output/parameter_sweep')
    v2_dir = Path('output/v2_parameter_sweep')
    
    v1_done = False
    v2_done = False
    check_count = 0
    
    while not (v1_done and v2_done):
        time.sleep(30)
        check_count += 1
        
        v1_done = check_sweep_complete(v1_dir, 'v1')
        v2_done = check_sweep_complete(v2_dir, 'v2')
        
        elapsed_min = check_count * 0.5
        print(f"\n[{elapsed_min:.1f} min] Status:")
        print(f"  V1 Baseline: {'✓ COMPLETE' if v1_done else '⏳ Running...'}")
        print(f"  V2 Price Follow: {'✓ COMPLETE' if v2_done else '⏳ Running...'}")
        
        if v1_done and v2_done:
            print("\n" + "="*80)
            print("BOTH SWEEPS COMPLETE!")
            print("="*80)
            break
    
    # Run comparison
    print("\nRunning comparison analysis...")
    result = subprocess.run(
        [sys.executable, 'scripts/compare_v1_v2_sweeps.py'],
        capture_output=False,
        text=True
    )
    
    if result.returncode == 0:
        print("\n" + "="*80)
        print("ALL DONE!")
        print("="*80)
    else:
        print("\nComparison script failed. You can run it manually:")
        print("  python scripts/compare_v1_v2_sweeps.py")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMonitoring interrupted. You can run comparison manually when sweeps complete:")
        print("  python scripts/compare_v1_v2_sweeps.py")
