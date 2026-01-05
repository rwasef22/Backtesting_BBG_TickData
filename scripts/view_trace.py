"""View and analyze detailed strategy trace output.

This script formats and displays the trace CSV in a readable format,
with options to filter by specific criteria.

Usage:
    python scripts/view_trace.py output/trace/emaar_v2_30s_3days_trace.csv
    python scripts/view_trace.py output/trace/emaar_v2_30s_3days_trace.csv --show-fills-only
    python scripts/view_trace.py output/trace/emaar_v2_30s_3days_trace.csv --max-events 100
"""
import argparse
import pandas as pd
from pathlib import Path


def format_trace_row(row, show_all=False):
    """Format a single trace row for display."""
    lines = []
    
    # Event header
    header = f"[{row['event_num']:5d}] {row['timestamp']} | {row['event_type']:6s}"
    if pd.notna(row['event_price']):
        header += f" @ {row['event_price']:.3f} x {int(row['event_volume'])}"
    lines.append(header)
    
    # Order book state
    if pd.notna(row['ob_best_bid_price']) or pd.notna(row['ob_best_ask_price']):
        ob_line = "  OB: "
        if pd.notna(row['ob_best_bid_price']):
            ob_line += f"Bid={row['ob_best_bid_price']:.3f}x{int(row['ob_best_bid_qty'])}  "
        else:
            ob_line += "Bid=None  "
        
        if pd.notna(row['ob_best_ask_price']):
            ob_line += f"Ask={row['ob_best_ask_price']:.3f}x{int(row['ob_best_ask_qty'])}"
        else:
            ob_line += "Ask=None"
        lines.append(ob_line)
    
    # Time windows
    if show_all:
        windows = []
        if row['in_opening_auction']:
            windows.append('OPENING')
        if row['in_silent_period']:
            windows.append('SILENT')
        if row['in_closing_auction']:
            windows.append('CLOSING')
        if windows:
            lines.append(f"  Windows: {', '.join(windows)}")
    
    # Strategy quotes
    if pd.notna(row['quote_bid_price']) or pd.notna(row['quote_ask_price']):
        quote_line = "  QUOTES: "
        if pd.notna(row['quote_bid_price']) and pd.notna(row['quote_bid_size']):
            quote_line += f"Bid={row['quote_bid_price']:.3f}x{int(row['quote_bid_size'])}  "
        else:
            quote_line += "Bid=None  "
        
        if pd.notna(row['quote_ask_price']) and pd.notna(row['quote_ask_size']):
            quote_line += f"Ask={row['quote_ask_price']:.3f}x{int(row['quote_ask_size'])}"
        else:
            quote_line += "Ask=None"
        lines.append(quote_line)
    
    # Fill information
    if pd.notna(row['fill_side']):
        fill_line = f"  *** FILL: {row['fill_side'].upper()} {int(row['fill_qty'])} @ {row['fill_price']:.3f} ***"
        lines.append(fill_line)
    
    # Position and P&L
    if show_all or pd.notna(row['fill_side']):
        pnl_line = f"  Position={int(row['position'])}  Entry={row['entry_price']:.3f}  PnL={row['realized_pnl']:.2f}"
        lines.append(pnl_line)
    
    # Notes
    if pd.notna(row['notes']) and row['notes']:
        lines.append(f"  Notes: {row['notes']}")
    
    lines.append("")  # Blank line between events
    return '\n'.join(lines)


def view_trace(file_path: str, show_fills_only: bool = False, max_events: int = None, 
               date_filter: str = None, show_all: bool = False):
    """Load and display trace file."""
    
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        return
    
    print(f"Loading trace from: {file_path}\n")
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Apply filters
    if show_fills_only:
        df = df[df['fill_side'].notna()].copy()
        print(f"Filtering to {len(df)} fill events only\n")
    
    if date_filter:
        df = df[df['date'] == date_filter].copy()
        print(f"Filtering to date: {date_filter} ({len(df)} events)\n")
    
    if max_events:
        df = df.head(max_events).copy()
        print(f"Limiting to first {max_events} events\n")
    
    # Display summary
    print("=" * 80)
    print("TRACE SUMMARY")
    print("=" * 80)
    print(f"Total events: {len(df)}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Trading days: {df['date'].nunique()}")
    
    fills = df[df['fill_side'].notna()]
    if len(fills) > 0:
        print(f"\nFills: {len(fills)} total")
        print(f"  Buy: {len(fills[fills['fill_side'] == 'buy'])}")
        print(f"  Sell: {len(fills[fills['fill_side'] == 'sell'])}")
        print(f"  Avg size: {fills['fill_qty'].mean():.0f}")
        print(f"  Total P&L: {fills['realized_pnl'].iloc[-1]:.2f} AED")
    
    quotes = df[(df['quote_bid_price'].notna()) | (df['quote_ask_price'].notna())]
    if len(quotes) > 0:
        print(f"\nQuotes: {len(quotes)} events with quotes")
        print(f"  Bid quotes: {quotes['quote_bid_price'].notna().sum()}")
        print(f"  Ask quotes: {quotes['quote_ask_price'].notna().sum()}")
    
    print("\n" + "=" * 80)
    print("EVENT-BY-EVENT TRACE")
    print("=" * 80)
    print()
    
    # Display events
    for _, row in df.iterrows():
        print(format_trace_row(row, show_all=show_all))
    
    # Final summary
    print("=" * 80)
    print("END OF TRACE")
    print("=" * 80)
    if len(df) > 0:
        last_row = df.iloc[-1]
        print(f"Final position: {int(last_row['position'])}")
        print(f"Final P&L: {last_row['realized_pnl']:.2f} AED")


def main():
    parser = argparse.ArgumentParser(description='View strategy trace')
    parser.add_argument('file', type=str, help='Path to trace CSV file')
    parser.add_argument('--show-fills-only', action='store_true', 
                       help='Show only events with fills')
    parser.add_argument('--max-events', type=int, default=None,
                       help='Limit number of events to display')
    parser.add_argument('--date', type=str, default=None,
                       help='Filter to specific date (YYYY-MM-DD)')
    parser.add_argument('--show-all', action='store_true',
                       help='Show all details including time windows')
    
    args = parser.parse_args()
    
    view_trace(args.file, 
               show_fills_only=args.show_fills_only,
               max_events=args.max_events,
               date_filter=args.date,
               show_all=args.show_all)


if __name__ == '__main__':
    main()
