#!/usr/bin/env python3
"""Tool to get NHL team game schedules for next 2 weeks."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, ClassVar

from modules.tool_logger import get_logger
from tools.base_tool import BaseTool

logger = get_logger(__name__)

try:
    from nhlpy import NHLClient

    NHL_API_AVAILABLE = True
except ImportError:
    NHL_API_AVAILABLE = False

# NHL team abbreviation to full name mapping
NHL_TEAMS = {
    "ANA": "Anaheim Ducks",
    "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres",
    "CAR": "Carolina Hurricanes",
    "CBJ": "Columbus Blue Jackets",
    "CGY": "Calgary Flames",
    "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche",
    "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings",
    "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens",
    "NJD": "New Jersey Devils",
    "NSH": "Nashville Predators",
    "NYI": "New York Islanders",
    "NYR": "New York Rangers",
    "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins",
    "SEA": "Seattle Kraken",
    "SJS": "San Jose Sharks",
    "STL": "St. Louis Blues",
    "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs",
    "UTA": "Utah Hockey Club",
    "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights",
    "WPG": "Winnipeg Jets",
    "WSH": "Washington Capitals",
}


def _get_fantasy_week_boundaries(weeks: int = 2) -> tuple:
    """Get start/end dates for fantasy weeks (Monday-Sunday)."""
    today = datetime.now()
    days_since_monday = today.weekday()
    current_week_monday = today - timedelta(days=days_since_monday)

    week_boundaries = []
    for i in range(weeks):
        week_start = current_week_monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        week_boundaries.append((week_start, week_end))

    start_date = week_boundaries[0][0]
    end_date = week_boundaries[-1][1]

    return (start_date, end_date, week_boundaries)


def _get_date_range_from_boundaries(start_date: datetime, end_date: datetime) -> list[str]:
    """Generate list of dates between start and end (YYYY-MM-DD format)."""
    dates = []
    current = start_date

    while current <= end_date:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return dates


class GetTeamSchedule(BaseTool):
    """Tool for fetching NHL team game schedules."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "get_team_schedule",
        "description": "Get the number of games each NHL team plays over the next N fantasy weeks (Monday-Sunday). Returns a token-optimized structure with team abbreviations, game counts by week, and game details (date, opponent, home/away). Essential for weekly fantasy matchups as teams with more games = more points. Aligns to fantasy week boundaries (Monday start). Format: {weeks: int, teams: [{abbr: str, total: int, by_week: [int], games: [{date: str, opp: str, h: bool}]}]}",
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": "Number of fantasy weeks to look ahead (default 2, which covers the current fantasy week and next fantasy week). Fantasy weeks run Monday-Sunday.",
                    "default": 2,
                }
            },
            "required": [],
        },
    }

    @classmethod
    def run(cls, weeks: int = 2) -> dict[str, Any]:
        """Get number of games each NHL team plays over specified fantasy weeks (Monday-Sunday)."""
        if not NHL_API_AVAILABLE:
            return {
                "success": False,
                "error": "nhl-api-py library is not installed. Install with: pip install nhl-api-py",
            }

        try:
            # Initialize NHL API client
            client = NHLClient()

            # Get fantasy week boundaries (Monday-Sunday)
            start_date, end_date, week_boundaries = _get_fantasy_week_boundaries(weeks)
            dates = _get_date_range_from_boundaries(start_date, end_date)

            # Format week boundaries for response
            week_info = []
            for i, (week_start, week_end) in enumerate(week_boundaries):
                week_info.append(
                    {
                        "week_num": i + 1,
                        "start": week_start.strftime("%Y-%m-%d"),
                        "end": week_end.strftime("%Y-%m-%d"),
                    }
                )

            # Track games per team
            team_games = defaultdict(
                lambda: {"total_games": 0, "games_by_week": [0] * weeks, "games": []}
            )

            logger.info(
                f"Fetching NHL schedules from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (fantasy weeks: Monday-Sunday)"
            )

            # Fetch schedule for each date
            for date_str in dates:
                try:
                    # Determine which fantasy week this date belongs to
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    week_num = 0
                    for i, (week_start, week_end) in enumerate(week_boundaries):
                        if week_start <= date_obj <= week_end:
                            week_num = i + 1
                            break

                    # Get daily schedule
                    schedule_data = client.schedule.daily_schedule(date=date_str)

                    if not schedule_data or "games" not in schedule_data:
                        continue

                    # Process each game
                    for game in schedule_data.get("games", []):
                        # Extract team information
                        away_team = game.get("awayTeam", {})
                        home_team = game.get("homeTeam", {})

                        away_abbr = away_team.get("abbrev", "")
                        home_abbr = home_team.get("abbrev", "")

                        # Skip if team info is missing
                        if not away_abbr or not home_abbr:
                            continue

                        # Add game for away team
                        team_games[away_abbr]["total_games"] += 1
                        team_games[away_abbr]["games_by_week"][week_num - 1] += 1
                        team_games[away_abbr]["games"].append(
                            {"date": date_str, "opp": home_abbr, "h": False}
                        )

                        # Add game for home team
                        team_games[home_abbr]["total_games"] += 1
                        team_games[home_abbr]["games_by_week"][week_num - 1] += 1
                        team_games[home_abbr]["games"].append(
                            {"date": date_str, "opp": away_abbr, "h": True}
                        )

                except Exception as e:
                    logger.warning(f"Error fetching schedule for {date_str}: {e}")
                    continue

            # Format results (optimized for token usage)
            teams = []
            for abbr in sorted(team_games.keys()):
                team_data = team_games[abbr]
                teams.append(
                    {
                        "abbr": abbr,
                        "total": team_data["total_games"],
                        "by_week": team_data["games_by_week"],
                        "games": sorted(team_data["games"], key=lambda x: x["date"]),
                    }
                )

            # Sort by total games (descending)
            teams.sort(key=lambda x: x["total"], reverse=True)

            logger.info(f"Successfully fetched schedules for {len(teams)} teams")

            return {
                "weeks": weeks,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "teams": teams,
            }

        except Exception as e:
            logger.error(f"Error fetching team schedules: {e}")
            return {"success": False, "error": f"Failed to fetch team schedules: {e!s}"}


# Export for backwards compatibility
TOOL_DEFINITION = GetTeamSchedule.TOOL_DEFINITION
get_team_schedule = GetTeamSchedule.run


def main():
    """
    Test function to run the tool standalone.
    """
    print("Fetching NHL team schedules for the next 2 fantasy weeks (Monday-Sunday)...\n")

    result = get_team_schedule(weeks=2)

    if "teams" in result:
        print(f"✓ Successfully fetched schedules for {len(result['teams'])} teams\n")

        print("All NHL Teams (sorted by total games):")
        print("-" * 80)

        for team in result["teams"]:
            # Build week breakdown string
            week_breakdown = ", ".join(
                [f"Week {i + 1}: {games}" for i, games in enumerate(team["by_week"])]
            )
            team_name = NHL_TEAMS.get(team["abbr"], team["abbr"])
            print(f"{team_name:<30} {team['total']} games ({week_breakdown})")
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
