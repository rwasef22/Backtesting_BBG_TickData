"""Generate a small synthetic TickData.xlsx for smoke testing."""
import os
import pandas as pd
from datetime import datetime, timedelta


def create_sample_tickdata(output_path: str, n_securities: int = 3, rows_per_sec: int = 5000):
    """Create a sample TickData.xlsx with multiple sheets.
    
    Each sheet has: Dates, Type, Price, Size columns.
    """
    data_dir = os.path.dirname(output_path)
    os.makedirs(data_dir, exist_ok=True)

    securities = [f"SECURITY_{i:02d} UH Equity" for i in range(n_securities)]
    base_price = 150.0

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sec_idx, sec_name in enumerate(securities):
            rows = []
            ts = datetime(2025, 1, 2, 10, 0, 0)
            for row_idx in range(rows_per_sec):
                # Alternate bid/ask/trade
                if row_idx % 3 == 0:
                    typ = 'BID'
                elif row_idx % 3 == 1:
                    typ = 'ASK'
                else:
                    typ = 'TRADE'

                price = base_price + sec_idx * 10 + (row_idx * 0.001)
                size = 100 + (row_idx % 1000)
                rows.append({
                    'Dates': ts,
                    'Type': typ,
                    'Price': price,
                    'Size': size
                })
                ts += timedelta(seconds=1)

            df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=sec_name, index=False, startrow=2)
            # Write dummy header at row 1 (1-based)
            ws = writer.sheets[sec_name]
            ws['A1'] = sec_name
            ws['A2'] = 'Metadata row'

    print(f"Created {output_path}")
    print(f"  Securities: {n_securities}")
    print(f"  Rows per security: {rows_per_sec}")
    print(f"  Total rows (approx): {n_securities * rows_per_sec:,}")


if __name__ == '__main__':
    output = os.path.join('data', 'raw', 'TickData_Sample.xlsx')
    create_sample_tickdata(output, n_securities=3, rows_per_sec=5000)
