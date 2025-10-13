#!/usr/bin/env python3
"""Tool to get available free agents."""

from datetime import datetime
from typing import Any, ClassVar

from modules.yahoo_utils import (
    LEAGUE_ID,
    YAHOO_CLIENT_ID,
    YAHOO_CLIENT_SECRET,
    extract_player_name,
    get_league_context_info,
    initialize_yahoo_query,
)
from tools.base_tool import BaseTool


class GetAvailablePlayers(BaseTool):
    """Tool for fetching available free agent players from Yahoo Fantasy Hockey."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
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
    def run(cls, count: int = 100, position: str | None = None) -> dict[str, Any]:
        """Get available free agent players from Yahoo Fantasy Hockey."""
        try:
            yahoo_query = initialize_yahoo_query()
            league_key = yahoo_query.get_league_key()
            league_info = get_league_context_info(yahoo_query)

            all_players = []
            batch_size = 25
            current_start = 0

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
                            break
                    else:
                        all_players.append(players_batch)
                        break

                    current_start += batch_count
                except Exception:
                    break

            players = []
            for player in all_players:
                player_name = extract_player_name(player)

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

                fantasy_points = 0.0
                if (
                    hasattr(player, "player_points")
                    and player.player_points
                    and hasattr(player.player_points, "total")
                    and player.player_points.total
                ):
                    fantasy_points = float(player.player_points.total)

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
                    "ownership_percentage": None,
                }

                if position is None or position_value == position or position in eligible_positions:
                    players.append(player_data)

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


TOOL_DEFINITION = GetAvailablePlayers.TOOL_DEFINITION
get_available_players = GetAvailablePlayers.run


def _print_fa_position_group(players: list[dict], position_name: str, limit: int):
    """Print a group of free agent players."""
    print(f"\n{position_name} ({len(players)} total)")
    print("-" * 80)
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Fantasy Pts':<12} {'Status':<12}")
    print("-" * 80)
    for p in players[:limit]:
        print(
            f"{p['name']:<30} {p['position'] or 'N/A':<5} {p['nhl_team'] or 'N/A':<5} {p['fantasy_points']:<12.2f} {p['status'] or 'Healthy':<12}"
        )


def display_available_players(data: dict[str, Any], limit: int = 10):
    """Display available players in a readable format."""
    if not data["success"]:
        print(f"\nError: {data['error']}")
        return

    result_data = data["data"]
    players = result_data["players"]
    counts = result_data["player_counts"]

    print(f"\n{'=' * 80}")
    print(f"AVAILABLE FREE AGENTS (Top {limit} per position)")
    if result_data["league_context"].get("league_name"):
        print(f"League: {result_data['league_context']['league_name']}")
    print("=" * 80)

    _print_fa_position_group(
        [p for p in players if p["position"] in ["C", "LW", "RW", "F"]], "FORWARDS", limit
    )
    _print_fa_position_group([p for p in players if p["position"] == "D"], "DEFENSE", limit)
    _print_fa_position_group([p for p in players if p["position"] == "G"], "GOALIES", limit)

    print(f"\nTotal available: {counts['total']}")


def main():
    """Test the get_available_players function."""
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing credentials in .env")
        return

    print("Testing get_available_players...")
    data = get_available_players(count=100)
    display_available_players(data, limit=10)


if __name__ == "__main__":
    main()
