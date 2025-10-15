#!/usr/bin/env python3
"""Tool to get available free agents."""

import sys
from datetime import datetime
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
    get_league_context_info,
    initialize_yahoo_query,
)
from tools.base_tool import BaseTool


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
    def run(cls, count: int = 100, position: str | None = None) -> list[Player]:
        """
        Get available free agent players from Yahoo Fantasy Hockey.

        Args:
            count: Maximum number of players to return (default 100)
            position: Filter by position ('C', 'LW', 'RW', 'D', 'G') or None for all

        Returns:
            List of Player models sorted by fantasy points (descending)

        Raises:
            Exception: If API fetch fails
        """
        yahoo_query = initialize_yahoo_query()
        league_key = yahoo_query.get_league_key()

        all_players = []
        batch_size = 25
        current_start = 0

        # Fetch players in batches (Yahoo API limitation)
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

        # Convert to Player models
        players = []
        for player in all_players:
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
                nhl_team=player.editorial_team_abbr
                if hasattr(player, "editorial_team_abbr")
                else None,
                fantasy_points=fantasy_points,
                status=status,
                is_injured=is_injured,
            )

            # Filter by position if specified
            if position is None:
                players.append(player_model)
            elif position_enum and position_enum.value == position:
                players.append(player_model)
            elif any(p.value == position for p in eligible_positions):
                players.append(player_model)

        # Sort by fantasy points (descending)
        players.sort(key=lambda p: p.fantasy_points, reverse=True)

        return players


TOOL_DEFINITION = GetAvailablePlayers.TOOL_DEFINITION
get_available_players = GetAvailablePlayers.run


def _print_fa_position_group(players: list[Player], position_name: str, limit: int):
    """Print a group of free agent players."""
    print(f"\n{position_name} ({len(players)} total)")
    print("-" * 80)
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Fantasy Pts':<12} {'Status':<12}")
    print("-" * 80)
    for p in players[:limit]:
        pos_str = p.position.value if p.position else "N/A"
        team_str = p.nhl_team or "N/A"
        status_str = p.status.value if p.status else "Healthy"
        print(f"{p.name:<30} {pos_str:<5} {team_str:<5} {p.fantasy_points:<12.2f} {status_str:<12}")


def display_available_players(players: list[Player], limit: int = 10):
    """Display available players in a readable format."""
    # Group by position
    forward_positions = [
        PlayerPosition.CENTER,
        PlayerPosition.LEFT_WING,
        PlayerPosition.RIGHT_WING,
        PlayerPosition.FORWARD,
    ]
    forwards = [p for p in players if p.position in forward_positions]
    defense = [p for p in players if p.position == PlayerPosition.DEFENSE]
    goalies = [p for p in players if p.position == PlayerPosition.GOALIE]

    print(f"\n{'=' * 80}")
    print(f"AVAILABLE FREE AGENTS (Top {limit} per position)")
    print("=" * 80)

    _print_fa_position_group(forwards, "FORWARDS", limit)
    _print_fa_position_group(defense, "DEFENSE", limit)
    _print_fa_position_group(goalies, "GOALIES", limit)

    print(f"\nTotal available: {len(players)}")


def main():
    """Test the get_available_players function."""
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing credentials in .env")
        return

    print("Testing get_available_players...")
    players = get_available_players(count=100)
    display_available_players(players, limit=10)


if __name__ == "__main__":
    main()
