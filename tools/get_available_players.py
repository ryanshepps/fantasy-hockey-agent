#!/usr/bin/env python3
"""
Test script to get available free agents.
Can be run standalone to verify Yahoo API connection and free agent fetching.
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


class GetAvailablePlayers(BaseTool):
    """Tool for fetching available free agent players from Yahoo Fantasy Hockey."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION = {
        "name": "get_available_players",
        "description": "Get available free agent players from Yahoo Fantasy Hockey league. Returns players categorized by position (forwards, defense, goalies) with their stats including fantasy points. Players are sorted by fantasy points in descending order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of players to fetch (default 100)",
                    "default": 100,
                },
                "position": {
                    "type": "string",
                    "description": "Filter by position: 'C' (center), 'LW' (left wing), 'RW' (right wing), 'D' (defense), 'G' (goalie), or null for all positions",
                    "enum": ["C", "LW", "RW", "D", "G", None],
                },
            },
            "required": [],
        },
    }

    @classmethod
    def run(cls, count: int = 100, position: str = None) -> dict[str, Any]:
        """
            Get available free agent players from Yahoo Fantasy Hockey.

        Args:
            count: Number of players to fetch (default 100)
            position: Filter by position (e.g., 'C', 'LW', 'RW', 'D', 'G') or None for all

            Returns:
                Dictionary with available players and their stats
        """
        from datetime import datetime

        try:
            yahoo_query = initialize_yahoo_query()
            league_key = yahoo_query.get_league_key()

            # Get league info for context
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

            all_players = []
            batch_size = 25
            current_start = 0

            # Fetch players in batches (silent mode)
            while len(all_players) < count:
                remaining = count - len(all_players)
                batch_count = min(batch_size, remaining)

                url = (
                    f"https://fantasysports.yahooapis.com/fantasy/v2/league/{league_key}/players;"
                    f"status=FA;sort=AR;start={current_start};count={batch_count}/stats"
                )

                try:
                    players_batch = yahoo_query.query(url, ["league", "players"])

                    if isinstance(players_batch, list):
                        all_players.extend(players_batch)
                        if len(players_batch) < batch_count:
                            break  # Reached end of available players
                    else:
                        all_players.append(players_batch)
                        break

                    current_start += batch_count
                except Exception:
                    break

            # Convert players to flat, agent-friendly structure
            players = []
            for player in all_players:
                # Get player name - handle both string and object formats
                if hasattr(player, "name"):
                    if isinstance(player.name, str):
                        player_name = player.name
                    elif hasattr(player.name, "full"):
                        player_name = player.name.full
                    else:
                        player_name = str(player.name)
                else:
                    player_name = "Unknown"

                # Get position
                position_value = None
                eligible_positions = []

                if hasattr(player, "primary_position"):
                    position_value = player.primary_position
                elif hasattr(player, "display_position"):
                    position_value = player.display_position

                if hasattr(player, "eligible_positions") and player.eligible_positions:
                    pos = player.eligible_positions
                    eligible_positions = pos if isinstance(pos, list) else [pos]
                    if not position_value and eligible_positions:
                        position_value = eligible_positions[0]

                # Get fantasy points
                fantasy_points = 0.0
                if hasattr(player, "player_points") and player.player_points:
                    if hasattr(player.player_points, "total") and player.player_points.total:
                        fantasy_points = float(player.player_points.total)

                # Build flat player object
                player_data = {
                    "player_id": player.player_id if hasattr(player, "player_id") else None,
                    "name": player_name,
                    "position": position_value,
                    "eligible_positions": eligible_positions,
                    "nhl_team": player.editorial_team_abbr
                    if hasattr(player, "editorial_team_abbr")
                    else None,
                    "fantasy_points": fantasy_points,
                    "status": player.status if hasattr(player, "status") else None,
                    "is_injured": player.status not in [None, "", "Healthy"]
                    if hasattr(player, "status")
                    else False,
                    "ownership_percentage": None,  # Yahoo doesn't always provide this in basic queries
                }

                # Apply position filter if specified
                if position is None or position_value == position or position in eligible_positions:
                    players.append(player_data)

            # Sort by fantasy points (highest first)
            players.sort(key=lambda p: p["fantasy_points"], reverse=True)

            return {
                "success": True,
                "data": {
                    "league_context": league_info,
                    "retrieved_at": datetime.now().isoformat(),
                    "filter": {"position": position, "max_count": count},
                    "players": players,
                    "player_counts": {
                        "total": len(players),
                        "forwards": len(
                            [p for p in players if p["position"] in ["C", "LW", "RW", "F"]]
                        ),
                        "defense": len([p for p in players if p["position"] == "D"]),
                        "goalies": len([p for p in players if p["position"] == "G"]),
                    },
                },
            }

        except Exception as e:
            import traceback

            return {"success": False, "error": str(e), "error_details": traceback.format_exc()}


# Export for backwards compatibility
TOOL_DEFINITION = GetAvailablePlayers.TOOL_DEFINITION
get_available_players = GetAvailablePlayers.run


def display_available_players(data: dict[str, Any], limit: int = 10):
    """Display available players in a readable format."""
    if not data["success"]:
        print(f"\nError fetching players: {data['error']}")
        if "error_details" in data:
            print(f"\nDetails:\n{data['error_details']}")
        return

    result_data = data["data"]
    players = result_data["players"]
    counts = result_data["player_counts"]

    print(f"\n{'=' * 80}")
    print(f"AVAILABLE FREE AGENTS (Top {limit} per position)")
    if result_data["league_context"].get("league_name"):
        print(f"League: {result_data['league_context']['league_name']}")
    print(f"{'=' * 80}\n")

    # Categorize for display
    forwards = [p for p in players if p["position"] in ["C", "LW", "RW", "F"]]
    defense = [p for p in players if p["position"] == "D"]
    goalies = [p for p in players if p["position"] == "G"]

    # Display forwards
    print(f"FORWARDS ({counts['forwards']} total)")
    print(f"{'-' * 80}")
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Fantasy Pts':<12} {'Status':<12}")
    print(f"{'-' * 80}")
    for player in forwards[:limit]:
        name = player["name"]
        position = player["position"] or "N/A"
        team = player["nhl_team"] or "N/A"
        pts = player["fantasy_points"]
        status = player["status"] or "Healthy"
        print(f"{name:<30} {position:<5} {team:<5} {pts:<12.2f} {status:<12}")

    # Display defense
    print(f"\nDEFENSE ({counts['defense']} total)")
    print(f"{'-' * 80}")
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Fantasy Pts':<12} {'Status':<12}")
    print(f"{'-' * 80}")
    for player in defense[:limit]:
        name = player["name"]
        position = player["position"] or "N/A"
        team = player["nhl_team"] or "N/A"
        pts = player["fantasy_points"]
        status = player["status"] or "Healthy"
        print(f"{name:<30} {position:<5} {team:<5} {pts:<12.2f} {status:<12}")

    # Display goalies
    print(f"\nGOALIES ({counts['goalies']} total)")
    print(f"{'-' * 80}")
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Fantasy Pts':<12} {'Status':<12}")
    print(f"{'-' * 80}")
    for player in goalies[:limit]:
        name = player["name"]
        position = player["position"] or "N/A"
        team = player["nhl_team"] or "N/A"
        pts = player["fantasy_points"]
        status = player["status"] or "Healthy"
        print(f"{name:<30} {position:<5} {team:<5} {pts:<12.2f} {status:<12}")

    print(f"\nTotal available players: {counts['total']}")


def main():
    """Test the get_available_players function."""
    # Validate credentials
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing required credentials in .env file")
        print("Please ensure YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, and LEAGUE_ID are set")
        return

    print("Testing get_available_players tool...")
    print("Initializing Yahoo Fantasy Sports Query...")

    # Get available players (default: top 100)
    data = get_available_players(count=100)

    # Display results (top 10 per position)
    display_available_players(data, limit=10)


if __name__ == "__main__":
    main()
