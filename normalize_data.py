#!/usr/bin/env python3
"""
normalize_data.py

Reads stats_final.xlsx, preprocesses & normalizes for DL (no training),
splits train/test, and writes stats_final_ML.xlsx with sheets 'train' and 'test'.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

INPUT_FILE   = "stats_final.xlsx"
OUTPUT_FILE  = "stats_final_ML.xlsx"

# 1) Columns to drop entirely before feature engineering
META_COLS = [
    "id", "sport_key", "sport_title",
    "home_team", "away_team",
    "StadiumName", "OutdoorOnly", "WindCategory",
    "GameID", "HomeScore", "AwayScore",
    "Latitude", "Longitude"      # <-- now dropping lat/long too
]

# 2) Columns to drop *only* for training (kept in test odds sheet)
DROP_COLS = [
    "TotalRunsLine", "TotalOverOdds", "TotalUnderOdds",
    "Sportbook", "Outcome", "OverPayout", "UnderPayout"
]
ODDS_COLS = DROP_COLS.copy()

# 3) Your prediction target
TARGET = "TotalRuns"


def load_and_combine(path):
    print("1) Loading Main + IndoorExtras …")
    main   = pd.read_excel(path, sheet_name="Main")
    indoor = pd.read_excel(path, sheet_name="IndoorExtras")
    print(f"   Main rows: {len(main)}, IndoorExtras rows: {len(indoor)}")
    main["is_indoor"]   = 0
    indoor["is_indoor"] = 1
    combined = pd.concat([main, indoor], ignore_index=True)
    print(f"   Total combined rows: {len(combined)}\n")
    return combined


def preprocess(df):
    print("2) Parsing 'commence_time' → datetime and building cyclical date features …")
    df["commence_time"] = pd.to_datetime(df["commence_time"])
    df["month"]     = df["commence_time"].dt.month
    df["dow"]       = df["commence_time"].dt.dayofweek
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"]   = np.sin(2 * np.pi * df["dow"]   / 7)
    df["dow_cos"]   = np.cos(2 * np.pi * df["dow"]   / 7)

    print("3) Engineering wind vector relative to batter …")
    wd_rad = np.deg2rad(df["WindDir"])
    cb_rad = np.deg2rad(df["CompassBearing"])
    delta  = cb_rad - wd_rad
    df["wind_parallel"] = df["WindSpeed_mph"] * np.cos(delta)
    df["wind_cross"]    = df["WindSpeed_mph"] * np.sin(delta)

    print("4) Encoding batter orientation as cyclical …")
    # These two are the x/y components of the batter's compass bearing
    df["batt_x"] = np.cos(cb_rad)
    df["batt_y"] = np.sin(cb_rad)

    if "Precipitation" in df.columns:
        print("5) Creating precipitation flag …")
        df["precip_flag"] = (df["Precipitation"] > 0).astype(int)

    print("6) Dropping raw columns we've encoded …\n")
    df = df.drop(
        columns=[
            "commence_time", "month", "dow",
            "WindDir", "CompassBearing", "WindSpeed_mph"
        ],
        errors="ignore"
    )
    return df


def main():
    # 1) Load & combine data
    df_orig = load_and_combine(INPUT_FILE)

    # 2) Drop meta/non‑features upfront
    print("7) Dropping meta/non‑feature columns …")
    df_orig.drop(columns=META_COLS, errors="ignore", inplace=True)
    print(f"   → Columns now: {df_orig.shape[1]}\n")

    # 3) Save odds/line for the test sheet
    print("8) Extracting odds/line columns for later …\n")
    odds_df = df_orig[ODDS_COLS].copy()

    # 4) Preprocess & feature‑engineer
    df = preprocess(df_orig.copy())
    print(f"   → After preprocess: {df.shape[0]} rows × {df.shape[1]} cols\n")

    # 5) Drop train‑only non‑features
    print("9) Dropping model non‑feature columns …")
    df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore", inplace=True)
    print(f"   → Now: {df.shape[1]} cols (including target)\n")

    # 6) Split into X & y, then train/test
    print("10) Splitting into train/test (80/20) …")
    y = df[TARGET]
    X = df.drop(columns=[TARGET])
    train_idx, test_idx = train_test_split(df.index, test_size=0.2, random_state=42)
    print(f"   → Train rows: {len(train_idx)}, Test rows: {len(test_idx)}\n")

    X_train  = X.loc[train_idx].reset_index(drop=True)
    y_train  = y.loc[train_idx].reset_index(drop=True)
    X_test   = X.loc[test_idx].reset_index(drop=True)
    y_test   = y.loc[test_idx].reset_index(drop=True)
    odds_test = odds_df.loc[test_idx].reset_index(drop=True)

    # 7) Specify the small set of categoricals
    print("11) Selecting categorical vs numeric features …")
    cat_cols = []
    for c in ["StadiumID", "HomeTeam", "AwayTeam", "is_indoor", "precip_flag"]:
        if c in X_train.columns:
            cat_cols.append(c)
            X_train[c] = X_train[c].astype(str)
            X_test[c]  = X_test[c].astype(str)
    num_cols = [c for c in X_train.columns if c not in cat_cols]
    print(f"   → {len(num_cols)} numeric cols, {len(cat_cols)} categorical cols\n")

    # 8) Impute & scale numeric
    print("12) Imputing & scaling numeric features …")
    X_train[num_cols] = X_train[num_cols].apply(pd.to_numeric, errors="coerce")
    X_test[ num_cols] = X_test[ num_cols].apply(pd.to_numeric, errors="coerce")

    num_imputer = SimpleImputer(strategy="median")
    X_train[num_cols] = num_imputer.fit_transform(X_train[num_cols])
    X_test[ num_cols] = num_imputer.transform(   X_test[num_cols])

    scaler = StandardScaler()
    X_train[num_cols] = scaler.fit_transform(X_train[num_cols])
    X_test[ num_cols] = scaler.transform(   X_test[num_cols])
    print("   → Numeric preprocessing done\n")

    # 9) One‑hot encode only the listed categoricals
    print("13) One‑hot encoding categorical features …")
    combined = pd.concat([X_train, X_test], keys=["train","test"])
    combined = pd.get_dummies(combined, columns=cat_cols, dummy_na=False)
    X_train = combined.xs("train")
    X_test  = combined.xs("test")
    print(f"   → Final feature count: {X_train.shape[1]}\n")

    # 10) Reattach target & odds, write out Excel
    print(f"14) Writing to {OUTPUT_FILE} …")
    train_df = pd.concat([X_train.reset_index(drop=True), y_train], axis=1)
    test_df  = pd.concat([X_test.reset_index(drop=True),
                          y_test.reset_index(drop=True),
                          odds_test],
                         axis=1)
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        train_df.to_excel(writer, sheet_name="train", index=False)
        test_df .to_excel(writer, sheet_name="test",  index=False)

    print("15) Preprocessing complete. File written.\n")


if __name__ == "__main__":
    main()
