#!/usr/bin/env python3
"""
eventids.py

Backfills MLB event IDs via The Odds API historical‑events endpoint,
day by day, from SINCE_SEASON → today, dedupes on `id`, writes to Excel.

Fixed to:
 • Skip (not break) on network errors and continue the day loop
 • Force normalize() to always emit the six target columns so astype() never KeyErrors
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# ─── Configuration ───────────────────────────────────────────────────────────────
API_KEY      = "2660cfe22b77a02d11bc68724386a685"
SPORT_KEY    = "baseball_mlb"
SINCE_SEASON = 2021
OUTPUT_FILE  = "input.xlsx"

HIST_EVENTS_URL = f"https://api.the-odds-api.com/v4/historical/sports/{SPORT_KEY}/events"

# ─── Helpers ────────────────────────────────────────────────────────────────────
def fetch_snapshot_events(snapshot_iso: str, window_start: str, window_end: str) -> list:
    params = {
        "apiKey":           API_KEY,
        "date":             snapshot_iso,
        "commenceTimeFrom": window_start,
        "commenceTimeTo":   window_end,
        "dateFormat":       "iso",
    }
    resp = requests.get(HIST_EVENTS_URL, params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    # Historical endpoint wraps in { data: [...] }
    return payload.get("data", payload)

def normalize(events: list) -> pd.DataFrame:
    cols = ["id","sport_key","sport_title","commence_time","home_team","away_team"]
    rows = []
    for e in events:
        rows.append({
            "id":            e["id"],
            "sport_key":     e["sport_key"],
            "sport_title":   e["sport_title"],
            "commence_time": e["commence_time"],
            "home_team":     e["home_team"],
            "away_team":     e["away_team"],
        })
    # Even if rows == [], this will give an empty DF with the right columns
    return pd.DataFrame(rows, columns=cols)

def load_previous(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        return pd.read_excel(path, dtype={"id": str})
    return pd.DataFrame(columns=["id","sport_key","sport_title","commence_time","home_team","away_team"])

def save_to_excel(df: pd.DataFrame, path: str):
    df.to_excel(path, index=False)


# ─── Main Backfill Loop ─────────────────────────────────────────────────────────
def main():
    start_date = datetime(SINCE_SEASON, 1, 1, tzinfo=timezone.utc)
    end_date   = datetime.now(timezone.utc)
    one_day    = timedelta(days=1)

    all_events = []
    day_cursor = start_date

    print(f"Backfilling MLB events via Odds API from {start_date.date()} → {end_date.date()}…")

    while day_cursor.date() <= end_date.date():
        snapshot     = day_cursor.replace(hour=0, minute=0, second=0).isoformat().replace("+00:00","Z")
        window_start = snapshot
        window_end   = (day_cursor + one_day).replace(hour=0, minute=0, second=0).isoformat().replace("+00:00","Z")

        try:
            events = fetch_snapshot_events(snapshot, window_start, window_end)
        except Exception as e:
            print(f"  [!] Error on {day_cursor.date()}: {e}  → skipping")
            # SKIP this day and continue
            day_cursor += one_day
            time.sleep(0.5)
            continue

        if events:
            print(f"  • {day_cursor.date()}: fetched {len(events)} events")
            all_events.extend(events)

        # brief pause so we don't slam the API
        time.sleep(0.5)
        day_cursor += one_day

    # ─── Normalize & Dedupe ───────────────────────────────────────────────────────
    print(f"\nNormalizing {len(all_events)} raw records…")
    df_new  = normalize(all_events).astype({"id": str})
    df_prev = load_previous(OUTPUT_FILE)
    df_all  = pd.concat([df_prev, df_new], ignore_index=True)

    before = len(df_all)
    df_all.drop_duplicates(subset=["id"], inplace=True)
    after  = len(df_all)
    print(f"Dropped {before-after} duplicates; {after} unique events total.")

    save_to_excel(df_all, OUTPUT_FILE)
    print(f"✓ Saved master list to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()
