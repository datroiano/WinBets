#!/usr/bin/env python3
import pandas as pd
import numpy as np

# ─── CONFIG ────────────────────────────────────────────────────────────────────
INPUT_FILE   = 'stats_final.xlsx'
OUTPUT_FILE  = 'agg_stats.xlsx'
SHEETS       = ['Main', 'IndoorExtras']
TEMP_BINS    = 4     # quartiles
WIND_STRONG_THRESHOLD = 10  # mph

def compute_aggregates(df):
    # Create binary outcome (1 if actual > line, 0 if < line; drop pushes)
    df = df.copy()
    df = df[df['Outcome'] != 'Push']
    df['BinaryOutcome'] = (df['Outcome'] == 'Over').astype(int)

    # Wind strong category
    df['WindStrongCat'] = df['WindCategory'] + np.where(
        df['WindSpeed_mph'] > WIND_STRONG_THRESHOLD, '_Strong', '_Weak'
    )

    # Temperature quartile
    df['TempQuartile'] = pd.qcut(df['Temp_F'], TEMP_BINS, labels=[f"Q{i+1}" for i in range(TEMP_BINS)])

    # Precipitation flag
    df['PrecipFlag'] = np.where(df['Precipitation'] > 0, 'Wet', 'Dry')

    # Numeric cols for correlation
    num_cols = [
        'Differential', 'BinaryOutcome',
        'Temp_F', 'Pressure_msl', 'RelHumidity', 'DewPoint', 'ApparentTemp',
        'WindSpeed_mph', 'WindGusts_mph', 'Precipitation'
    ]
    corr = df[num_cols].corr()

    # Aggregations by binary outcome
    by_outcome = df.groupby('BinaryOutcome').agg({
        'Differential': ['count','mean','std'],
        'Temp_F':       ['mean','std'],
        'WindSpeed_mph':['mean','std'],
        'Precipitation':['mean','std']
    })

    # Aggregations by wind category
    by_wind_cat = df.groupby('WindCategory').agg({
        'Differential': ['count','mean','std'],
        'BinaryOutcome':['mean']
    }).rename(columns={'mean':'WinRate'})

    # Aggregations by wind strong category
    by_wind_strong = df.groupby('WindStrongCat').agg({
        'Differential': ['count','mean','std'],
        'BinaryOutcome':['mean']
    }).rename(columns={'mean':'WinRate'})

    # Aggregations by temp quartile
    by_temp_q = df.groupby('TempQuartile').agg({
        'Differential': ['count','mean','std'],
        'BinaryOutcome':['mean']
    }).rename(columns={'mean':'WinRate'})

    # Aggregations by precipitation flag
    by_precip = df.groupby('PrecipFlag').agg({
        'Differential': ['count','mean','std'],
        'BinaryOutcome':['mean']
    }).rename(columns={'mean':'WinRate'})

    return {
        'correlations':       corr,
        'by_outcome':         by_outcome,
        'by_wind_category':   by_wind_cat,
        'by_wind_strong':     by_wind_strong,
        'by_temp_quartile':   by_temp_q,
        'by_precip_flag':     by_precip
    }

def main():
    writer = pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl')

    for sheet in SHEETS:
        print(f"Processing sheet: {sheet}")
        df = pd.read_excel(INPUT_FILE, sheet_name=sheet)
        agg = compute_aggregates(df)

        # write each table to its own sheet
        agg['correlations'].to_excel(writer, sheet_name=f"{sheet}_corr")
        agg['by_outcome'].to_excel(writer, sheet_name=f"{sheet}_outcome")
        agg['by_wind_category'].to_excel(writer, sheet_name=f"{sheet}_windcat")
        agg['by_wind_strong'].to_excel(writer, sheet_name=f"{sheet}_windstrong")
        agg['by_temp_quartile'].to_excel(writer, sheet_name=f"{sheet}_tempq")
        agg['by_precip_flag'].to_excel(writer, sheet_name=f"{sheet}_precip")

    writer._save()
    print(f"\nAggregated statistics saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
