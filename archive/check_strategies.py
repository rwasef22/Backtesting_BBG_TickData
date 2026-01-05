import pandas as pd

df = pd.read_csv('output/comprehensive_sweep/comprehensive_results.csv')

print("=== STRATEGIES IN comprehensive_results.csv ===")
print(sorted(df['strategy'].unique()))
print(f"\nTotal rows: {len(df)}")

print("\n=== V2.1 DATA ===")
v21_data = df[df['strategy'] == 'v2_1']
print(f"V2.1 rows found: {len(v21_data)}")
if len(v21_data) > 0:
    print("\nV2.1 intervals:")
    print(v21_data[['interval_sec', 'total_pnl', 'total_trades']].to_string(index=False))
else:
    print("NO V2.1 DATA FOUND!")

print("\n=== ALL STRATEGIES ===")
print(df.groupby('strategy').size())

# Write to file
with open('check_strategies.txt', 'w') as f:
    f.write("STRATEGIES:\n")
    f.write(str(sorted(df['strategy'].unique())))
    f.write(f"\n\nV2.1 rows: {len(v21_data)}\n")
    if len(v21_data) > 0:
        f.write("\nV2.1 data:\n")
        f.write(v21_data[['interval_sec', 'total_pnl', 'total_trades']].to_string(index=False))

print("\n✓ Written to check_strategies.txt")
