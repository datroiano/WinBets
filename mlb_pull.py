#!/usr/bin/env python3
"""
mlb_match_with_stadium_and_extras.py

Reads 'input.xlsx' (Odds API events), fetches MLB Stats API schedules
to retrieve GameID, StadiumID, HomeScore, AwayScore, TotalRuns, then
splits into two sheets:

  • 'Main'   ← rows where all new fields are populated
  • 'Extras' ← rows where any new field is missing

Writes out 'stats_plus_odds.xlsx'.
"""

import pandas as pd
import requests
import re

# ─── Configuration ───────────────────────────────────────────────────────────────
INPUT_FILE   = "input.xlsx"
OUTPUT_FILE  = "stats_plus_odds.xlsx"
BASE_URL     = "https://statsapi.mlb.com/api/v1"
SCHEDULE_EP  = "/schedule"

# ─── Helpers ────────────────────────────────────────────────────────────────────
def normalize_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def fetch_schedule_for_season(season: int) -> pd.DataFrame:
    url = BASE_URL + SCHEDULE_EP
    params = {
        "sportId":   1,
        "season":    season,
        "gameTypes": "R",
        "hydrate":   "teams,venue"
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json().get("dates", [])

    records = []
    for day in data:
        for g in day.get("games", []):
            dt = pd.to_datetime(g["gameDate"], utc=True).date()
            home = g["teams"]["home"]["team"]["name"]
            away = g["teams"]["away"]["team"]["name"]
            records.append({
                "game_date":   dt,
                "home_norm":   normalize_name(home),
                "away_norm":   normalize_name(away),
                "home_score":  g["teams"]["home"].get("score"),
                "away_score":  g["teams"]["away"].get("score"),
                "GameID":      g["gamePk"],
                "StadiumID":   g.get("venue", {}).get("id"),
            })
    return pd.DataFrame(records)

# ─── Main ───────────────────────────────────────────────────────────────────────
def main():
    # Load input
    df = pd.read_excel(INPUT_FILE, dtype={"id": str})

    # Extract date and normalize names
    df["game_date"] = pd.to_datetime(df["commence_time"], utc=True).dt.date
    df["home_norm"] = df["home_team"].apply(normalize_name)
    df["away_norm"] = df["away_team"].apply(normalize_name)
    df["season"]    = df["game_date"].apply(lambda d: d.year)

    # Prepare new columns
    for col in ("GameID","HomeScore","AwayScore","TotalRuns","StadiumID"):
        df[col] = pd.NA

    # Fetch schedules per season
    sched_frames = []
    for season in sorted(df["season"].unique()):
        print(f"Fetching MLB schedule for {season} …")
        sched_frames.append(fetch_schedule_for_season(season))
    sched_all = pd.concat(sched_frames, ignore_index=True)

    # Match and populate
    for idx, row in df.iterrows():
        subset = sched_all[sched_all["game_date"] == row["game_date"]]
        candidates = subset[
            (
                (subset["home_norm"] == row["home_norm"]) &
                (subset["away_norm"] == row["away_norm"])
            ) | (
                (subset["home_norm"] == row["away_norm"]) &
                (subset["away_norm"] == row["home_norm"])
            )
        ]
        if not candidates.empty:
            match = candidates.iloc[0]
            # Assign scores in correct orientation
            if normalize_name(row["home_team"]) == match["home_norm"]:
                df.at[idx, "HomeScore"] = match["home_score"]
                df.at[idx, "AwayScore"] = match["away_score"]
            else:
                df.at[idx, "HomeScore"] = match["away_score"]
                df.at[idx, "AwayScore"] = match["home_score"]
            df.at[idx, "GameID"]    = match["GameID"]
            df.at[idx, "StadiumID"] = match["StadiumID"]

    # Compute TotalRuns
    df["TotalRuns"] = (
        df["HomeScore"].astype("Int64") +
        df["AwayScore"].astype("Int64")
    )

    # Split into Main vs Extras
    new_cols = ["GameID","HomeScore","AwayScore","TotalRuns","StadiumID"]
    mask_perfect = df[new_cols].notna().all(axis=1)
    df_main   = df[mask_perfect].copy()
    df_extras = df[~mask_perfect].copy()

    # Drop helper columns
    drop_cols = ["game_date","home_norm","away_norm","season"]
    df_main.drop(columns=[c for c in drop_cols if c in df_main], inplace=True)
    df_extras.drop(columns=[c for c in drop_cols if c in df_extras], inplace=True)

    # Write to Excel with two sheets
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df_main.to_excel(writer, sheet_name="Main", index=False)
        df_extras.to_excel(writer, sheet_name="Extras", index=False)

    print(f"✓ Wrote {len(df_main)} complete rows to 'Main' and "
          f"{len(df_extras)} incomplete rows to 'Extras' in '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()
