import pandas as pd

df = pd.read_csv('output/trace/emaar_v2_30s_3days_trace_fixed.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Check EOD period
eod = df[(df['timestamp'].dt.time >= pd.to_datetime('14:55').time()) & 
         (df['timestamp'].dt.time <= pd.to_datetime('15:00').time())]

print('Events at EOD (14:55-15:00):')
print(f'Total events: {len(eod)}')

fills = eod[eod['fill_side'].notna()]
print(f'Fills: {len(fills)}')

if len(fills) > 0:
    print('\nFill events:')
    print(fills[['timestamp', 'fill_side', 'fill_qty', 'position', 'notes']].to_string())
else:
    print('\nNo fills during EOD period (correct behavior!)')

# Check position at end of each day
print('\n\nPosition at end of each trading day:')
for date in df['date'].unique():
    day_data = df[df['date'] == date]
    last_pos = day_data['position'].iloc[-1]
    print(f'{date}: {last_pos}')
