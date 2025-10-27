#!/usr/bin/env python3
"""Tool to get your current fantasy hockey roster."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

# Add project root to path for imports when running standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.league import LeagueContext
from models.player import Player, PlayerPosition, PlayerStatus, RosterSlot
from models.roster import Roster, RosterCounts
from modules.yahoo_stats_fetcher import get_games_played_from_yahoo
from modules.yahoo_utils import (
    LEAGUE_ID,
    TEAM_ID,
    YAHOO_CLIENT_ID,
    YAHOO_CLIENT_SECRET,
    extract_player_fantasy_points,
    extract_player_name,
    extract_player_position_info,
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


def _parse_roster_slot(slot_str: str | None) -> RosterSlot | None:
    """Parse roster slot string to RosterSlot enum."""
    if not slot_str:
        return None
    try:
        return RosterSlot(slot_str)
    except ValueError:
        return None


def _parse_status(status_str: str | None) -> PlayerStatus:
    """Parse status string to PlayerStatus enum."""
    if not status_str or status_str == "" or status_str == "Healthy":
        return PlayerStatus.HEALTHY
    try:
        return PlayerStatus(status_str)
    except ValueError:
        # Default to HEALTHY if status is unknown
        return PlayerStatus.HEALTHY


def _convert_roster_to_players(roster: list) -> list[Player]:
    """Convert Yahoo API roster objects to Player models."""
    players = []

    for player in roster:
        player_name = extract_player_name(player)
        position_info = extract_player_position_info(player)
        fantasy_points = extract_player_fantasy_points(player)

        # Parse position
        position = _parse_position(position_info["position"])

        # Parse eligible positions
        eligible_positions = []
        for pos_str in position_info.get("eligible_positions", []):
            pos = _parse_position(pos_str)
            if pos:
                eligible_positions.append(pos)

        # Parse selected position (roster slot)
        selected_position = _parse_roster_slot(position_info.get("selected_position"))

        # Parse status
        status_str = player.status if hasattr(player, "status") else None
        status = _parse_status(status_str)
        is_injured = status != PlayerStatus.HEALTHY

        # Extract games played from Yahoo player stats
        is_goalie = position == PlayerPosition.GOALIE
        games_played = get_games_played_from_yahoo(player, is_goalie) or 0

        player_model = Player(
            player_id=str(player.player_id) if hasattr(player, "player_id") else None,
            name=player_name,
            position=position,
            eligible_positions=eligible_positions,
            selected_position=selected_position,
            nhl_team=player.editorial_team_abbr if hasattr(player, "editorial_team_abbr") else None,
            fantasy_points=fantasy_points,
            games_played=games_played,
            status=status,
            is_injured=is_injured,
        )

        players.append(player_model)

    return players


def _calculate_roster_counts(players: list[Player]) -> RosterCounts:
    """Calculate roster statistics by position and status."""
    forward_positions = [
        PlayerPosition.CENTER,
        PlayerPosition.LEFT_WING,
        PlayerPosition.RIGHT_WING,
        PlayerPosition.FORWARD,
    ]

    return RosterCounts(
        total=len(players),
        forwards=len([p for p in players if p.position in forward_positions]),
        defense=len([p for p in players if p.position == PlayerPosition.DEFENSE]),
        goalies=len([p for p in players if p.position == PlayerPosition.GOALIE]),
        active=len([p for p in players if p.is_active()]),
        bench=len([p for p in players if p.selected_position == RosterSlot.BENCH]),
        injured_reserve=len([p for p in players if p.is_on_ir()]),
    )


def _convert_league_context(league_info: dict) -> LeagueContext:
    """Convert league info dict to LeagueContext model."""
    return LeagueContext(
        league_id=league_info.get("league_id"),
        league_key=league_info.get("league_key"),
        league_name=league_info.get("league_name"),
        season=league_info.get("season"),
        current_week=league_info.get("current_week"),
        game_code=league_info.get("game_code"),
    )


class GetCurrentRoster(BaseTool):
    """Tool for fetching current fantasy hockey roster."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "get_current_roster",
        "description": "Get the current roster for a fantasy hockey team. Returns a Roster object with validated Player models, categorized by position with stats, injury status, and lineup position.",
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
    def run(cls, team_id: int | None = None) -> Roster:
        """
        Get the current roster for a team.

        Args:
            team_id: Yahoo team ID (defaults to user's team)

        Returns:
            Roster object with validated Player models

        Raises:
            Exception: If roster fetch fails
        """
        yahoo_query = initialize_yahoo_query()

        if team_id is None:
            team_id = int(TEAM_ID) if TEAM_ID else None
            if not team_id:
                teams = yahoo_query.get_league_teams()
                if teams and len(teams) > 0:
                    team_id = teams[0].team_id

        # Try multiple API endpoints (Yahoo API can be inconsistent)
        roster = None
        try:
            roster = yahoo_query.get_team_roster_player_stats(team_id)
        except Exception:
            try:
                roster = yahoo_query.get_team_roster_player_info_by_week(team_id)
            except Exception:
                roster = yahoo_query.get_team_roster_by_week(team_id)

        # Convert to Player models
        league_info = get_league_context_info(yahoo_query)
        league_context = _convert_league_context(league_info)
        players = _convert_roster_to_players(roster)

        # Sort by fantasy points (descending)
        players.sort(key=lambda p: p.fantasy_points, reverse=True)

        # Calculate roster statistics
        roster_counts = _calculate_roster_counts(players)

        # Return validated Roster model
        return Roster(
            team_id=str(team_id) if team_id else None,
            league_context=league_context,
            retrieved_at=datetime.now().isoformat(),
            players=players,
            roster_counts=roster_counts,
        )


def _print_position_group(players: list[Player], position_name: str):
    """Print a group of players by position."""
    print(f"\n{position_name} ({len(players)} players)")
    print("-" * 80)
    print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Slot':<8} {'Pts':<10} {'Status':<12}")
    print("-" * 80)
    for p in players:
        pos_str = p.position.value if p.position else "N/A"
        team_str = p.nhl_team or "N/A"
        slot_str = p.selected_position.value if p.selected_position else "N/A"
        status_str = p.status.value if p.status else "Healthy"
        print(
            f"{p.name:<30} {pos_str:<5} {team_str:<5} {slot_str:<8} {p.fantasy_points:<10.2f} {status_str:<12}"
        )


def display_roster(roster: Roster):
    """Display roster in a readable format."""
    print(f"\n{'=' * 80}")
    print(f"YOUR ROSTER (Team ID: {roster.team_id})")
    if roster.league_context and roster.league_context.league_name:
        print(f"League: {roster.league_context.league_name}")
    print("=" * 80)

    # Display by position groups
    forwards = roster.get_forwards()
    defense = roster.get_defensemen()
    goalies = roster.get_goalies()

    _print_position_group(forwards, "FORWARDS")
    _print_position_group(defense, "DEFENSE")
    _print_position_group(goalies, "GOALIES")

    counts = roster.roster_counts
    print(
        f"\nTotal: {counts.total} | Active: {counts.active} | Bench: {counts.bench} | IR: {counts.injured_reserve}"
    )


def main():
    """Test the get_current_roster function."""
    if not YAHOO_CLIENT_ID or not YAHOO_CLIENT_SECRET or not LEAGUE_ID:
        print("Error: Missing credentials in .env")
        return

    print("Testing get_current_roster...")
    tool = GetCurrentRoster()
    roster = tool.execute()
    display_roster(roster)


if __name__ == "__main__":
    main()
