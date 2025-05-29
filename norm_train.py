#!/usr/bin/env python3
"""
normalize_and_save_v2.py

Reads stats_final.xlsx (Main + IndoorExtras), drops meta & score fields,
engineers features, imputes & scales numeric columns, one-hot encodes categoricals,
and writes the entire normalized dataset to stats_final_ML_v2.xlsx.
"""

import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

INPUT_FILE   = "stats_final.xlsx"
OUTPUT_FILE  = "stats_final_ML_v2.xlsx"

# Meta/identifier columns (and scores/coords) to drop
META_COLS = [
    "id", "sport_key", "sport_title",
    "home_team", "away_team",
    "StadiumName", "OutdoorOnly", "WindCategory",
    "GameID", "HomeScore", "AwayScore",
    "Latitude", "Longitude"
]

def load_and_combine(path):
    print("Loading Main + IndoorExtras …")
    main   = pd.read_excel(path, sheet_name="Main")
    indoor = pd.read_excel(path, sheet_name="IndoorExtras")
    main["is_indoor"]   = 0
    indoor["is_indoor"] = 1
    combined = pd.concat([main, indoor], ignore_index=True)
    print(f" → total rows: {len(combined)}")
    return combined

def engineer(df):
    print("Parsing 'commence_time' and deriving cyclical date features …")
    df["commence_time"] = pd.to_datetime(df["commence_time"])
    df["month"] = df["commence_time"].dt.month
    df["dow"]   = df["commence_time"].dt.dayofweek

    df["month_sin"] = np.sin(2*np.pi*df.month/12)
    df["month_cos"] = np.cos(2*np.pi*df.month/12)
    df["dow_sin"]   = np.sin(2*np.pi*df.dow/7)
    df["dow_cos"]   = np.cos(2*np.pi*df.dow/7)

    print("Engineering wind vector components …")
    wd = np.deg2rad(df["WindDir"])
    cb = np.deg2rad(df["CompassBearing"])
    delta = cb - wd
    df["wind_parallel"] = df["WindSpeed_mph"] * np.cos(delta)
    df["wind_cross"]    = df["WindSpeed_mph"] * np.sin(delta)

    print("Encoding batter bearing as cyclical …")
    df["batt_x"] = np.cos(cb)
    df["batt_y"] = np.sin(cb)

    if "Precipitation" in df.columns:
        print("Adding precipitation flag …")
        df["precip_flag"] = (df["Precipitation"] > 0).astype(int)

    print("Dropping raw intermediate columns …")
    df = df.drop(columns=[
        "commence_time","month","dow",
        "WindDir","CompassBearing","WindSpeed_mph"
    ], errors="ignore")

    return df

def main():
    # 1) Load and drop meta
    df = load_and_combine(INPUT_FILE)
    print("Dropping meta/ID/score/coord columns …")
    df.drop(columns=META_COLS, errors="ignore", inplace=True)
    print(f" → columns remaining: {df.shape[1]}\n")

    # 2) Engineer new features
    df = engineer(df)
    print(f"After engineering: {df.shape}\n")

    # 3) Identify categorical vs numeric
    # Include Sportbook as a categorical column!
    cat_cols = [c for c in ["StadiumID", "Sportbook", "is_indoor", "precip_flag"]
                if c in df.columns]
    for c in cat_cols:
        df[c] = df[c].astype(str)

    num_cols = [c for c in df.columns if c not in cat_cols]

    print(f"Categorical columns ({len(cat_cols)}): {cat_cols}")
    print(f"Numeric columns   ({len(num_cols)}): {num_cols[:5]} …\n")

    # 4) Impute + scale numeric
    print("Imputing missing numeric values …")
    imputer = SimpleImputer(strategy="median")
    df[num_cols] = imputer.fit_transform(df[num_cols])

    print("Scaling numeric features …")
    scaler = StandardScaler()
    df[num_cols] = scaler.fit_transform(df[num_cols])

    # 5) One-hot encode categorical features
    print("One-hot encoding categorical features …")
    df = pd.get_dummies(df, columns=cat_cols, dummy_na=False)
    print(f"Final dataset shape: {df.shape}\n")

    # 6) Write out to Excel
    print(f"Writing normalized data to {OUTPUT_FILE} …")
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="normalized", index=False)

    print("Done.")

if __name__ == "__main__":
    main()
