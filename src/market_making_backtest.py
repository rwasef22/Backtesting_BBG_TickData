"""Streaming-integrated backtest entrypoint.

This module provides `MarketMakingBacktest.run_streaming` which consumes the
`stream_sheets` generator from `data_loader` and processes data sheet-by-sheet
and chunk-by-chunk. A pluggable `handler` processes each chunk (security, df,
orderbook, state) allowing incremental strategy execution.
"""
from typing import Callable, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from src.data_loader import stream_sheets, preprocess_chunk_df
from src.orderbook import OrderBook


class MarketMakingBacktest:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        # per-security orderbooks/state
        self.order_books: Dict[str, OrderBook] = {}

    def _default_handler(self, security: str, df, orderbook: OrderBook, state: dict):
        """Default handler: accumulate counts by type and last prices."""
        n = len(df)
        state['rows'] = state.get('rows', 0) + n
        
        # Count by type
        if 'type' in df.columns:
            df_type_lower = df['type'].astype(str).str.lower()
            for typ in ['bid', 'ask', 'trade']:
                count = int((df_type_lower == typ).sum())
                if count > 0:
                    state[f'{typ}_count'] = state.get(f'{typ}_count', 0) + count

        # Apply updates to orderbook (fast vectorized-ish approach)
        for _, row in df.iterrows():
            orderbook.apply_update({'timestamp': row['timestamp'], 'type': row['type'], 'price': row['price'], 'volume': row['volume']})

        # track last trade price
        if orderbook.last_trade:
            state['last_price'] = orderbook.last_trade.get('price')

        return state

    def run_streaming(self, file_path: str, header_row: int = 3, chunk_size: int = 100000,
                      only_trades: bool = True, max_sheets: Optional[int] = None,
                      handler: Optional[Callable[[str, Any, OrderBook, dict], dict]] = None,
                      write_csv: bool = True, output_dir: Optional[str] = 'output',
                      sheet_names_filter: Optional[list] = None) -> Dict[str, dict]:
        """Stream the Excel file and process each sheet chunk-by-chunk.

        - file_path: path to TickData.xlsx
        - only_trades: filter to trade events early if True (faster)
        - max_sheets: limit to first N sheets
        - sheet_names_filter: optional list of specific sheet names to process
        - handler: function(security, df, orderbook, state) -> state
        Returns a dict mapping security -> state summary
        """
        results: Dict[str, dict] = {}
        handler = handler or self._default_handler

        chunk_count = 0
        for sheet_name, chunk in stream_sheets(file_path, header_row=header_row, chunk_size=chunk_size, 
                                                max_sheets=max_sheets, only_trades=only_trades,
                                                sheet_names_filter=sheet_names_filter):
            chunk_count += 1
            print(f"Processing chunk {chunk_count}: {len(chunk)} rows for {sheet_name}")
            
            sec = sheet_name.replace(' UH Equity', '').replace(' DH Equity', '')
            if sec not in self.order_books:
                self.order_books[sec] = OrderBook()
            ob = self.order_books[sec]
            state = results.get(sec, {})

            # normalize chunk
            df = preprocess_chunk_df(chunk)

            # call handler
            state = handler(sec, df, ob, state) or state
            results[sec] = state
            
            print(f"  After chunk {chunk_count}: {len(state.get('trades', []))} total trades")

        print(f"\nTotal chunks processed: {chunk_count}")

        # Optionally write per-security CSVs to avoid stale outputs
        if write_csv:
            out_dir = Path(output_dir or 'output')
            out_dir.mkdir(parents=True, exist_ok=True)
            for sec, state in results.items():
                trades = state.get('trades', [])
                if not trades:
                    continue
                try:
                    df = pd.DataFrame(trades)
                    if 'timestamp' in df.columns:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df = df.sort_values('timestamp').reset_index(drop=True)
                    # Round PNL and position values to integers
                    if 'realized_pnl' in df.columns:
                        df['realized_pnl'] = df['realized_pnl'].round(0).astype(int)
                    if 'pnl' in df.columns:
                        df['pnl'] = df['pnl'].round(0).astype(int)
                    if 'position' in df.columns:
                        df['position'] = df['position'].round(0).astype(int)
                    # Standard per-security filename; downstream can select needed columns
                    file_name = f"{sec.lower()}_trades_timeseries.csv"
                    df.to_csv(out_dir / file_name, index=False)
                except Exception:
                    # Fail-safe: never break the backtest due to IO/format issues
                    pass

        return results
