#!/usr/bin/env python3
"""
get_weather.py

Reads 'input_with_odds.xlsx', filters out rows without OverUnderTotal,
fetches 3‑hour average weather (temperature, humidity, wind speed/direction,
condition) around each GameDate using the Open‑Meteo Archive API (m/s units),
converts to °F and mph, and writes the enriched data to 'weather_ready.xlsx'.
"""

import requests
import math
from collections import Counter
from datetime import datetime, timedelta
import pandas as pd

def get_3hr_weather_avg(game_date_str, latitude, longitude):
    """
    Fetch historical weather data from the Open‑Meteo Archive API in m/s,
    then compute 3‑hour averages for temperature (°C), relative humidity (%),
    wind speed (m/s), wind direction (°), and the most common weather condition.

    :param game_date_str: str, 'YYYY‑MM‑DD HH:MM:SS'
    :param latitude: float
    :param longitude: float
    :return: dict with keys:
        - average_temperature_C
        - average_humidity_percent
        - average_wind_speed_m_s
        - average_wind_direction_degrees
        - most_common_condition
    """
    # Parse the input datetime
    dt = datetime.strptime(game_date_str, '%Y-%m-%d %H:%M:%S')

    # Build a ±1.5 hour window
    start_window = dt - timedelta(hours=1.5)
    end_window   = dt + timedelta(hours=1.5)

    # API expects YYYY‑MM‑DD date strings
    start_date = start_window.date().isoformat()
    end_date   = end_window.date().isoformat()

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        # request wind_speed in m/s explicitly
        "hourly": "temperature_2m,relativehumidity_2m,wind_speed_10m,wind_direction_10m,weathercode",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})

    temps, hums, winds, wind_dirs_rad, codes = [], [], [], [], []
    for time_str, temp, hum, wspd, wdir, code in zip(
        hourly.get("time", []),
        hourly.get("temperature_2m", []),
        hourly.get("relativehumidity_2m", []),
        hourly.get("wind_speed_10m", []),
        hourly.get("wind_direction_10m", []),
        hourly.get("weathercode", []),
    ):
        t = datetime.fromisoformat(time_str)
        if start_window <= t <= end_window:
            temps.append(temp)
            hums.append(hum)
            winds.append(wspd)
            wind_dirs_rad.append(math.radians(wdir))
            codes.append(code)

    if not temps:
        raise ValueError("No weather data available in the 3‑hour window")

    # Arithmetic means
    avg_temp = sum(temps) / len(temps)
    avg_hum  = sum(hums) / len(hums)
    avg_wind = sum(winds) / len(winds)

    # Circular mean for wind direction
    sin_sum = sum(math.sin(rad) for rad in wind_dirs_rad)
    cos_sum = sum(math.cos(rad) for rad in wind_dirs_rad)
    avg_dir = math.degrees(math.atan2(sin_sum/len(wind_dirs_rad),
                                      cos_sum/len(wind_dirs_rad))) % 360

    # Map the most frequent weather code to text
    most_code = Counter(codes).most_common(1)[0][0]
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
    condition = weather_map.get(most_code, "Unknown")

    return {
        "average_temperature_C":        avg_temp,
        "average_humidity_percent":     avg_hum,
        "average_wind_speed_m_s":       avg_wind,
        "average_wind_direction_degrees": avg_dir,
        "most_common_condition":        condition,
    }


# Example usage
if __name__ == "__main__":
    import pandas as pd

    # ——— manually set your stadium coordinates here ———
    latitude  =  40.82919482
    longitude =  -73.9264977

    # 1. Load & filter input
    df = pd.read_excel("input_with_odds.xlsx")
    df = df.drop(columns=["OverUnderLine"])
    df = df[df["OverUnderTotal"].notna()].reset_index(drop=True)

    # 2. Collect weather stats
    temps_C, hums, winds_ms, wind_dirs = [], [], [], []
    for _, row in df.iterrows():
        gd = row["GameDate"]
        if not isinstance(gd, str):
            gd = gd.strftime("%Y-%m-%d %H:%M:%S")
        w = get_3hr_weather_avg(gd, latitude, longitude)
        temps_C.append(w["average_temperature_C"])
        hums.append(w["average_humidity_percent"])
        winds_ms.append(w["average_wind_speed_m_s"])
        wind_dirs.append(w["average_wind_direction_degrees"])

    # 3. Convert & append new columns
    MS_TO_MPH = 3600.0 / 1609.344  # exact m/s → mph factor
    df["AverageTempF"] = [round(c * 9 / 5 + 32, 1) for c in temps_C]
    df["AverageHumidity"] = [round(h, 1) for h in hums]
    df["AverageWindSpeedMph"] = [round(m * MS_TO_MPH, 1) for m in winds_ms]
    df["AverageWindDirection"] = [round(d, 0) for d in wind_dirs]

    # 4. Save to new Excel
    df.to_excel("weather_ready.xlsx", index=False)

    print("Done: weather_ready.xlsx created with weather data.")

