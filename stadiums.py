import requests
import pandas as pd
from requests.exceptions import RequestException

def fetch_mlb_stadiums():
    """
    Fetches MLB stadium information via the StatsAPI and outputs an Excel file.
    Columns include:
      - StadiumID
      - StadiumName
      - City
      - State
      - Latitude
      - Longitude
      - FieldInfo (includes orientation description)
    """
    url = "https://statsapi.mlb.com/api/v1/venues"
    params = {"sportId": 1, "hydrate": "location,fieldInfo,timezone"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except RequestException as e:
        print("Error fetching MLB venues from StatsAPI:", e)
        return
    
    venues = response.json().get("venues", [])
    rows = []
    for v in venues:
        loc = v.get("location", {})
        coords = loc.get("defaultCoordinates", {})
        field_info = v.get("fieldInfo", {})
        rows.append({
            "StadiumID": v.get("id"),
            "StadiumName": v.get("name"),
            "City": loc.get("city"),
            "State": loc.get("state"),
            "Latitude": coords.get("latitude"),
            "Longitude": coords.get("longitude"),
            "FieldInfo": field_info.get("description", "")
        })

    df = pd.DataFrame(rows)
    
    # Save to Excel
    output_path = "mlb_weather_stadiums.xlsx"
    df.to_excel(output_path, index=False)
    
    # Display to user
    print("\nMLB Stadiums:")
    print(df)
    print(f"\nSaved stadium list to: {output_path}")

if __name__ == "__main__":
    fetch_mlb_stadiums()
