#!/usr/bin/env python3
"""Tool to get your current fantasy hockey roster."""

from datetime import datetime
from typing import Any

from tools.base_tool import BaseTool
from modules.yahoo_utils import (
    TEAM_ID,
    YAHOO_CLIENT_ID,
    YAHOO_CLIENT_SECRET,
    LEAGUE_ID,
    initialize_yahoo_query,
    extract_player_name,
    extract_player_position_info,
    extract_player_fantasy_points,
    get_league_context_info,
)


def _convert_roster_to_flat_structure(roster: list) -> list[dict]:
    """Convert Yahoo API roster objects to flat dictionaries."""
    players = []

    for player in roster:
        player_name = extract_player_name(player)
        position_info = extract_player_position_info(player)
        fantasy_points = extract_player_fantasy_points(player)

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
    """Calculate roster statistics by position and status."""
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


class GetCurrentRoster(BaseTool):
    """Tool for fetching current fantasy hockey roster."""

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
        """Get the current roster for a team."""
        try:
            yahoo_query = initialize_yahoo_query()

            if team_id is None:
                team_id = int(TEAM_ID) if TEAM_ID else None
                if not team_id:
                    teams = yahoo_query.get_league_teams()
                    if teams and len(teams) > 0:
                        team_id = teams[0].team_id

            roster = None
            try:
                roster = yahoo_query.get_team_roster_player_stats(team_id)
            except Exception:
                try:
                    roster = yahoo_query.get_team_roster_player_info_by_week(team_id)
                except Exception:
                    roster = yahoo_query.get_team_roster_by_week(team_id)

            league_info = get_league_context_info(yahoo_query)
            players = _convert_roster_to_flat_structure(roster)
            players.sort(key=lambda p: p["fantasy_points"], reverse=True)
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


def _print_position_group(players: list[dict], position_name: str):
    """Print a group of players by position."""
    print(f"\n{position_name} ({len(players)} players)")
    print("-" * 80)
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Slot':<8} {'Pts':<10} {'Status':<12}")
    print("-" * 80)
    for p in players:
        print(f"{p['name']:<30} {p['position'] or 'N/A':<5} {p['nhl_team'] or 'N/A':<5} {p['selected_position'] or 'N/A':<8} {p['fantasy_points']:<10.2f} {p['status'] or 'Healthy':<12}")


def display_roster(roster_data: dict[str, Any]):
    """Display roster in a readable format."""
    if not roster_data["success"]:
        print(f"\nError: {roster_data['error']}")
        return

    data = roster_data["data"]
    players = data["players"]
    counts = data["roster_counts"]

    print(f"\n{'=' * 80}")
    print(f"YOUR ROSTER (Team ID: {data['team_id']})")
    if data["league_context"].get("league_name"):
        print(f"League: {data['league_context']['league_name']}")
    print("=" * 80)

    _print_position_group([p for p in players if p["position"] in ["C", "LW", "RW", "F"]], "FORWARDS")
    _print_position_group([p for p in players if p["position"] == "D"], "DEFENSE")
    _print_position_group([p for p in players if p["position"] == "G"], "GOALIES")

    print(f"\nTotal: {counts['total']} | Active: {counts['active']} | Bench: {counts['bench']} | IR: {counts['injured_reserve']}")


def main():
    """Test the get_current_roster function."""
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing credentials in .env")
        return

    print("Testing get_current_roster...")
    roster_data = get_current_roster()
    display_roster(roster_data)


if __name__ == "__main__":
    main()
