#!/usr/bin/env python3
"""Tool to get available free agents from specific NHL teams."""

import sys
from pathlib import Path
from typing import Any, ClassVar

# Add project root to path for imports when running standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.player import Player, PlayerPosition, PlayerStatus
from modules.yahoo_utils import (
    LEAGUE_ID,
    YAHOO_CLIENT_ID,
    YAHOO_CLIENT_SECRET,
    extract_player_name,
    initialize_yahoo_query,
)
from tools.base_tool import BaseTool


def _nhl_to_yahoo_abbr(abbr: str) -> str:
    """
    Convert NHL API team abbreviation to Yahoo format.

    Yahoo uses short forms (TB, NJ, SJ, LA) while NHL API uses
    full forms (TBL, NJD, SJS, LAK). This function converts NHL API
    format to Yahoo format for filtering.

    Args:
        abbr: Team abbreviation in NHL API format (e.g., 'TBL')

    Returns:
        Team abbreviation in Yahoo format (e.g., 'TB')
    """
    # Reverse mapping from NHL API forms to Yahoo forms
    reverse_map = {
        "TBL": "TB",  # Tampa Bay Lightning
        "NJD": "NJ",  # New Jersey Devils
        "SJS": "SJ",  # San Jose Sharks
        "LAK": "LA",  # Los Angeles Kings
    }
    return reverse_map.get(abbr, abbr)


def _parse_position(position_str: str | None) -> PlayerPosition | None:
    """Parse position string to PlayerPosition enum."""
    if not position_str:
        return None
    try:
        return PlayerPosition(position_str)
    except ValueError:
        return None


def _parse_status(status_str: str | None) -> PlayerStatus:
    """Parse status string to PlayerStatus enum."""
    if not status_str or status_str == "" or status_str == "Healthy":
        return PlayerStatus.HEALTHY
    try:
        return PlayerStatus(status_str)
    except ValueError:
        return PlayerStatus.HEALTHY


class GetPlayersFromTeams(BaseTool):
    """Tool for fetching available free agents from specific NHL teams."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "get_players_from_teams",
        "description": "Fetch top available free agents from specific NHL teams. Returns top N players per team sorted by fantasy points. Use this after get_team_schedule to target players on teams with favorable schedules. Example: get_players_from_teams(teams=['TOR', 'EDM', 'BOS'], limit_per_team=5) returns top 5 FAs from each team.",
        "input_schema": {
            "type": "object",
            "properties": {
                "teams": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of NHL team abbreviations (e.g., ['TOR', 'EDM', 'BOS']). Use 3-letter NHL API format (TBL not TB, NJD not NJ, SJS not SJ, LAK not LA).",
                },
                "limit_per_team": {
                    "type": "integer",
                    "description": "Number of top players to fetch per team sorted by fantasy points (default 5)",
                    "default": 5,
                },
            },
            "required": ["teams"],
        },
    }

    @classmethod
    def run(cls, teams: list[str], limit_per_team: int = 5) -> list[Player]:
        """
        Get available free agents from specific NHL teams.

        Args:
            teams: List of NHL team abbreviations (e.g., ['TOR', 'EDM', 'BOS'])
            limit_per_team: Number of top players per team (default 5)

        Returns:
            List of Player models sorted by fantasy points (descending)

        Raises:
            Exception: If API fetch fails
        """
        yahoo_query = initialize_yahoo_query()
        league_key = yahoo_query.get_league_key()

        # Convert NHL API team abbreviations to Yahoo format for filtering
        # Create a mapping to track which teams we're looking for
        yahoo_teams = set()
        team_mapping = {}  # Maps Yahoo format -> NHL API format for results
        for team in teams:
            yahoo_abbr = _nhl_to_yahoo_abbr(team)
            yahoo_teams.add(yahoo_abbr)
            team_mapping[yahoo_abbr] = team

        # Fetch all available players
        # Yahoo API doesn't support filtering by team in the request,
        # so we fetch in batches and filter client-side
        all_players = []
        batch_size = 25
        current_start = 0
        max_total_fetch = 200  # Reasonable upper bound to avoid infinite loops

        # Fetch players in batches
        while len(all_players) < max_total_fetch:
            url = (
                f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;"
                f"status=FA;sort=AR;start={current_start};count={batch_size}/stats"
            )

            try:
                players_batch = yahoo_query.query(url, ["league", "players"])

                if isinstance(players_batch, list):
                    all_players.extend(players_batch)
                    if len(players_batch) < batch_size:
                        break
                else:
                    all_players.append(players_batch)
                    break

                current_start += batch_size
            except Exception:
                break

        # Convert to Player models and filter by team
        players_by_team: dict[str, list[Player]] = {team: [] for team in teams}

        for player in all_players:
            # Get team abbreviation (in Yahoo format)
            yahoo_team_abbr = (
                player.editorial_team_abbr if hasattr(player, "editorial_team_abbr") else None
            )
            if not yahoo_team_abbr or yahoo_team_abbr not in yahoo_teams:
                continue

            # Get the NHL API format team abbreviation for organizing results
            nhl_team_abbr = team_mapping[yahoo_team_abbr]

            player_name = extract_player_name(player)

            # Parse position
            position_value = None
            if hasattr(player, "primary_position"):
                position_value = player.primary_position
            elif hasattr(player, "display_position"):
                position_value = player.display_position

            # Parse eligible positions
            eligible_positions_raw = []
            if hasattr(player, "eligible_positions") and player.eligible_positions:
                pos = player.eligible_positions
                eligible_positions_raw = pos if isinstance(pos, list) else [pos]
                if not position_value and eligible_positions_raw:
                    position_value = eligible_positions_raw[0]

            # Convert to enums
            position_enum = _parse_position(position_value)
            eligible_positions = [
                _parse_position(p) for p in eligible_positions_raw if _parse_position(p)
            ]

            # Parse fantasy points
            fantasy_points = 0.0
            if (
                hasattr(player, "player_points")
                and player.player_points
                and hasattr(player.player_points, "total")
                and player.player_points.total
            ):
                fantasy_points = float(player.player_points.total)

            # Parse status
            status_str = player.status if hasattr(player, "status") else None
            status = _parse_status(status_str)
            is_injured = status != PlayerStatus.HEALTHY

            # Create Player model
            player_model = Player(
                player_id=str(player.player_id) if hasattr(player, "player_id") else None,
                name=player_name,
                position=position_enum,
                eligible_positions=eligible_positions,
                selected_position=None,  # Free agents don't have a roster slot
                nhl_team=yahoo_team_abbr,  # Store Yahoo format (what API returns)
                fantasy_points=fantasy_points,
                status=status,
                is_injured=is_injured,
            )

            players_by_team[nhl_team_abbr].append(player_model)

        # Get top N per team and combine
        result_players = []
        for team in teams:
            team_players = players_by_team[team]
            # Sort by fantasy points descending
            team_players.sort(key=lambda p: p.fantasy_points, reverse=True)
            # Take top N
            result_players.extend(team_players[:limit_per_team])

        # Sort final list by fantasy points
        result_players.sort(key=lambda p: p.fantasy_points, reverse=True)

        return result_players


def display_players_by_team(players: list[Player]):
    """Display players grouped by team in a readable format."""
    from collections import defaultdict

    players_by_team = defaultdict(list)
    for p in players:
        if p.nhl_team:
            players_by_team[p.nhl_team].append(p)

    print(f"\n{'=' * 80}")
    print("AVAILABLE FREE AGENTS BY TEAM")
    print("=" * 80)

    for team in sorted(players_by_team.keys()):
        team_players = players_by_team[team]
        print(f"\n{team} ({len(team_players)} players)")
        print("-" * 80)
        print(f"{'Name':<30} {'Pos':<5} {'Fantasy Pts':<12} {'Status':<12}")
        print("-" * 80)
        for p in team_players:
            pos_str = p.position.value if p.position else "N/A"
            status_str = p.status.value if p.status else "Healthy"
            print(f"{p.name:<30} {pos_str:<5} {p.fantasy_points:<12.2f} {status_str:<12}")

    print(f"\nTotal players: {len(players)}")


def main():
    """Test the get_players_from_teams function."""
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing credentials in .env")
        return

    print("Testing get_players_from_teams...")

    # Test with a few high-game teams (example)
    test_teams = ["TOR", "EDM", "COL"]
    tool = GetPlayersFromTeams()
    result = tool.execute(teams=test_teams, limit_per_team=5)
    display_players_by_team(result)


if __name__ == "__main__":
    main()
