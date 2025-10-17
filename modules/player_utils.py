#!/usr/bin/env python3
"""Utilities for player analysis and comparison."""

from models.player import Player, PlayerPosition


def get_player_team_abbr(player: Player) -> str | None:
    """
    Extract normalized team abbreviation from player model.

    Args:
        player: Player model with nhl_team attribute

    Returns:
        Normalized team abbreviation (NHL API format) or None if no team

    Examples:
        >>> player = Player(name="John Doe", nhl_team="TB")
        >>> get_player_team_abbr(player)
        'TBL'
    """
    from modules.team_utils import normalize_team_abbr

    team = player.nhl_team
    return normalize_team_abbr(team) if team else None


def positions_are_compatible(
    drop_position: PlayerPosition | None,
    pickup_position: PlayerPosition | None
) -> bool:
    """
    Check if two positions are compatible for streaming.

    Simplified matching: both must be goalies or both must be non-goalies.
    This prevents dropping a goalie to pick up a skater (or vice versa).

    Args:
        drop_position: Position of player being dropped
        pickup_position: Position of player being picked up

    Returns:
        True if positions are compatible for streaming

    Examples:
        >>> positions_are_compatible(PlayerPosition.CENTER, PlayerPosition.LEFT_WING)
        True
        >>> positions_are_compatible(PlayerPosition.GOALIE, PlayerPosition.CENTER)
        False
        >>> positions_are_compatible(PlayerPosition.GOALIE, PlayerPosition.GOALIE)
        True
    """
    if not drop_position or not pickup_position:
        return False

    # Both must be goalies or both must be non-goalies
    return (drop_position == PlayerPosition.GOALIE) == (pickup_position == PlayerPosition.GOALIE)
