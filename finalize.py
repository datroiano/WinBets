#!/usr/bin/env python3
import pandas as pd

def main():
    input_file  = 'stats_v5.xlsx'
    output_file = 'stats_final.xlsx'
    sheets      = ['Main', 'IndoorExtras']

    # Create a new Excel writer
    writer = pd.ExcelWriter(output_file, engine='openpyxl')

    for sheet in sheets:
        # Read each sheet
        df = pd.read_excel(input_file, sheet_name=sheet)

        # Add the Differential column
        df['Differential'] = df['TotalRuns'] - df['TotalRunsLine']

        # Write back to the new workbook
        df.to_excel(writer, sheet_name=sheet, index=False)
        print(f"✅ Added Differential on sheet '{sheet}'")

    # Finalize
    writer._save()
    print(f"\n🎉 Saved with Differential → {output_file}")

if __name__ == '__main__':
    main()
