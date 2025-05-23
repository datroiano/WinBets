# Stadium Season Stats Exporter

A comprehensive tool to fetch and export detailed MLB game statistics for all games played at a specific stadium during a given season.

## Features

- **Comprehensive Game Data**: Fetches detailed statistics for every game played at a stadium in a season
- **Rich Statistics**: Includes batting, pitching, game info, weather, attendance, and more
- **Multi-Sheet Excel Export**: Organizes data into multiple sheets for easy analysis
- **Real-time API Data**: Uses MLB's official StatsAPI for accurate, up-to-date information
- **User-Friendly**: Simple command-line interface with input validation

## Files

- `stadium_season_stats.py` - Main script for exporting stadium season statistics
- `list_stadiums.py` - Helper script to find Stadium IDs
- `README_Stadium_Stats.md` - This documentation file

## Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install requests pandas openpyxl
```

Or if you have a requirements.txt file:

```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Find Stadium ID

First, run the helper script to find the Stadium ID you need:

```bash
python list_stadiums.py
```

This will display a table of all MLB stadiums with their IDs. Example output:
```
Stadium ID   Stadium Name                        City                 State
---------------------------------------------------------------------------
1            Marlins Park                        Miami                FL   
2            Yankee Stadium                      Bronx                NY   
15           Tropicana Field                     St. Petersburg       FL   
```

### Step 2: Run the Main Script

```bash
python stadium_season_stats.py
```

You'll be prompted to enter:
- **Stadium ID**: The numeric ID from step 1 (e.g., `15` for Tropicana Field)
- **Season Year**: A 4-digit year (e.g., `2024`, `2023`)

## Output

The script generates an Excel file with three sheets:

### 1. Games_Data Sheet
Contains detailed statistics for each game:

**Basic Game Info:**
- GameID, GameDate, DayNight, GameType, Season
- AwayTeam, HomeTeam (names and abbreviations)
- GameStatus, Scores, Hits, Errors

**Detailed Batting Stats (Home/Away):**
- AtBats, Runs, Hits, RBI, BaseOnBalls, StrikeOuts
- StolenBases, Doubles, Triples, HomeRuns

**Detailed Pitching Stats (Home/Away):**
- Pitches, Strikes, EarnedRuns, InningsPitched
- PitchingHits, PitchingWalks, PitchingStrikeouts

**Additional Info:**
- Weather (Temperature, Condition, Wind)
- WinningPitcher, LosingPitcher, SavePitcher
- Attendance, GameDuration, FirstPitch

### 2. Summary Sheet
Key statistics for the season:
- Total Games, Home/Away Wins
- Average Attendance, Total/Average Runs
- Total Home Runs, Average Game Duration
- Day vs Night Games breakdown

### 3. Stadium_Info Sheet
Stadium details:
- Stadium ID, Name, Location
- Coordinates, Field Information
- Season analyzed and game count

## Example Usage

```bash
# Find Yankee Stadium ID
python list_stadiums.py

# Export 2024 Yankees home games
python stadium_season_stats.py
Enter Stadium ID: 3
Enter Season Year (e.g., 2024): 2024
```

Output file example: `Yankee Stadium_2024_Games_20241201_143022.xlsx`

## Data Sources

This tool uses MLB's official StatsAPI:
- Base URL: `https://statsapi.mlb.com/api/v1`
- Stadium Info: `/venues/{id}`
- Game Schedule: `/schedule`
- Detailed Stats: `/game/{id}/boxscore`

## Features and Limitations

**Features:**
- ✅ Real-time data from official MLB API
- ✅ Comprehensive statistics (50+ data points per game)
- ✅ Multi-sheet Excel export with summary analytics
- ✅ Weather and attendance data when available
- ✅ Handles all game types (regular season, playoffs, etc.)
- ✅ Rate limiting to be respectful to API
- ✅ Error handling and user-friendly messages

**Limitations:**
- 📊 Detailed stats only available for completed games
- 🌐 Requires internet connection for API access
- ⏱️ Processing time depends on number of games (typically 1-2 minutes for full season)
- 📅 Historical data availability depends on MLB API retention

## Troubleshooting

**Common Issues:**

1. **"Could not find stadium with ID X"**
   - Run `list_stadiums.py` to verify the Stadium ID
   - Make sure you're using the numeric ID, not the name

2. **"No games found for stadium X in YYYY"**
   - Check if the year is correct
   - Some stadiums may not have hosted games in certain years
   - Try a recent year (2023, 2024)

3. **Slow processing**
   - Normal for full seasons (81+ home games)
   - The script fetches detailed stats for each game
   - Progress is shown during processing

4. **Network errors**
   - Check internet connection
   - MLB API may be temporarily unavailable
   - Try again after a few minutes

## Advanced Usage

You can modify the script to:
- Filter by specific date ranges
- Include different game types
- Add custom statistics calculations
- Export to different formats (CSV, JSON)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all dependencies are installed
3. Ensure you have a stable internet connection
4. Try with a different stadium/year combination

---

**Note**: This tool is for educational and analytical purposes. Please respect MLB's API usage guidelines and don't make excessive requests. 