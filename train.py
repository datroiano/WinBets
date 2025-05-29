#!/usr/bin/env python3
"""
train_test_model.py

Loads stats_final_ML.xlsx, trains a DNN to predict TotalRuns,
evaluates on the test set (MSE/MAE), then binarizes
into Over/Under versus the line and computes classification metrics.
"""

import pandas as pd
import numpy as np

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping

from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    brier_score_loss,
    roc_auc_score
)

# 1) Configuration
DATA_FILE = "stats_final_ML.xlsx"
TARGET    = "TotalRuns"
LINE_COL  = "TotalRunsLine"   # from the test sheet
ODDS_COLS = [                 # these were in your test sheet
    "TotalRunsLine",
    "TotalOverOdds",
    "TotalUnderOdds",
    "Sportbook",
    "Outcome",
    "OverPayout",
    "UnderPayout",
]

def load_data(path):
    # Read in both sheets
    train_df = pd.read_excel(path, sheet_name="train")
    test_df  = pd.read_excel(path, sheet_name="test")

    # ---- TRAIN SPLIT ----
    X_train = train_df.drop(columns=[TARGET])
    y_train = train_df[TARGET].values

    # ---- TEST SPLIT ----
    # Keep the line for classification
    lines_test = test_df[LINE_COL].values

    # Build X_test/y_test
    X_test = test_df.drop(columns=[TARGET] + ODDS_COLS)
    y_test = test_df[TARGET].values

    return (
        X_train.values.astype(np.float32),
        y_train.astype(np.float32),
        X_test.values.astype(np.float32),
        y_test.astype(np.float32),
        lines_test.astype(np.float32)
    )

def build_model(input_dim):
    model = Sequential([
        Input(shape=(input_dim,)),
        Dense(64, activation="relu"),
        Dense(32, activation="relu"),
        Dense(16, activation="relu"),
        Dense(1, activation="linear")
    ])
    model.compile(
        optimizer=Adam(1e-3),
        loss="mse",
        metrics=["mae"]
    )
    return model

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

def main():
    # 1) Load data
    X_train, y_train, X_test, y_test, lines_test = load_data(DATA_FILE)
    print(f" → X_train: {X_train.shape}, y_train: {y_train.shape}")
    print(f" → X_test:  {X_test.shape},  y_test:  {y_test.shape}\n")

    # 2) Build & train
    model = build_model(X_train.shape[1])
    es = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True, verbose=1)

    print("Training regression model…")
    model.fit(
        X_train, y_train,
        validation_split=0.2,
        epochs=100,
        batch_size=32,
        callbacks=[es],
        verbose=2
    )

    # 3) Regression metrics on test
    print("\nEvaluating regression performance on test set…")
    y_pred = model.predict(X_test).flatten()
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"  • Test MSE: {mse:.4f}")
    print(f"  • Test MAE: {mae:.4f}\n")

    # 4) Regression metrics on test
    print("\nEvaluating regression performance on test set…")
    y_pred = model.predict(X_test).flatten()
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"  • Test MSE: {mse:.4f}")
    print(f"  • Test MAE: {mae:.4f}\n")

    # 5) Filter out any samples missing the line
    mask = ~np.isnan(lines_test)
    if np.sum(~mask) > 0:
        print(f"Note: Skipping {np.sum(~mask)} samples with missing TotalRunsLine for classification metrics.\n")
    y_test_cls    = y_test[mask]
    y_pred_cls    = y_pred[mask]
    lines_test_cls = lines_test[mask]

    # 6) Binarize into Over/Under
    actual_ov = (y_test_cls > lines_test_cls).astype(int)
    pred_ov   = (y_pred_cls > lines_test_cls).astype(int)

    # 7) Classification metrics
    acc  = accuracy_score(actual_ov, pred_ov)
    prec = precision_score(actual_ov, pred_ov)
    rec  = recall_score(actual_ov, pred_ov)
    f1   = f1_score(actual_ov, pred_ov)
    cm   = confusion_matrix(actual_ov, pred_ov)

    print("Over/Under classification metrics:")
    print(f"  • Accuracy : {acc:.3f}")
    print(f"  • Precision: {prec:.3f}")
    print(f"  • Recall   : {rec:.3f}")
    print(f"  • F1 Score : {f1:.3f}")
    print("  • Confusion matrix (actual rows × predicted cols):")
    print(cm, "\n")

    # 8) Probabilistic metrics via sigmoid‑distance
    prob_ov = sigmoid(y_pred_cls - lines_test_cls)
    # Brier score
    brier = brier_score_loss(actual_ov, prob_ov)
    # ROC AUC (only if both classes are present)
    if len(np.unique(actual_ov)) == 2:
        rocauc = roc_auc_score(actual_ov, prob_ov)
        print("Calibration / probabilistic metrics:")
        print(f"  • Brier score (lower better): {brier:.4f}")
        print(f"  • ROC AUC (higher better):   {rocauc:.4f}")
    else:
        print(f"Only one class present after filtering; skipping ROC AUC. Brier: {brier:.4f}")


if __name__ == "__main__":
    main()
