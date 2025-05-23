# fetch_historical_odds.py

import pandas as pd
import requests
import time
import logging
from datetime import datetime

# === CONFIGURATION ===
API_KEY = "2660cfe22b77a02d11bc68724386a685"  # ← Replace with your Odds API key
INPUT_FILE = "input.xlsx"
SHEET_NAME = "Primary"
OUTPUT_FILE = "input_with_odds.xlsx"

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# === UTILITY FUNCTIONS ===
def american_to_decimal(american_odds: float) -> float:
    """
    Convert American odds to decimal odds.
    """
    if american_odds is None:
        return None
    if american_odds > 0:
        return round(american_odds / 100.0 + 1.0, 2)
    else:
        return round(100.0 / abs(american_odds) + 1.0, 2)


def fetch_event_id(game_date_iso: str):
    """
    Fetch the Odds API event ID for the given MLB historical date and time.
    """
    url = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events"
    params = {
        "apiKey": API_KEY,
        "date": game_date_iso
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    for ev in data:
        if ev.get("commence_time") == game_date_iso:
            return ev.get("id")
    return None


def fetch_totals_for_event(event_id: str, game_date_iso: str):
    """
    Fetch the over/under totals market for a specific Odds API event ID.
    Returns (point, decimal_odds) tuple.
    """
    url = f"https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "totals",
        "date": game_date_iso,
        "oddsFormat": "american"
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    event = resp.json().get("data", {})
    for book in event.get("bookmakers", []):
        for market in book.get("markets", []):
            if market.get("key") == "totals":
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == "Over":
                        point = outcome.get("point")
                        price = outcome.get("price")
                        return point, american_to_decimal(price)
    return None, None


# === MAIN SCRIPT ===
def main():
    # Load Excel sheet
    df = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)

    # Debug: print available columns
    logging.info(f"Columns in sheet: {list(df.columns)}")

    # Prepare output columns
    df["OverUnderTotal"] = None
    df["Odds"] = None

    total_games = len(df)
    logging.info(f"Processing {total_games} games from {INPUT_FILE}")

    for idx, row in df.iterrows():
        game_id = row.get("GameID")  # Corrected column name
        game_date = row.get("GameDate")  # Corrected column name

        # Validate fields
        if pd.isna(game_id) or pd.isna(game_date):
            logging.error(f"Missing data for row {idx + 1}: GameID or GameDate is null. Skipping.")
            continue

        # Construct ISO8601 timestamp with 'Z'
        if isinstance(game_date, datetime):
            iso_dt = game_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            try:
                dt = datetime.fromisoformat(str(game_date))
                iso_dt = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                logging.error(f"Invalid GameDate format for row {idx + 1}: {game_date}. Skipping.")
                continue

        logging.info(f"[{idx + 1}/{total_games}] Fetching event ID for game {game_id} on {iso_dt}")
        try:
            event_id = fetch_event_id(iso_dt)
        except Exception as e:
            logging.error(f"Error fetching event list for {iso_dt}: {e}")
            continue

        if not event_id:
            logging.error(f"No event ID found for GameID {game_id} at {iso_dt}. Skipping.")
            continue

        logging.info(f"Found event ID {event_id}; fetching totals odds")
        try:
            point, dec_odds = fetch_totals_for_event(event_id, iso_dt)
        except Exception as e:
            logging.error(f"Error fetching odds for event {event_id}: {e}")
            continue

        if point is None:
            logging.error(f"No totals market found for event {event_id}. Skipping.")
            continue

        # Assign to DataFrame
        df.at[idx, "OverUnderTotal"] = point
        df.at[idx, "Odds"] = dec_odds

        # Optional rate-limit pause
        time.sleep(1)

    # Save updated workbook
    df.to_excel(OUTPUT_FILE, index=False)
    logging.info(f"Finished! Saved updated data to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
