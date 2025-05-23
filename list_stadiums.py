#!/usr/bin/env python3
"""
Stadium ID Lookup Helper

This script fetches and displays all MLB stadium IDs and names to help you 
find the correct Stadium ID for use with stadium_season_stats.py

Usage:
    python list_stadiums.py
"""

import requests
import pandas as pd
from requests.exceptions import RequestException

def list_mlb_stadiums():
    """
    Fetches and displays all MLB stadium information with their IDs.
    """
    print("MLB Stadiums with Stadium IDs")
    print("=" * 50)
    
    url = "https://statsapi.mlb.com/api/v1/venues"
    params = {"sportId": 1, "hydrate": "location,fieldInfo,timezone"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except RequestException as e:
        print(f"Error fetching MLB venues from StatsAPI: {e}")
        return
    
    venues = response.json().get("venues", [])
    
    if not venues:
        print("No venues found.")
        return
    
    # Sort venues by name for easier lookup
    venues.sort(key=lambda x: x.get('name', ''))
    
    print(f"Found {len(venues)} MLB venues:")
    print()
    print(f"{'Stadium ID':<12} {'Stadium Name':<35} {'City':<20} {'State':<5}")
    print("-" * 75)
    
    for venue in venues:
        stadium_id = venue.get('id', 'N/A')
        name = venue.get('name', 'Unknown')
        location = venue.get('location', {})
        city = location.get('city', 'Unknown')
        state = location.get('state', 'N/A')
        
        # Truncate long names for display
        if len(name) > 34:
            name = name[:31] + "..."
        if len(city) > 19:
            city = city[:16] + "..."
        
        print(f"{stadium_id:<12} {name:<35} {city:<20} {state:<5}")
    
    print("\nTo use with stadium_season_stats.py, copy the Stadium ID (first column)")
    print("Example: python stadium_season_stats.py")
    print("         Enter Stadium ID: 15")

def main():
    """Entry point"""
    try:
        list_mlb_stadiums()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

if __name__ == "__main__":
    main() 