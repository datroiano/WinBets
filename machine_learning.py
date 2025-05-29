#!/usr/bin/env python3
"""
mlb_over_under_model_multi_updated.py

For each sheet in ["Main","IndoorExtras"]:
 - compute relative-wind features (headwind & crosswind)
 - drop raw WindDir, CompassBearing, TotalUnderOdds
 - drop user-specified features: TotalRunsLine, Longitude, StadiumID,
   Sportbook_draftkings, Sportbook_fanduel, Sportbook_betonlineag,
   StadiumName_* for Globe Life Field, Rogers Centre, loanDepot park,
   Daikin Park, T-Mobile Park, Chase Field,
   Sportbook_unibet_us, Sportbook_betrivers, Sportbook_pointsbetus
 - train a RandomForest on Over/Under
 - report baseline, train/test accuracy, Brier score, avg Over prob
 - print ALL feature importances, numbered
 - save model to disk

Also includes a helper to predict on future games.
"""

import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss
from sklearn.model_selection import train_test_split

# === Configuration ===
SHEETS = ["Main", "IndoorExtras"]
INPUT_FILE = "stats_final.xlsx"
RANDOM_STATE = 42

# Columns to remove (after initial drop)
EXTRA_DROP = [
    'TotalRunsLine', 'Longitude', 'StadiumID',
    'Sportbook_draftkings', 'Sportbook_fanduel', 'Sportbook_betonlineag',
    'StadiumName_Globe Life Field', 'StadiumName_Rogers Centre',
    'StadiumName_loanDepot park', 'StadiumName_Daikin Park',
    'StadiumName_T-Mobile Park', 'StadiumName_Chase Field',
    'Sportbook_unibet_us', 'Sportbook_betrivers', 'Sportbook_pointsbetus'
]


def load_and_preprocess(path, sheet_name):
    # 1) Load the sheet
    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")

    # 2) Keep only Over/Under outcomes
    df = df[df["Outcome"].isin(["Over", "Under"])].copy()
    df["label"] = df["Outcome"].map({"Under": 0, "Over": 1})

    # 3) Compute relative-wind components if possible
    if {"WindDir", "CompassBearing", "WindSpeed_mph"}.issubset(df.columns):
        rel_deg = (df["WindDir"] - df["CompassBearing"]) % 360
        rad = np.deg2rad(rel_deg)
        df["wind_head"] = df["WindSpeed_mph"] * np.cos(rad)
        df["wind_cross"] = df["WindSpeed_mph"] * np.sin(rad)
        df.drop(columns=["WindDir", "CompassBearing"], inplace=True)

    # 4) Drop unwanted or leaky columns
    drop_cols = [
        "id", "sport_key", "sport_title", "commence_time",
        "home_team", "away_team", "GameID",
        "HomeScore", "AwayScore", "TotalRuns", "Differential",
        "Outcome", "OverPayout", "UnderPayout", "TotalUnderOdds"
    ]
    existing = [c for c in drop_cols if c in df.columns]
    df.drop(columns=existing, inplace=True)

    # 5) Split into features X and label y
    X = df.drop(columns=["label"])
    y = df["label"].values

    # 6) One-hot encode categoricals
    X = pd.get_dummies(X, drop_first=True)

    # 7) Drop extra features as requested
    to_drop = [c for c in EXTRA_DROP if c in X.columns]
    X.drop(columns=to_drop, inplace=True)

    # 8) Fill any remaining NaNs with the median (all columns now numeric)
    X = X.fillna(X.median())

    return X, y


def evaluate_and_save(X, y, sheet_name, test_size=0.1):
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size,
        stratify=y, random_state=RANDOM_STATE
    )

    # Baseline accuracy by always picking the majority class
    majority = np.bincount(y_train).argmax()
    baseline = (y_test == majority).mean()

    # Train RandomForest
    clf = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)
    clf.fit(X_train, y_train)

    # Predictions & probabilities on train/test
    p_tr = clf.predict(X_train)
    p_te = clf.predict(X_test)
    prob_te = clf.predict_proba(X_test)[:, 1]

    # Compute metrics
    acc_tr = accuracy_score(y_train, p_tr)
    acc_te = accuracy_score(y_test, p_te)
    brier = brier_score_loss(y_test, prob_te)
    avg_p = prob_te.mean()

    # Report
    print(f"\n=== Sheet: {sheet_name} ===")
    print(f"Baseline (always pick {majority}):       {baseline:.3f}")
    print(f"Train accuracy:                          {acc_tr:.3f}")
    print(f"Test  accuracy:                          {acc_te:.3f}")
    print(f"Brier score:                             {brier:.3f}")
    print(f"Average P(Over) on test set:             {avg_p:.3f}")

    # Feature importances
    imps = pd.Series(clf.feature_importances_, index=X.columns)
    imps_sorted = imps.sort_values(ascending=False)

    print("\nFeature importances (ranked):")
    for rank, (feat, imp) in enumerate(imps_sorted.items(), 1):
        print(f"{rank:2d}. {feat:30s} {imp:.4f}")

    # Save model and column list
    out_path = f"rf_model_{sheet_name}.pkl"
    joblib.dump({"model": clf, "columns": X.columns.tolist()}, out_path)
    print(f"\nSaved model to → {out_path}")


def predict_upcoming(upcoming_file, model_file):
    """
    Load a saved model and make Over/Under predictions on new upcoming games.
    Returns a DataFrame with original data plus Pick and P(Over).
    """
    df = pd.read_excel(upcoming_file, engine="openpyxl")
    data = joblib.load(model_file)
    clf, cols = data["model"], data["columns"]

    # Compute relative-wind again if angles present
    if {"WindDir", "CompassBearing", "WindSpeed_mph"}.issubset(df.columns):
        rel_deg = (df["WindDir"] - df["CompassBearing"]) % 360
        rad = np.deg2rad(rel_deg)
        df["wind_head"] = df["WindSpeed_mph"] * np.cos(rad)
        df["wind_cross"] = df["WindSpeed_mph"] * np.sin(rad)
        df.drop(columns=["WindDir", "CompassBearing"], inplace=True)

    # Drop TotalUnderOdds if present
    if "TotalUnderOdds" in df.columns:
        df.drop(columns=["TotalUnderOdds"], inplace=True)

    Xnew = pd.get_dummies(df, drop_first=True)
    Xnew = Xnew.reindex(columns=cols, fill_value=0).fillna(0)

    preds = clf.predict(Xnew)
    probs = clf.predict_proba(Xnew)[:, 1]

    out = df.copy()
    out["Pick"] = pd.Categorical(preds, categories=[0, 1]).map({0: "Under", 1: "Over"})
    out["P(Over)"] = probs
    return out


if __name__ == "__main__":
    # Train & evaluate models on each sheet
    for sheet in SHEETS:
        X, y = load_and_preprocess(INPUT_FILE, sheet)
        print(f"\nLoaded '{sheet}': {X.shape[0]} rows × {X.shape[1]} features")
        evaluate_and_save(X, y, sheet)

    # Usage hint for predictions
    print("\nTo predict on upcoming games, use:")
    print(">>> from mlb_over_under_model_multi_updated import predict_upcoming")
    print(">>> df_preds = predict_upcoming('upcoming_games.xlsx', 'rf_model_Main.pkl')")
    print(">>> print(df_preds[['Pick','P(Over)']].head())")