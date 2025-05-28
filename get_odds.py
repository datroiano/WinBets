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

# processing limits
MAX_LINES     = 10000       # how many events per sheet to process
API_MAX_LINES = 5       # max_lines param for the odds call

INPUT_FILE    = 'stats_v2.xlsx'
OUTPUT_FILE   = 'stats_v3.xlsx'
SHEETS        = ['Main', 'IndoorExtras']

# **Make this tz-naive** so it compares cleanly to your tz-naive column
HISTORICAL_CUTOFF = pd.to_datetime('2023-05-03T05:30:00').tz_localize(None)

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
            return None
        try:
            resp.raise_for_status()
        except RequestException as e:
            print(f"⚠️  HTTP error {resp.status_code}: {e}")
            return None
        return resp
    print(f"❌  Failed after {retries} retries.")
    return None

def get_snapshot_ts(event_id, game_time_iso):
    url = f"https://api.the-odds-api.com/v4/historical/sports/{SPORT_KEY}/events"
    params = {
        'apiKey':   API_KEY,
        'date':     game_time_iso,
        'eventIds': event_id
    }
    print(f"      * fetching snapshot_ts for {event_id} at {game_time_iso}")
    resp = safe_get(url, params)
    if not resp:
        return None
    return resp.json().get('timestamp')

def fetch_historical_totals(event_id, snapshot_ts):
    url = f"https://api.the-odds-api.com/v4/historical/sports/{SPORT_KEY}/events/{event_id}/odds"
    params = {
        'apiKey':     API_KEY,
        'date':       snapshot_ts,
        'regions':    REGIONS,
        'markets':    MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'max_lines':  API_MAX_LINES
    }
    print(f"      * fetching odds for {event_id} at {snapshot_ts}")
    resp = safe_get(url, params)
    if not resp:
        return dict.fromkeys(
            ['TotalRunsLine','TotalOverOdds','TotalUnderOdds','Sportbook'],
            None
        )

    data = resp.json().get('data', {})
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
    print(f"⚠️  totals market missing for {event_id}@{snapshot_ts}")
    return dict.fromkeys(
        ['TotalRunsLine','TotalOverOdds','TotalUnderOdds','Sportbook'],
        None
    )

def main():
    writer = pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl')

    for sheet in SHEETS:
        df = pd.read_excel(INPUT_FILE, sheet_name=sheet)
        # parse to datetime and drop any timezone
        df['commence_time'] = (
            pd.to_datetime(df['commence_time'])
              .dt.tz_localize(None)
        )

        # split into old vs new based on the cutoff
        df_old = df[df['commence_time'] < HISTORICAL_CUTOFF].copy()
        df_new = df[df['commence_time'] >= HISTORICAL_CUTOFF].copy()

        # add placeholder columns to both
        cols = ['TotalRunsLine','TotalOverOdds','TotalUnderOdds',
                'Sportbook','Outcome','OverPayout','UnderPayout']
        for c in cols:
            df_old[c] = None
            df_new[c] = None

        total  = len(df_new)
        limit  = min(total, MAX_LINES)
        print(f"\n⏳ Sheet '{sheet}': {total} to process, limiting to {limit}")

        processed = 0
        for idx, row in df_new.iterrows():
            if processed >= limit:
                break

            eid = row['id']
            iso = row['commence_time'].strftime('%Y-%m-%dT%H:%M:%SZ')
            print(f"  → [{sheet}] #{processed+1}/{limit} eid={eid}")

            ts = get_snapshot_ts(eid, iso)
            if not ts:
                print(f"      ⚠️ no snapshot for {eid}")
            else:
                odds = fetch_historical_totals(eid, ts)
                df_new.at[idx, 'TotalRunsLine']  = odds['TotalRunsLine']
                df_new.at[idx, 'TotalOverOdds']  = odds['TotalOverOdds']
                df_new.at[idx, 'TotalUnderOdds'] = odds['TotalUnderOdds']
                df_new.at[idx, 'Sportbook']      = odds['Sportbook']

                line   = odds['TotalRunsLine']
                over_o = odds['TotalOverOdds'] or 0
                under_o= odds['TotalUnderOdds'] or 0
                actual = row.get('TotalRuns', 0)

                if   line is None:  outcome = None
                elif actual == line: outcome = 'Push'
                elif actual >  line: outcome = 'Over'
                else:                outcome = 'Under'
                df_new.at[idx, 'Outcome'] = outcome

                if   outcome == 'Over':  over_p, under_p = 100*over_o, 0
                elif outcome == 'Under': over_p, under_p = 0, 100*under_o
                elif outcome == 'Push':  over_p, under_p = 100, 100
                else:                    over_p, under_p = None, None
                df_new.at[idx, 'OverPayout']  = over_p
                df_new.at[idx, 'UnderPayout'] = under_p

                print(f"      → line={line}, over={over_o}, under={under_o}, book={odds['Sportbook']}; outcome={outcome}, payouts={over_p}/{under_p}")

            processed += 1

        # write both updated and old sheets
        df_new.to_excel(writer,          sheet_name=sheet,        index=False)
        df_old.to_excel(writer,          sheet_name=f"{sheet}Old", index=False)
        print(f"✅ Finished '{sheet}' ({processed} processed), moved {len(df_old)} to '{sheet}Old'.")

    writer._save()
    print(f"\n🎉 All done → {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
