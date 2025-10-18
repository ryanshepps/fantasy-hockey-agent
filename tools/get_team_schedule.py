#!/usr/bin/env python3
"""Tool to get NHL team game schedules for next 2 weeks."""

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

# Add project root to path for imports when running standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.game import Game
from models.schedule import Schedule, TeamSchedule, WeekInfo
from modules.schedule_utils import get_date_range_from_boundaries, get_fantasy_week_boundaries
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


class GetTeamSchedule(BaseTool):
    """Tool for fetching NHL team game schedules."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "get_team_schedule",
        "description": "Get the number of games each NHL team plays starting from TODAY through the end of the next N-1 fantasy weeks (Monday-Sunday). Returns a token-optimized structure with team abbreviations, game counts by week, and game details (date, opponent, home/away). Essential for weekly fantasy matchups as teams with more games = more points. Week 1 = rest of current week (today -> Sunday), Week 2+ = full weeks. Format: {weeks: int, teams: [{abbr: str, total: int, by_week: [int], games: [{date: str, opp: str, h: bool}]}]}",
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": "Number of fantasy weeks to include (default 2). Week 1 covers today through end of current fantasy week (Sunday), Week 2+ covers full fantasy weeks (Monday-Sunday). This ensures recommendations only consider games in the future.",
                    "default": 2,
                }
            },
            "required": [],
        },
    }

    @classmethod
    def run(cls, weeks: int = 2) -> Schedule:
        """
        Get number of games each NHL team plays starting from today through specified fantasy weeks.

        Args:
            weeks: Number of fantasy weeks to include (default 2)
                   Week 1 = rest of current week (today -> Sunday)
                   Week 2+ = full fantasy weeks (Monday -> Sunday)

        Returns:
            Schedule object with validated TeamSchedule models, starting from today's date

        Raises:
            Exception: If NHL API is not available or fetch fails
        """
        if not NHL_API_AVAILABLE:
            raise ImportError(
                "nhl-api-py library is not installed. Install with: pip install nhl-api-py"
            )

        # Initialize NHL API client
        client = NHLClient()

        # Get fantasy week boundaries (Monday-Sunday)
        start_date, end_date, week_boundaries = get_fantasy_week_boundaries(weeks)
        dates = get_date_range_from_boundaries(start_date, end_date)

        # Format week boundaries for response
        week_info_list = []
        for i, (week_start, week_end) in enumerate(week_boundaries):
            week_info_list.append(
                WeekInfo(
                    week_num=i + 1,
                    start=week_start.strftime("%Y-%m-%d"),
                    end=week_end.strftime("%Y-%m-%d"),
                )
            )

        # Track games per team
        team_games = defaultdict(
            lambda: {"total_games": 0, "games_by_week": [0] * weeks, "games": []}
        )

        logger.info(
            f"Fetching NHL schedules from {start_date.strftime('%Y-%m-%d')} (today) to {end_date.strftime('%Y-%m-%d')} (fantasy weeks: Monday-Sunday)"
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
                        Game(date=date_str, opponent=home_abbr, is_home=False)
                    )

                    # Add game for home team
                    team_games[home_abbr]["total_games"] += 1
                    team_games[home_abbr]["games_by_week"][week_num - 1] += 1
                    team_games[home_abbr]["games"].append(
                        Game(date=date_str, opponent=away_abbr, is_home=True)
                    )

            except Exception as e:
                logger.warning(f"Error fetching schedule for {date_str}: {e}")
                continue

        # Convert to TeamSchedule models
        teams = []
        for abbr in sorted(team_games.keys()):
            team_data = team_games[abbr]

            # Sort games by date
            games_sorted = sorted(team_data["games"], key=lambda g: g.date)

            team_schedule = TeamSchedule(
                abbr=abbr,
                total=team_data["total_games"],
                by_week=team_data["games_by_week"],
                games=games_sorted,
            )
            teams.append(team_schedule)

        # Sort by total games (descending)
        teams.sort(key=lambda x: x.total_games, reverse=True)

        logger.info(f"Successfully fetched schedules for {len(teams)} teams")

        # Return validated Schedule model
        return Schedule(
            weeks=weeks,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            week_info=week_info_list,
            teams=teams,
        )


def main():
    """
    Test function to run the tool standalone.
    """
    print("Fetching NHL team schedules for the next 2 fantasy weeks (Monday-Sunday)...\n")

    tool = GetTeamSchedule()
    schedule = tool.execute(weeks=2)

    print(f"✓ Successfully fetched schedules for {len(schedule.teams)} teams\n")
    print(f"Period: {schedule.start_date} to {schedule.end_date}\n")

    print("All NHL Teams (sorted by total games):")
    print("-" * 80)

    for team in schedule.teams:
        # Build week breakdown string
        week_breakdown = ", ".join(
            [f"Week {i + 1}: {games}" for i, games in enumerate(team.games_by_week)]
        )
        team_name = NHL_TEAMS.get(team.abbr, team.abbr)
        print(f"{team_name:<30} {team.total_games} games ({week_breakdown})")


if __name__ == "__main__":
    main()
