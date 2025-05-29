#!/usr/bin/env python3
import pandas as pd

def find_duplicates_loops():
    # 1) Load the Excel sheets
    file = "stats_final_ML.xlsx"
    df_train = pd.read_excel(file, sheet_name="train")
    df_test  = pd.read_excel(file, sheet_name="test")

    # 2) Define the first 51 columns to compare
    cols = list(df_train.columns[:51])

    # 3) Build a list of records: (sheet_name, excel_row, [values…])
    records = []
    for idx, row in df_train.iterrows():
        records.append(("train", idx + 2, row[cols].tolist()))
    for idx, row in df_test.iterrows():
        records.append(("test", idx + 2, row[cols].tolist()))

    # 4) Nested loops to compare every pair of rows
    duplicates = []
    n = len(records)
    for i in range(n):
        sheet_i, row_i, vals_i = records[i]
        for j in range(i + 1, n):
            sheet_j, row_j, vals_j = records[j]

            # Use AND logic: all corresponding values must match
            all_equal = True
            for a, b in zip(vals_i, vals_j):
                # treat two NaNs as equal
                if pd.isna(a) and pd.isna(b):
                    continue
                if a != b:
                    all_equal = False
                    break

            if all_equal:
                duplicates.append(((sheet_i, row_i), (sheet_j, row_j)))

    # 5) Report
    if not duplicates:
        print("✅ No duplicates found across the first 51 columns.")
        return

    print(f"⚠ Found {len(duplicates)} duplicate pairs:")
    for (s1, r1), (s2, r2) in duplicates:
        print(f"  • {s1} row {r1} == {s2} row {r2}")

    # 6) Save duplicates to Excel for inspection
    with pd.ExcelWriter("duplicates.xlsx") as writer:
        for idx, ((s1, r1), (s2, r2)) in enumerate(duplicates, start=1):
            # grab the matching rows
            df1 = df_train if s1 == "train" else df_test
            df2 = df_train if s2 == "train" else df_test

            row1 = df1.iloc[r1 - 2][cols]
            row2 = df2.iloc[r2 - 2][cols]

            # combine side by side
            df_pair = pd.concat(
                [row1.reset_index(drop=True), row2.reset_index(drop=True)],
                axis=1,
                keys=[f"{s1}_{r1}", f"{s2}_{r2}"]
            )
            df_pair.to_excel(writer, sheet_name=f"dup_pair_{idx}", index=False)

    print("→ Duplicates written to 'duplicates.xlsx'")

if __name__ == "__main__":
    find_duplicates_loops()
