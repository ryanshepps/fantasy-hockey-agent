#!/usr/bin/env python3
"""
Test script to get your current fantasy hockey roster.
Can be run standalone to verify Yahoo API connection and roster fetching.
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery

from tools.base_tool import BaseTool

# Load environment variables
load_dotenv()

# Yahoo API credentials
YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID")
YAHOO_CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET")
LEAGUE_ID = os.getenv("LEAGUE_ID")
TEAM_ID = os.getenv("TEAM_ID")  # Your team ID from .env
GAME_KEY = os.getenv("GAME_KEY", "nhl")


def initialize_yahoo_query():
    """Initialize the Yahoo Fantasy Sports Query object."""
    yahoo_query = YahooFantasySportsQuery(
        league_id=LEAGUE_ID,
        game_code="nhl",
        game_id=None,
        yahoo_consumer_key=YAHOO_CLIENT_ID,
        yahoo_consumer_secret=YAHOO_CLIENT_SECRET,
        env_file_location=Path("."),
        save_token_data_to_env_file=True,
    )
    return yahoo_query


def _extract_player_name(player) -> str:
    """
    Extract player name from Yahoo API player object.

    Args:
        player: Yahoo API player object

    Returns:
        Player name string
    """
    if hasattr(player, "name"):
        if isinstance(player.name, str):
            return player.name
        elif hasattr(player.name, "full"):
            return player.name.full
        else:
            return str(player.name)
    return "Unknown"


def _extract_player_position_info(player) -> dict:
    """
    Extract position information from Yahoo API player object.

    Args:
        player: Yahoo API player object

    Returns:
        Dictionary with position, eligible_positions, and selected_position
    """
    position = None
    eligible_positions = []
    selected_position = None

    # Get primary position
    if hasattr(player, "primary_position"):
        position = player.primary_position
    elif hasattr(player, "display_position"):
        position = player.display_position
    elif hasattr(player, "position_type"):
        position = player.position_type

    # Get eligible positions
    if hasattr(player, "eligible_positions") and player.eligible_positions:
        pos = player.eligible_positions
        eligible_positions = pos if isinstance(pos, list) else [pos]
        if not position and eligible_positions:
            position = eligible_positions[0]

    # Get selected position (lineup slot)
    if hasattr(player, "selected_position"):
        selected_pos = player.selected_position
        if selected_pos:
            if hasattr(selected_pos, "position"):
                selected_position = selected_pos.position
            else:
                selected_position = str(selected_pos)

    return {
        "position": position,
        "eligible_positions": eligible_positions,
        "selected_position": selected_position,
    }


def _extract_player_fantasy_points(player) -> float:
    """
    Extract fantasy points from Yahoo API player object.

    Args:
        player: Yahoo API player object

    Returns:
        Fantasy points as float
    """
    fantasy_points = 0.0

    if hasattr(player, "player_points") and player.player_points:
        if hasattr(player.player_points, "total"):
            fantasy_points = (
                float(player.player_points.total) if player.player_points.total else 0.0
            )
        elif isinstance(player.player_points, (int, float)):
            fantasy_points = float(player.player_points)
    elif hasattr(player, "player_stats") and player.player_stats:
        if hasattr(player.player_stats, "points"):
            fantasy_points = (
                float(player.player_stats.points) if player.player_stats.points else 0.0
            )
        elif hasattr(player.player_stats, "stats") and player.player_stats.stats:
            stats = player.player_stats.stats
            if isinstance(stats, dict) and "points" in stats:
                fantasy_points = float(stats["points"])

    return fantasy_points


def _convert_roster_to_flat_structure(roster: list) -> list[dict]:
    """
    Convert Yahoo API roster objects to flat, agent-friendly dictionaries.

    Args:
        roster: List of Yahoo API player objects

    Returns:
        List of flat player dictionaries
    """
    players = []

    for player in roster:
        # Extract player information
        player_name = _extract_player_name(player)
        position_info = _extract_player_position_info(player)
        fantasy_points = _extract_player_fantasy_points(player)

        # Build flat player object
        player_data = {
            "player_id": player.player_id if hasattr(player, "player_id") else None,
            "name": player_name,
            "position": position_info["position"],
            "eligible_positions": position_info["eligible_positions"],
            "selected_position": position_info["selected_position"],
            "nhl_team": player.editorial_team_abbr
            if hasattr(player, "editorial_team_abbr")
            else None,
            "fantasy_points": fantasy_points,
            "status": player.status if hasattr(player, "status") else None,
            "is_injured": player.status not in [None, "", "Healthy"]
            if hasattr(player, "status")
            else False,
        }

        players.append(player_data)

    return players


def _calculate_roster_counts(players: list[dict]) -> dict:
    """
    Calculate roster statistics by position and status.

    Args:
        players: List of player dictionaries

    Returns:
        Dictionary with roster counts
    """
    return {
        "total": len(players),
        "forwards": len([p for p in players if p["position"] in ["C", "LW", "RW", "F"]]),
        "defense": len([p for p in players if p["position"] == "D"]),
        "goalies": len([p for p in players if p["position"] == "G"]),
        "active": len(
            [p for p in players if p["selected_position"] not in ["BN", "IR", "IR+", None]]
        ),
        "bench": len([p for p in players if p["selected_position"] == "BN"]),
        "injured_reserve": len([p for p in players if p["selected_position"] in ["IR", "IR+"]]),
    }


def _get_league_context_info(yahoo_query) -> dict:
    """
    Get league context information (name, week, season).

    Args:
        yahoo_query: Yahoo Fantasy Sports Query object

    Returns:
        Dictionary with league information
    """
    league_info = {}
    try:
        league = yahoo_query.get_league_info()
        if league:
            league_name = getattr(league, "name", None)
            # Handle bytes to string conversion
            if isinstance(league_name, bytes):
                league_name = league_name.decode("utf-8")

            league_info = {
                "league_name": league_name,
                "current_week": getattr(league, "current_week", None),
                "season": getattr(league, "season", None),
            }
    except Exception:
        pass

    return league_info


class GetCurrentRoster(BaseTool):
    """Tool for fetching current fantasy hockey roster."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION = {
        "name": "get_current_roster",
        "description": "Get the current roster for a fantasy hockey team. Returns players categorized by position with their stats including fantasy points, status (injured/healthy), and position in lineup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "integer",
                    "description": "Team ID (if not provided, uses the first team which is typically the user's team)",
                    "default": None,
                }
            },
            "required": [],
        },
    }

    @classmethod
    def run(cls, team_id: int = None) -> dict[str, Any]:
        """
        Get the current roster for a team.

        Args:
            team_id: Team ID (if None, uses TEAM_ID from .env file)

        Returns:
            Dictionary with roster players and their stats
        """
        from datetime import datetime

        try:
            yahoo_query = initialize_yahoo_query()

            # Determine team_id to use
            if team_id is None:
                team_id = int(TEAM_ID) if TEAM_ID else None
                if not team_id:
                    # Fallback: get first team in league
                    teams = yahoo_query.get_league_teams()
                    if teams and len(teams) > 0:
                        team_id = teams[0].team_id

            # Fetch roster data with fallback methods
            roster = None
            try:
                roster = yahoo_query.get_team_roster_player_stats(team_id)
            except Exception:
                try:
                    roster = yahoo_query.get_team_roster_player_info_by_week(team_id)
                except Exception:
                    roster = yahoo_query.get_team_roster_by_week(team_id)

            # Get league context information
            league_info = _get_league_context_info(yahoo_query)

            # Convert roster to flat structure
            players = _convert_roster_to_flat_structure(roster)

            # Sort by fantasy points (highest first)
            players.sort(key=lambda p: p["fantasy_points"], reverse=True)

            # Calculate roster counts
            roster_counts = _calculate_roster_counts(players)

            return {
                "success": True,
                "data": {
                    "team_id": team_id,
                    "league_context": league_info,
                    "retrieved_at": datetime.now().isoformat(),
                    "players": players,
                    "roster_counts": roster_counts,
                },
            }

        except Exception as e:
            import traceback

            return {"success": False, "error": str(e), "error_details": traceback.format_exc()}


# Export for backwards compatibility
TOOL_DEFINITION = GetCurrentRoster.TOOL_DEFINITION
get_current_roster = GetCurrentRoster.run


def display_roster(roster_data: dict[str, Any]):
    """Display roster in a readable format."""
    if not roster_data["success"]:
        print(f"\nError fetching roster: {roster_data['error']}")
        if "error_details" in roster_data:
            print(f"\nDetails:\n{roster_data['error_details']}")
        return

    data = roster_data["data"]
    players = data["players"]
    counts = data["roster_counts"]

    print(f"\n{'=' * 80}")
    print(f"YOUR ROSTER (Team ID: {data['team_id']})")
    if data["league_context"].get("league_name"):
        print(f"League: {data['league_context']['league_name']}")
        if data["league_context"].get("current_week"):
            print(f"Week: {data['league_context']['current_week']}")
    print(f"{'=' * 80}\n")

    # Categorize for display
    forwards = [p for p in players if p["position"] in ["C", "LW", "RW", "F"]]
    defense = [p for p in players if p["position"] == "D"]
    goalies = [p for p in players if p["position"] == "G"]

    # Display forwards
    print(f"FORWARDS ({counts['forwards']} players)")
    print(f"{'-' * 80}")
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Slot':<8} {'Pts':<10} {'Status':<12}")
    print(f"{'-' * 80}")
    for player in forwards:
        name = player["name"]
        position = player["position"] or "N/A"
        team = player["nhl_team"] or "N/A"
        slot = player["selected_position"] or "N/A"
        pts = player["fantasy_points"]
        status = player["status"] or "Healthy"
        print(f"{name:<30} {position:<5} {team:<5} {slot:<8} {pts:<10.2f} {status:<12}")

    # Display defense
    print(f"\nDEFENSE ({counts['defense']} players)")
    print(f"{'-' * 80}")
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Slot':<8} {'Pts':<10} {'Status':<12}")
    print(f"{'-' * 80}")
    for player in defense:
        name = player["name"]
        position = player["position"] or "N/A"
        team = player["nhl_team"] or "N/A"
        slot = player["selected_position"] or "N/A"
        pts = player["fantasy_points"]
        status = player["status"] or "Healthy"
        print(f"{name:<30} {position:<5} {team:<5} {slot:<8} {pts:<10.2f} {status:<12}")

    # Display goalies
    print(f"\nGOALIES ({counts['goalies']} players)")
    print(f"{'-' * 80}")
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Slot':<8} {'Pts':<10} {'Status':<12}")
    print(f"{'-' * 80}")
    for player in goalies:
        name = player["name"]
        position = player["position"] or "N/A"
        team = player["nhl_team"] or "N/A"
        slot = player["selected_position"] or "N/A"
        pts = player["fantasy_points"]
        status = player["status"] or "Healthy"
        print(f"{name:<30} {position:<5} {team:<5} {slot:<8} {pts:<10.2f} {status:<12}")

    print("\nRoster Summary:")
    print(
        f"  Total: {counts['total']} | Active: {counts['active']} | Bench: {counts['bench']} | IR: {counts['injured_reserve']}"
    )


def main():
    """Test the get_current_roster function."""
    # Validate credentials
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing required credentials in .env file")
        print("Please ensure YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, and LEAGUE_ID are set")
        return

    print("Testing get_current_roster tool...")
    print("Initializing Yahoo Fantasy Sports Query...")

    # Get roster
    roster_data = get_current_roster()

    # Display results
    display_roster(roster_data)


if __name__ == "__main__":
    main()
