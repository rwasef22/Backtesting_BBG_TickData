#!/usr/bin/env python3
"""
Generate performance summary plots for closing strategy sweep results.
"""

import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def generate_sweep_summary(sweep_dir: str, output_name: str = 'performance_summary.png'):
    """Generate a summary plot for sweep results."""
    
    # Find the sweep results file
    sweep_file = None
    
    for f in os.listdir(sweep_dir):
        if f == 'sweep_all_results.csv':
            sweep_file = os.path.join(sweep_dir, f)
            break
    
    if not sweep_file:
        print(f"  No sweep_all_results.csv found in {sweep_dir}")
        return
    
    # Load data
    df = pd.read_csv(sweep_file)
    
    # Detect parameter column (not security, pnl, trades, etc.)
    param_col = None
    skip_cols = ['security', 'pnl', 'trades', 'auction_entries', 'vwap_exits', 
                 'stop_losses', 'eod_flattens', 'buy_entries', 'sell_entries',
                 'filtered_sell_entries', 'param_value']
    
    for col in df.columns:
        if col not in skip_cols:
            if 'spread' in col.lower() or 'period' in col.lower() or 'threshold' in col.lower():
                param_col = col
                break
    
    if param_col is None:
        param_col = 'param_value' if 'param_value' in df.columns else df.columns[1]
    
    param_values = sorted(df[param_col].unique())
    securities = df['security'].unique()
    
    # For security-based cumulative, calculate once
    best_pnl_by_security = df.groupby('security')['pnl'].max()
    securities_sorted = best_pnl_by_security.sort_values(ascending=False).index.tolist()
    
    # Create figure with 7 panels (3 rows)
    fig = plt.figure(figsize=(18, 16))
    
    # Panel 1: Cumulative P&L across securities (one curve per parameter)
    ax1 = fig.add_subplot(3, 1, 1)
    
    colors_cycle = plt.cm.tab10.colors
    for idx, param_val in enumerate(param_values):
        param_df = df[df[param_col] == param_val].set_index('security')
        pnl_ordered = [param_df.loc[sec, 'pnl'] if sec in param_df.index else 0 for sec in securities_sorted]
        cumulative_pnl = np.cumsum(pnl_ordered) / 1000
        ax1.plot(range(len(securities_sorted)), cumulative_pnl, 
                marker='o', markersize=4, label=f'{param_col}={param_val}',
                color=colors_cycle[idx % len(colors_cycle)], linewidth=2)
    
    ax1.set_xticks(range(len(securities_sorted)))
    ax1.set_xticklabels(securities_sorted, rotation=45, ha='right', fontsize=9)
    ax1.set_xlabel('Securities (sorted by best P&L)')
    ax1.set_ylabel('Cumulative P&L (K AED)')
    ax1.set_title('Cumulative P&L Across Securities by Parameter Value', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='black', linewidth=0.5)
    
    # Panel 2: Total P&L by Parameter Value
    ax2 = fig.add_subplot(3, 3, 4)
    total_pnl_by_param = df.groupby(param_col)['pnl'].sum()
    colors = ['green' if p >= 0 else 'red' for p in total_pnl_by_param.values]
    bars = ax2.bar([str(v) for v in total_pnl_by_param.index], total_pnl_by_param.values / 1000, 
                   color=colors, alpha=0.7, edgecolor='black')
    ax2.set_title(f'Total P&L by {param_col}', fontsize=12, fontweight='bold')
    ax2.set_xlabel(param_col)
    ax2.set_ylabel('Total P&L (K AED)')
    ax2.axhline(y=0, color='black', linewidth=0.5)
    ax2.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars, total_pnl_by_param.values):
        ax2.annotate(f'{val/1000:.0f}K', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords='offset points', ha='center', fontsize=9)
    
    # Panel 3: P&L by Security (best param for each)
    ax3 = fig.add_subplot(3, 3, 5)
    pnl_values = [best_pnl_by_security[s] / 1000 for s in securities_sorted]
    colors = ['green' if p >= 0 else 'red' for p in pnl_values]
    ax3.barh(securities_sorted, pnl_values, color=colors, alpha=0.7, edgecolor='black')
    ax3.set_title('Best P&L by Security', fontsize=12, fontweight='bold')
    ax3.set_xlabel('P&L (K AED)')
    ax3.axvline(x=0, color='black', linewidth=0.5)
    ax3.grid(True, alpha=0.3, axis='x')
    
    # Panel 4: Trades by Parameter Value
    ax4 = fig.add_subplot(3, 3, 6)
    total_trades_by_param = df.groupby(param_col)['trades'].sum()
    ax4.bar([str(v) for v in total_trades_by_param.index], total_trades_by_param.values, 
            color='steelblue', alpha=0.7, edgecolor='black')
    ax4.set_title(f'Total Trades by {param_col}', fontsize=12, fontweight='bold')
    ax4.set_xlabel(param_col)
    ax4.set_ylabel('Total Trades')
    ax4.grid(True, alpha=0.3, axis='y')
    
    # Panel 5: Heatmap of P&L by Security x Parameter
    ax5 = fig.add_subplot(3, 3, 7)
    pivot = df.pivot(index='security', columns=param_col, values='pnl')
    pivot = pivot.reindex(securities_sorted)  # Sort by best P&L
    im = ax5.imshow(pivot.values / 1000, aspect='auto', cmap='RdYlGn')
    ax5.set_xticks(range(len(param_values)))
    ax5.set_xticklabels([str(v) for v in param_values])
    ax5.set_yticks(range(len(securities_sorted)))
    ax5.set_yticklabels(securities_sorted, fontsize=8)
    ax5.set_xlabel(param_col)
    ax5.set_title('P&L Heatmap (K AED)', fontsize=12, fontweight='bold')
    plt.colorbar(im, ax=ax5, label='P&L (K AED)')
    
    # Panel 6: Summary Statistics Table
    ax6 = fig.add_subplot(3, 3, 8)
    ax6.axis('off')
    
    best_param = total_pnl_by_param.idxmax()
    best_total_pnl = total_pnl_by_param.max()
    total_securities = len(securities)
    
    # Calculate optimal per-security sum
    optimal_pnl = df.groupby('security')['pnl'].max().sum()
    
    stats_data = [
        ['Parameter Swept', param_col],
        ['Parameter Values', ', '.join(str(v) for v in param_values)],
        ['Securities', str(total_securities)],
        ['Best Uniform Param', str(best_param)],
        ['Best Uniform P&L', f'{best_total_pnl:,.0f} AED'],
        ['Optimal (per-sec)', f'{optimal_pnl:,.0f} AED'],
        ['Improvement', f'{optimal_pnl - best_total_pnl:,.0f} AED'],
    ]
    
    table = ax6.table(cellText=stats_data, colLabels=['Metric', 'Value'],
                      loc='center', cellLoc='left', colWidths=[0.4, 0.5])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)
    for i in range(2):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(color='white', fontweight='bold')
    for i in range(1, len(stats_data) + 1):
        for j in range(2):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#E6F0FF')
    ax6.set_title('Sweep Summary', fontsize=12, fontweight='bold', pad=20)
    
    # Panel 7: Optimal Parameter per Security
    ax7 = fig.add_subplot(3, 3, 9)
    ax7.axis('off')
    
    optimal_params = []
    for sec in securities_sorted:
        sec_df = df[df['security'] == sec]
        best_row = sec_df.loc[sec_df['pnl'].idxmax()]
        optimal_params.append([sec, str(best_row[param_col]), f"{best_row['pnl']:,.0f}"])
    
    # Split into 2 columns if many securities
    n_rows = (len(optimal_params) + 1) // 2
    left_data = optimal_params[:n_rows]
    right_data = optimal_params[n_rows:] if len(optimal_params) > n_rows else []
    while len(right_data) < len(left_data):
        right_data.append(['', '', ''])
    
    combined = []
    for i in range(len(left_data)):
        row = list(left_data[i])
        if i < len(right_data):
            row.extend(right_data[i])
        else:
            row.extend(['', '', ''])
        combined.append(row)
    
    table7 = ax7.table(cellText=combined, 
                       colLabels=['Security', 'Optimal', 'P&L', 'Security', 'Optimal', 'P&L'],
                       loc='center', cellLoc='center', colWidths=[0.18, 0.12, 0.18, 0.18, 0.12, 0.18])
    table7.auto_set_font_size(False)
    table7.set_fontsize(9)
    table7.scale(1.0, 1.5)
    for i in range(6):
        table7[(0, i)].set_facecolor('#70AD47')
        table7[(0, i)].set_text_props(color='white', fontweight='bold')
    ax7.set_title('Optimal Parameter per Security', fontsize=12, fontweight='bold', pad=20)
    
    plt.suptitle(f'Closing Strategy Sweep - {param_col}', fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    
    output_path = os.path.join(sweep_dir, output_name)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate sweep summary plots')
    parser.add_argument('--sweep-dir', help='Specific sweep directory to process')
    parser.add_argument('--all', action='store_true', help='Process all sweep directories')
    
    args = parser.parse_args()
    
    # Default sweep directories
    default_sweep_dirs = [
        'output/vwap_spread_sweep',
        'output/vwap_spread_sweep_1m_cap',
        'output/vwap_period_sweep_1m_cap',
    ]
    
    if args.sweep_dir:
        sweep_dirs = [args.sweep_dir]
    elif args.all:
        # Find all sweep directories
        output_dir = os.path.join(PROJECT_ROOT, 'output')
        sweep_dirs = []
        for d in os.listdir(output_dir):
            full_path = os.path.join(output_dir, d)
            if os.path.isdir(full_path) and 'sweep' in d.lower():
                # Check if it has sweep_all_results.csv
                if os.path.exists(os.path.join(full_path, 'sweep_all_results.csv')):
                    sweep_dirs.append(full_path)
    else:
        sweep_dirs = [os.path.join(PROJECT_ROOT, d) for d in default_sweep_dirs]
    
    print(f"Processing {len(sweep_dirs)} sweep directories...")
    
    for sweep_dir in sweep_dirs:
        if os.path.exists(sweep_dir):
            print(f"\nProcessing {sweep_dir}...")
            generate_sweep_summary(sweep_dir)
        else:
            print(f"  {sweep_dir} not found")


if __name__ == '__main__':
    main()
