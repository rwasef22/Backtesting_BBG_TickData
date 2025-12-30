@echo off
cd /d "C:\Ray\VS Code\tick-backtest-project\output"
move *_inventory_pnl.png v1_baseline\ 2>nul
move *_trades_timeseries.csv v1_baseline\ 2>nul
move backtest_summary.csv v1_baseline\ 2>nul
move performance_summary.csv v1_baseline\ 2>nul
move run_log.txt v1_baseline\ 2>nul
echo Files moved successfully!
dir v1_baseline /b | find /c /v ""
