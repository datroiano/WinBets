#!/usr/bin/env python3
import pandas as pd
import requests
import time
from datetime import timedelta
from requests.exceptions import RequestException

# ─── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY       = '2660cfe22b77a02d11bc68724386a685'
SPORT_KEY     = 'baseball_mlb'
REGIONS       = 'us'
MARKETS       = 'totals'
ODDS_FORMAT   = 'decimal'
API_MAX_LINES = 5        # max_lines parameter to the odds endpoint

INPUT_FILE    = 'stats_v3.xlsx'
OUTPUT_FILE   = 'stats_v4.xlsx'
SHEETS        = ['Main', 'IndoorExtras']

# ─── helper: GET with retry on 429 only ──────────────────────────────────────────
def safe_get(url, params, retries=3, backoff=60):
    for attempt in range(1, retries+1):
        try:
            resp = requests.get(url, params=params, timeout=10)
        except RequestException as e:
            print(f"⚠️  Request error: {e}")
            return None

        if resp.status_code == 429:
            print(f"⚠️  Rate limit (429). Sleeping {backoff}s before retry {attempt}/{retries}.")
            time.sleep(backoff)
            continue
        if resp.status_code == 404:
            # no data here
            return None
        try:
            resp.raise_for_status()
        except RequestException as e:
            print(f"⚠️  HTTP error {resp.status_code}: {e}")
            return None
        return resp
    print(f"❌  Failed after {retries} retries for URL {url}")
    return None

# ─── fetch snapshot timestamp for a given event/time ───────────────────────────
def get_snapshot_ts(event_id: str, game_time_iso: str) -> str | None:
    url = f"https://api.the-odds-api.com/v4/historical/sports/{SPORT_KEY}/events"
    params = {
        'apiKey':   API_KEY,
        'date':     game_time_iso,
        'eventIds': event_id
    }
    resp = safe_get(url, params)
    if not resp:
        return None
    info = resp.json() or {}
    return info.get('timestamp')

# ─── fetch the historical totals odds for one event at a snapshot ──────────────
def fetch_historical_totals(event_id: str, snapshot_ts: str) -> dict:
    url = (
        f"https://api.the-odds-api.com/v4/historical/"
        f"sports/{SPORT_KEY}/events/{event_id}/odds"
    )
    params = {
        'apiKey':     API_KEY,
        'date':       snapshot_ts,
        'regions':    REGIONS,
        'markets':    MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'max_lines':  API_MAX_LINES
    }
    resp = safe_get(url, params)
    if not resp:
        return dict.fromkeys(
            ['TotalRunsLine','TotalOverOdds','TotalUnderOdds','Sportbook'],
            None
        )

    payload = resp.json() or {}
    data    = payload.get('data', {})
    for book in data.get('bookmakers', []):
        for market in book.get('markets', []):
            if market.get('key') == MARKETS:
                outcomes = market.get('outcomes', [])
                over  = next((o for o in outcomes if o['name']=='Over'),  None)
                under = next((o for o in outcomes if o['name']=='Under'), None)
                if over and under:
                    return {
                        'TotalRunsLine':  over.get('point'),
                        'TotalOverOdds':  over.get('price'),
                        'TotalUnderOdds': under.get('price'),
                        'Sportbook':      book.get('key')
                    }
    return dict.fromkeys(
        ['TotalRunsLine','TotalOverOdds','TotalUnderOdds','Sportbook'],
        None
    )

# ─── main ───────────────────────────────────────────────────────────────────────
def main():
    writer = pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl')

    for sheet in SHEETS:
        df = pd.read_excel(INPUT_FILE, sheet_name=sheet)

        # parse and drop any timezone info
        df['commence_time'] = (
            pd.to_datetime(df['commence_time'])
              .dt.tz_localize(None)
        )

        # ensure odds columns exist
        odds_cols = [
            'TotalRunsLine','TotalOverOdds','TotalUnderOdds',
            'Sportbook','Outcome','OverPayout','UnderPayout'
        ]
        for col in odds_cols:
            if col not in df.columns:
                df[col] = None

        # identify rows where ALL odds columns are blank
        missing = df[odds_cols].isna().all(axis=1)

        print(f"\n⏳ Sheet '{sheet}': {missing.sum()} rows with missing odds to update")

        for idx in df[missing].index:
            row = df.loc[idx]
            eid = row['id']
            iso = row['commence_time'].strftime('%Y-%m-%dT%H:%M:%SZ')
            print(f"  → Updating row {idx} (event_id={eid})")

            # 1) get the right snapshot timestamp
            ts = get_snapshot_ts(eid, iso)
            if not ts:
                print(f"      ⚠️  no snapshot for {eid}, skipping")
                continue

            # 2) fetch odds at that snapshot
            odds = fetch_historical_totals(eid, ts)
            df.at[idx, 'TotalRunsLine']  = odds['TotalRunsLine']
            df.at[idx, 'TotalOverOdds']  = odds['TotalOverOdds']
            df.at[idx, 'TotalUnderOdds'] = odds['TotalUnderOdds']
            df.at[idx, 'Sportbook']      = odds['Sportbook']

            # compute Outcome & Payouts if line available
            line = odds['TotalRunsLine']
            if line is None:
                print(f"      ⚠️  no totals line for {eid}, skipping outcome/payout")
                continue

            actual = row.get('TotalRuns', 0)
            over_o = odds['TotalOverOdds'] or 0
            under_o= odds['TotalUnderOdds'] or 0

            if   actual == line: outcome = 'Push'
            elif actual >  line: outcome = 'Over'
            else:                 outcome = 'Under'
            df.at[idx, 'Outcome'] = outcome

            # $100 bet payouts
            if   outcome == 'Over':  df.at[idx,'OverPayout'], df.at[idx,'UnderPayout'] = 100*over_o, 0
            elif outcome == 'Under': df.at[idx,'OverPayout'], df.at[idx,'UnderPayout'] = 0, 100*under_o
            else:                     df.at[idx,'OverPayout'], df.at[idx,'UnderPayout'] = 100, 100

            print(
                f"      → line={line}, over={over_o}, under={under_o}, "
                f"outcome={outcome}"
            )

        # write updated sheet
        df.to_excel(writer, sheet_name=sheet, index=False)
        print(f"✅ Finished sheet '{sheet}'")

    writer._save()
    print(f"\n🎉 All done → {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
