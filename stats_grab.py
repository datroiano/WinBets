#!/usr/bin/env python3

import requests
import pandas as pd
import math
import time
from collections import Counter
from datetime import datetime, timedelta

from stadiums_store import stadium_data

# ─── SETTINGS ───────────────────────────────────────────────────────────────────
SEASONS   = ['2022','2023', '2024', '2025']
STADIUMS  = ['3313', '1', '4']   # StadiumID strings to include
API_KEY   = "2660cfe22b77a02d11bc68724386a685"

# ─── FETCH GAMES ────────────────────────────────────────────────────────────────
def fetch_games_for_stadiums(seasons, stadium_ids, stadiums_info):
    print(f"Fetching games for stadiums {stadium_ids} in seasons {seasons}...")
    all_games = []
    url = "https://statsapi.mlb.com/api/v1/schedule"

    for season in seasons:
        params = {
            "sportId": 1,
            "season": season,
            "gameTypes": "R",
            "hydrate": "venue,teams"
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()

        for date_entry in resp.json().get("dates", []):
            for g in date_entry.get("games", []):
                sid = str(g.get("venue", {}).get("id", ""))
                if sid not in stadium_ids:
                    continue

                away_score = g["teams"]["away"].get("score")
                home_score = g["teams"]["home"].get("score")
                if away_score is None or home_score is None:
                    continue

                all_games.append({
                    "GameDate":       g.get("gameDate"),        # ISO timestamp
                    "GameID":         g.get("gamePk"),
                    "StadiumID":      sid,
                    "CompassBearing": stadiums_info[sid]["CompassBearing"],
                    "AwayScore":      away_score,
                    "HomeScore":      home_score,
                    "TotalRuns":      away_score + home_score,
                })

    print(f"  → Found {len(all_games)} games with scores\n")
    return all_games

# ─── FETCH ODDS ────────────────────────────────────────────────────────────────
def fetch_odds_for_games(games):
    """
    Fetch totals lines & odds via the per‑event historical odds endpoint.
    Loops through each GameID and pulls its snapshot at GameDate.
    """
    print("Fetching odds per event ID...")
    out = []
    skipped = 0
    session = requests.Session()
    session.headers.update({'User-Agent': 'WinBetsStatsGrabber/1.0'})
    base_url = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events"
    total = len(games)

    for i, g in enumerate(games, start=1):
        event_id   = g["GameID"]
        game_date  = g["GameDate"]
        print(f"[{i}/{total}] Event {event_id} at {game_date} …", end=" ")

        url = f"{base_url}/{event_id}/odds"
        params = {
            "apiKey":     API_KEY,
            "regions":    "us",
            "markets":    "totals",
            "date":       game_date,
            "oddsFormat": "american"
        }

        try:
            resp = session.get(url, params=params, timeout=10)

            # retry once on rate limit
            if resp.status_code == 429:
                time.sleep(1)
                resp = session.get(url, params=params, timeout=10)
                if resp.status_code == 429:
                    skipped += 1
                    print("rate limited, skipping")
                    continue

            # skip if no odds
            if resp.status_code == 422:
                skipped += 1
                print("no odds data, skipping")
                continue

            resp.raise_for_status()
            body = resp.json()
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 422:
                skipped += 1
                print("no odds data, skipping")
                continue
            print(f"HTTP {code}, skipping")
            skipped += 1
            continue
        except Exception as e:
            print(f"error {e}, skipping")
            skipped += 1
            continue

        event = body.get("data")
        if not event:
            skipped += 1
            print("no data field, skipping")
            continue

        # locate the totals market
        totals = None
        for bm in event.get("bookmakers", []):
            for m in bm.get("markets", []):
                if m.get("key") == "totals":
                    totals = m
                    break
            if totals:
                break

        if not totals:
            skipped += 1
            print("no totals market, skipping")
            continue

        # extract line & odds from the outcomes
        line = None
        over_odds = under_odds = None
        for oc in totals.get("outcomes", []):
            if oc.get("name") == "Over":
                over_odds = oc.get("price")
                line      = oc.get("point")
            elif oc.get("name") == "Under":
                under_odds = oc.get("price")
                line       = oc.get("point")

        if line is None or over_odds is None or under_odds is None:
            skipped += 1
            print(f"incomplete odds (line={line}, over={over_odds}, under={under_odds}), skipping")
            continue

        g["TotalRunLine"] = line
        g["OddsOver"]     = over_odds
        g["OddsUnder"]    = under_odds
        out.append(g)
        print("ok")

    print(f"Fetched odds for {len(out)} games; skipped {skipped}")
    return out




# ─── FETCH WEATHER ─────────────────────────────────────────────────────────────
def get_2hr_weather_avg(game_date_str, latitude, longitude):
    dt = datetime.strptime(game_date_str, "%Y-%m-%dT%H:%M:%SZ")
    start, end = dt - timedelta(hours=1), dt + timedelta(hours=1)

    resp = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": latitude, "longitude": longitude,
            "start_date": start.date().isoformat(),
            "end_date":   end.date().isoformat(),
            "hourly":     "temperature_2m,relativehumidity_2m,wind_speed_10m,wind_direction_10m,weathercode",
            "wind_speed_unit": "ms",
            "timezone": "auto",
        },
        timeout=10
    )
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})

    temps, hums, winds, dirs_rad, codes = [], [], [], [], []
    for t_str, temp, hum, wspd, wdir, code in zip(
        hourly.get("time", []),
        hourly.get("temperature_2m", []),
        hourly.get("relativehumidity_2m", []),
        hourly.get("wind_speed_10m", []),
        hourly.get("wind_direction_10m", []),
        hourly.get("weathercode", []),
    ):
        t = datetime.fromisoformat(t_str)
        if start <= t <= end:
            temps.append(temp); hums.append(hum)
            winds.append(wspd); dirs_rad.append(math.radians(wdir))
            codes.append(code)

    if not temps:
        raise ValueError("No weather data available in the 2‑hour window")

    avg_temp = sum(temps) / len(temps)
    avg_hum  = sum(hums) / len(hums)
    avg_wind = sum(winds) / len(winds)
    sin_sum = sum(math.sin(d) for d in dirs_rad)
    cos_sum = sum(math.cos(d) for d in dirs_rad)
    avg_dir = math.degrees(math.atan2(sin_sum/len(dirs_rad), cos_sum/len(dirs_rad))) % 360

    weather_map = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Dense drizzle", 56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain", 71: "Slight snow fall",
        73: "Moderate snow fall", 75: "Heavy snow fall", 77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
        96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    most_code = Counter(codes).most_common(1)[0][0]

    return {
        "average_temperature_C":            avg_temp,
        "average_humidity_percent":         avg_hum,
        "average_wind_speed_m_s":           avg_wind,
        "average_wind_direction_degrees":   avg_dir,
        "most_common_condition":            weather_map.get(most_code, "Unknown"),
    }

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    stadiums_info = { str(s["StadiumID"]): s for s in stadium_data }

    games = fetch_games_for_stadiums(SEASONS, STADIUMS, stadiums_info)
    games = fetch_odds_for_games(games)

    enriched = []
    for g in games:
        try:
            w = get_2hr_weather_avg(
                g["GameDate"],
                stadiums_info[g["StadiumID"]]["Latitude"],
                stadiums_info[g["StadiumID"]]["Longitude"]
            )
            g.update({
                "WindDirection":   w["average_wind_direction_degrees"],
                "WindSpeedMPH":    w["average_wind_speed_m_s"] * 2.23694,
                "TempF":           w["average_temperature_C"] * 9/5 + 32,
                "Humidity":        w["average_humidity_percent"],
            })
            enriched.append(g)
        except Exception as e:
            print(f"Skipping weather for game {g['GameID']}: {e}")

    print(f"Enriched {len(enriched)} games with weather data")

    df = pd.DataFrame(enriched)
    df.dropna(axis=1, how="all", inplace=True)

    if "TotalRuns" not in df.columns or "TotalRunLine" not in df.columns:
        print("Error: Required columns missing. Exiting.")
        return

    df["Differential"] = df["TotalRuns"] - df["TotalRunLine"]
    df["Into?"] = df.apply(
        lambda r: "Yes" if ((r["WindDirection"] - r["CompassBearing"] + 360) % 360) <= 45 or ((r["WindDirection"] - r["CompassBearing"] + 360) % 360) >= 315 else "No",
        axis=1
    )

    df.to_excel("mlb_stats.xlsx", index=False)
    print("Saved mlb_stats.xlsx")

if __name__ == "__main__":
    main()
