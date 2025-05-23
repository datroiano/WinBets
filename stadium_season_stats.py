#!/usr/bin/env python3
"""
Stadium Season Stats Exporter

This script fetches comprehensive game statistics for all games played at a specific 
stadium during a given season and exports the data to an Excel file.

Usage:
    python stadium_season_stats.py

The script will prompt for:
    - Stadium ID (numeric ID from MLB StatsAPI)
    - Season year (e.g., 2023, 2024)

The output Excel file will contain detailed game statistics including:
    - Game details (date, teams, scores)
    - Team statistics (hits, runs, errors, etc.)
    - Pitching statistics
    - Weather information (if available)
    - Game duration and attendance
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
from requests.exceptions import RequestException
import time

class StadiumSeasonStatsExporter:
    def __init__(self):
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Stadium-Season-Stats-Exporter/1.0'
        })

    def get_stadium_info(self, stadium_id):
        """Fetch stadium information by ID"""
        url = f"{self.base_url}/venues/{stadium_id}"
        params = {"hydrate": "location,fieldInfo,timezone"}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            venues = response.json().get("venues", [])
            return venues[0] if venues else None
        except RequestException as e:
            print(f"Error fetching stadium info: {e}")
            return None

    def get_season_schedule(self, stadium_id, season):
        """Fetch all games played at the stadium during the season"""
        print(f"Fetching schedule for stadium {stadium_id} in {season}...")
        
        url = f"{self.base_url}/schedule"
        params = {
            "sportId": 1,
            "season": season,
            "venueIds": stadium_id,
            "hydrate": "team,linescore,decisions,person,probablePitcher,stats,weather,broadcasts",
            "gameType": "R,F,D,L,W"  # Regular season, playoffs, division series, etc.
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            games = []
            for date_entry in data.get("dates", []):
                games.extend(date_entry.get("games", []))
            
            print(f"Found {len(games)} games")
            return games
        except RequestException as e:
            print(f"Error fetching schedule: {e}")
            return []

    def get_detailed_game_stats(self, game_id):
        """Fetch detailed statistics for a specific game"""
        url = f"{self.base_url}/game/{game_id}/boxscore"
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            print(f"Error fetching game {game_id} details: {e}")
            return None

    def extract_game_data(self, game, detailed_stats=None):
        """Extract comprehensive data from a game object"""
        # Basic game info
        game_data = {
            'GameID': game.get('gamePk'),
            'GameDate': game.get('gameDate', ''),
            'DayNight': game.get('dayNight', ''),
            'GameType': game.get('gameType', ''),
            'Season': game.get('season', ''),
            'SeriesDescription': game.get('seriesDescription', ''),
            'SeriesGameNumber': game.get('seriesGameNumber', ''),
            'GameNumber': game.get('gameNumber', 1),
            'DoubleHeader': game.get('doubleHeader', 'N'),
            'ScheduledInnings': game.get('scheduledInnings', 9),
        }
        
        # Teams
        teams = game.get('teams', {})
        away_team = teams.get('away', {}).get('team', {})
        home_team = teams.get('home', {}).get('team', {})
        
        game_data.update({
            'AwayTeam': away_team.get('name', ''),
            'AwayTeamAbbr': away_team.get('abbreviation', ''),
            'HomeTeam': home_team.get('name', ''),
            'HomeTeamAbbr': home_team.get('abbreviation', ''),
        })
        
        # Score and game outcome
        status = game.get('status', {})
        game_data.update({
            'GameStatus': status.get('detailedState', ''),
            'StatusCode': status.get('statusCode', ''),
        })
        
        # Linescore data
        linescore = game.get('linescore', {})
        if linescore:
            game_data.update({
                'CurrentInning': linescore.get('currentInning', ''),
                'InningState': linescore.get('inningState', ''),
                'AwayScore': linescore.get('teams', {}).get('away', {}).get('runs', 0),
                'HomeScore': linescore.get('teams', {}).get('home', {}).get('runs', 0),
                'AwayHits': linescore.get('teams', {}).get('away', {}).get('hits', 0),
                'HomeHits': linescore.get('teams', {}).get('home', {}).get('hits', 0),
                'AwayErrors': linescore.get('teams', {}).get('away', {}).get('errors', 0),
                'HomeErrors': linescore.get('teams', {}).get('home', {}).get('errors', 0),
                'AwayLeftOnBase': linescore.get('teams', {}).get('away', {}).get('leftOnBase', 0),
                'HomeLeftOnBase': linescore.get('teams', {}).get('home', {}).get('leftOnBase', 0),
            })
        
        # Weather information
        weather = game.get('weather', {})
        if weather:
            game_data.update({
                'Temperature': weather.get('temp', ''),
                'Condition': weather.get('condition', ''),
                'Wind': weather.get('wind', ''),
                'WindSpeed': weather.get('windSpeed', ''),
                'WindDirection': weather.get('windDirection', ''),
            })
        
        # Decisions (winning/losing/save pitchers)
        decisions = game.get('decisions', {})
        if decisions:
            winner = decisions.get('winner', {})
            loser = decisions.get('loser', {})
            save = decisions.get('save', {})
            
            game_data.update({
                'WinningPitcher': winner.get('fullName', ''),
                'WinningPitcherID': winner.get('id', ''),
                'LosingPitcher': loser.get('fullName', ''),
                'LosingPitcherID': loser.get('id', ''),
                'SavePitcher': save.get('fullName', ''),
                'SavePitcherID': save.get('id', ''),
            })
        
        # Add detailed stats if available
        if detailed_stats:
            boxscore = detailed_stats.get('teams', {})
            
            # Away team detailed stats
            away_stats = boxscore.get('away', {}).get('teamStats', {})
            away_batting = away_stats.get('batting', {})
            away_pitching = away_stats.get('pitching', {})
            
            game_data.update({
                'Away_AtBats': away_batting.get('atBats', 0),
                'Away_Runs': away_batting.get('runs', 0),
                'Away_Hits': away_batting.get('hits', 0),
                'Away_RBI': away_batting.get('rbi', 0),
                'Away_BaseOnBalls': away_batting.get('baseOnBalls', 0),
                'Away_StrikeOuts': away_batting.get('strikeOuts', 0),
                'Away_StolenBases': away_batting.get('stolenBases', 0),
                'Away_Doubles': away_batting.get('doubles', 0),
                'Away_Triples': away_batting.get('triples', 0),
                'Away_HomeRuns': away_batting.get('homeRuns', 0),
                'Away_Pitches': away_pitching.get('numberOfPitches', 0),
                'Away_Strikes': away_pitching.get('strikes', 0),
                'Away_EarnedRuns': away_pitching.get('earnedRuns', 0),
                'Away_InningsPitched': away_pitching.get('inningsPitched', ''),
                'Away_PitchingHits': away_pitching.get('hits', 0),
                'Away_PitchingWalks': away_pitching.get('baseOnBalls', 0),
                'Away_PitchingStrikeouts': away_pitching.get('strikeOuts', 0),
            })
            
            # Home team detailed stats
            home_stats = boxscore.get('home', {}).get('teamStats', {})
            home_batting = home_stats.get('batting', {})
            home_pitching = home_stats.get('pitching', {})
            
            game_data.update({
                'Home_AtBats': home_batting.get('atBats', 0),
                'Home_Runs': home_batting.get('runs', 0),
                'Home_Hits': home_batting.get('hits', 0),
                'Home_RBI': home_batting.get('rbi', 0),
                'Home_BaseOnBalls': home_batting.get('baseOnBalls', 0),
                'Home_StrikeOuts': home_batting.get('strikeOuts', 0),
                'Home_StolenBases': home_batting.get('stolenBases', 0),
                'Home_Doubles': home_batting.get('doubles', 0),
                'Home_Triples': home_batting.get('triples', 0),
                'Home_HomeRuns': home_batting.get('homeRuns', 0),
                'Home_Pitches': home_pitching.get('numberOfPitches', 0),
                'Home_Strikes': home_pitching.get('strikes', 0),
                'Home_EarnedRuns': home_pitching.get('earnedRuns', 0),
                'Home_InningsPitched': home_pitching.get('inningsPitched', ''),
                'Home_PitchingHits': home_pitching.get('hits', 0),
                'Home_PitchingWalks': home_pitching.get('baseOnBalls', 0),
                'Home_PitchingStrikeouts': home_pitching.get('strikeOuts', 0),
            })
            
            # Game info from detailed stats
            game_info = detailed_stats.get('gameInfo', {})
            if game_info:
                game_data.update({
                    'Attendance': game_info.get('attendance', ''),
                    'GameDuration': game_info.get('gameDurationMinutes', ''),
                    'FirstPitch': game_info.get('firstPitch', ''),
                })
        
        return game_data

    def export_to_excel(self, games_data, stadium_info, season, stadium_id):
        """Export the games data to Excel with multiple sheets"""
        
        # Create DataFrame
        df = pd.DataFrame(games_data)
        
        # Convert GameDate to datetime for better sorting and handle timezone issues
        if 'GameDate' in df.columns:
            df['GameDate'] = pd.to_datetime(df['GameDate'])
            # Remove timezone information for Excel compatibility
            if df['GameDate'].dt.tz is not None:
                df['GameDate'] = df['GameDate'].dt.tz_localize(None)
            df = df.sort_values('GameDate')
        
        # Handle other potential datetime columns that might have timezone info
        datetime_columns = ['FirstPitch']
        for col in datetime_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)
        
        # Generate filename
        stadium_name = stadium_info.get('name', f'Stadium_{stadium_id}') if stadium_info else f'Stadium_{stadium_id}'
        safe_stadium_name = "".join(c for c in stadium_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_stadium_name}_{season}_Games_{timestamp}.xlsx"
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Main games data
            df.to_excel(writer, sheet_name='Games_Data', index=False)
            
            # Summary statistics
            if not df.empty:
                summary_data = {
                    'Metric': [
                        'Total Games',
                        'Home Team Wins',
                        'Away Team Wins',
                        'Average Attendance',
                        'Total Runs Scored',
                        'Average Runs Per Game',
                        'Total Home Runs',
                        'Average Game Duration (minutes)',
                        'Day Games',
                        'Night Games'
                    ],
                    'Value': [
                        len(df),
                        len(df[df['HomeScore'] > df['AwayScore']]) if 'HomeScore' in df.columns else 'N/A',
                        len(df[df['AwayScore'] > df['HomeScore']]) if 'AwayScore' in df.columns else 'N/A',
                        df['Attendance'].astype(str).str.replace(',', '').astype(float).mean() if 'Attendance' in df.columns and not df['Attendance'].isna().all() else 'N/A',
                        (df['HomeScore'].sum() + df['AwayScore'].sum()) if 'HomeScore' in df.columns else 'N/A',
                        (df['HomeScore'].sum() + df['AwayScore'].sum()) / len(df) if 'HomeScore' in df.columns else 'N/A',
                        (df['Home_HomeRuns'].sum() + df['Away_HomeRuns'].sum()) if 'Home_HomeRuns' in df.columns else 'N/A',
                        df['GameDuration'].astype(float).mean() if 'GameDuration' in df.columns and not df['GameDuration'].isna().all() else 'N/A',
                        len(df[df['DayNight'] == 'day']) if 'DayNight' in df.columns else 'N/A',
                        len(df[df['DayNight'] == 'night']) if 'DayNight' in df.columns else 'N/A'
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Stadium info sheet
            if stadium_info:
                loc = stadium_info.get('location', {})
                coords = loc.get('defaultCoordinates', {})
                field_info = stadium_info.get('fieldInfo', {})
                
                stadium_data = {
                    'Attribute': [
                        'Stadium ID',
                        'Stadium Name',
                        'City',
                        'State',
                        'Latitude',
                        'Longitude',
                        'Field Info',
                        'Season',
                        'Games Analyzed'
                    ],
                    'Value': [
                        stadium_info.get('id', ''),
                        stadium_info.get('name', ''),
                        loc.get('city', ''),
                        loc.get('state', ''),
                        coords.get('latitude', ''),
                        coords.get('longitude', ''),
                        field_info.get('description', ''),
                        season,
                        len(df)
                    ]
                }
                stadium_df = pd.DataFrame(stadium_data)
                stadium_df.to_excel(writer, sheet_name='Stadium_Info', index=False)
        
        print(f"\nData exported to: {filename}")
        print(f"Total games analyzed: {len(df)}")
        
        return filename

    def run(self):
        """Main execution method"""
        print("Stadium Season Stats Exporter")
        print("=" * 50)
        
        # Get user input
        try:
            stadium_id = input("Enter Stadium ID: ").strip()
            if not stadium_id.isdigit():
                print("Error: Stadium ID must be a number")
                return
            stadium_id = int(stadium_id)
            
            season = input("Enter Season Year (e.g., 2024): ").strip()
            if not season.isdigit() or len(season) != 4:
                print("Error: Season must be a 4-digit year")
                return
            season = int(season)
            
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            return
        except Exception as e:
            print(f"Error getting input: {e}")
            return
        
        # Fetch stadium info
        stadium_info = self.get_stadium_info(stadium_id)
        if not stadium_info:
            print(f"Error: Could not find stadium with ID {stadium_id}")
            return
        
        print(f"\nFound stadium: {stadium_info.get('name', 'Unknown')}")
        print(f"Location: {stadium_info.get('location', {}).get('city', 'Unknown')}, "
              f"{stadium_info.get('location', {}).get('state', 'Unknown')}")
        
        # Fetch games
        games = self.get_season_schedule(stadium_id, season)
        if not games:
            print(f"No games found for stadium {stadium_id} in {season}")
            return
        
        # Process games with detailed stats
        print(f"\nProcessing {len(games)} games with detailed statistics...")
        games_data = []
        
        for i, game in enumerate(games, 1):
            print(f"Processing game {i}/{len(games)}: {game.get('gamePk', 'Unknown')}", end="")
            
            # Get detailed stats for completed games
            detailed_stats = None
            if game.get('status', {}).get('statusCode') == 'F':  # Final games only
                detailed_stats = self.get_detailed_game_stats(game.get('gamePk'))
                time.sleep(0.1)  # Be nice to the API
            
            game_data = self.extract_game_data(game, detailed_stats)
            games_data.append(game_data)
            print(" ✓")
        
        # Export to Excel
        print("\nExporting data to Excel...")
        filename = self.export_to_excel(games_data, stadium_info, season, stadium_id)
        
        print(f"\nSuccess! Created {filename}")
        print(f"Stadium: {stadium_info.get('name', 'Unknown')}")
        print(f"Season: {season}")
        print(f"Games: {len(games_data)}")

def main():
    """Entry point"""
    try:
        exporter = StadiumSeasonStatsExporter()
        exporter.run()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 