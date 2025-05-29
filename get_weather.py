#!/usr/bin/env python3
import pandas as pd
import requests
import time
import math
from datetime import timedelta

# ─── CONFIG ────────────────────────────────────────────────────────────────────
INPUT_FILE       = 'stats_v4.xlsx'
OUTPUT_FILE      = 'stats_v5.xlsx'
SHEETS           = ['Main', 'IndoorExtras']
MAX_ROWS         = None    # max rows per sheet for testing; set to None to do all
WEATHER_URL      = 'https://archive-api.open-meteo.com/v1/archive'

HOURLY_VARS = [
    'temperature_2m',
    'pressure_msl',
    'relative_humidity_2m',
    'dew_point_2m',
    'apparent_temperature',
    'wind_speed_10m',
    'wind_direction_10m',
    'wind_gusts_10m',
    'precipitation'
]

WEATHER_PARAMS = {
    'hourly':            ','.join(HOURLY_VARS),
    'temperature_unit':  'fahrenheit',
    'wind_speed_unit':   'mph',
    'timeformat':        'iso8601',
    'timezone':          'UTC'
}

def safe_fetch(params):
    """Fetch with one retry on failure."""
    for attempt in (1, 2):
        try:
            r = requests.get(WEATHER_URL, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"⚠️  Fetch attempt {attempt} failed: {e}")
            if attempt == 1:
                time.sleep(2)
    return None

def weighted_avg(vals, weights):
    total_w = 0.0
    cum     = 0.0
    for v, w in zip(vals, weights):
        if v is not None:
            cum     += v * w
            total_w += w
    return cum/total_w if total_w else None

def classify_wind(compass_bearing, wind_dir):
    diff = (wind_dir - compass_bearing + 360) % 360
    if diff <= 50 or diff >= 310:
        cat = 'Headwind'
    elif 130 <= diff <= 230:
        cat = 'Tailwind'
    else:
        cat = 'Crosswind'
    vec = math.cos(math.radians(diff))
    return cat, vec

def process_sheet(df):
    df['commence_time'] = pd.to_datetime(df['commence_time']).dt.tz_localize(None)

    new_cols = [
        'Temp_F', 'Pressure_msl',
        'RelHumidity', 'DewPoint', 'ApparentTemp',
        'WindSpeed_mph', 'WindDir', 'WindGusts_mph',
        'WindCategory', 'WindVector',
        'Precipitation'
    ]
    for c in new_cols:
        df[c] = None

    rows = df.index if MAX_ROWS is None else df.index[:MAX_ROWS]
    for idx in rows:
        row = df.loc[idx]
        lat = row['Latitude']
        lon = row['Longitude']
        start = row['commence_time']
        cbearing = row['CompassBearing']

        # align to top of the hour, then build 3‑hour window
        base = start.replace(minute=0, second=0, microsecond=0)
        times = [base + timedelta(hours=i) for i in range(3)]
        start_date = times[0].date().isoformat()
        end_date   = times[-1].date().isoformat()

        params = WEATHER_PARAMS.copy()
        params.update({
            'latitude':   lat,
            'longitude':  lon,
            'start_date': start_date,
            'end_date':   end_date
        })

        data = safe_fetch(params)
        if not data:
            print(f"❌  No weather data for row {idx}, skipping")
            continue

        hourly     = data.get('hourly', {})
        time_index = hourly.get('time', [])

        vals = {}
        for var in HOURLY_VARS:
            arr = hourly.get(var, [])
            # map the ISO strings to Timestamps
            mapping = {pd.to_datetime(t): v for t, v in zip(time_index, arr)}
            vals[var] = [mapping.get(t) for t in times]

        weights = [1.0, 1.0, 0.5]

        df.at[idx, 'Temp_F']       = weighted_avg(vals['temperature_2m'], weights)
        df.at[idx, 'Pressure_msl'] = weighted_avg(vals['pressure_msl'],    weights)
        df.at[idx, 'RelHumidity']  = weighted_avg(vals['relative_humidity_2m'], weights)
        df.at[idx, 'DewPoint']     = weighted_avg(vals['dew_point_2m'],    weights)
        df.at[idx, 'ApparentTemp'] = weighted_avg(vals['apparent_temperature'], weights)

        ws = weighted_avg(vals['wind_speed_10m'],    weights)
        wd = weighted_avg(vals['wind_direction_10m'],weights)
        wg = weighted_avg(vals['wind_gusts_10m'],    weights)
        df.at[idx, 'WindSpeed_mph'] = ws
        df.at[idx, 'WindDir']       = wd
        df.at[idx, 'WindGusts_mph'] = wg

        cat, vec = None, None
        if ws is not None and wd is not None:
            cat, vec = classify_wind(cbearing, wd)
            df.at[idx, 'WindCategory'] = cat
            df.at[idx, 'WindVector']   = ws * vec

        df.at[idx, 'Precipitation'] = weighted_avg(vals['precipitation'], weights)

        temp_str = f"{df.at[idx,'Temp_F']:.1f}" if df.at[idx,'Temp_F'] is not None else "N/A"
        ws_str   = f"{ws:.1f}"               if ws is not None           else "N/A"
        cat_str  = f" {cat}"                 if cat else ""
        print(f"✅  Row {idx} done: Temp={temp_str}F, Wind={ws_str}mph{cat_str}")

    return df

def main():
    writer = pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl')

    for sheet in SHEETS:
        print(f"\n--- Processing sheet '{sheet}' ---")
        df = pd.read_excel(INPUT_FILE, sheet_name=sheet)
        df = process_sheet(df)
        df.to_excel(writer, sheet_name=sheet, index=False)
        print(f"--- Finished '{sheet}' ---")

    writer._save()
    print(f"\n🎉 Saved as {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
w