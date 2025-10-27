#!/usr/bin/env python3
"""
Yahoo Fantasy Stats Fetcher.

Fetches individual stat values from Yahoo Fantasy API to use as the source of truth
for player statistics, particularly games played for PPG calculations.
"""

try:
    from modules.logger import AgentLogger
    logger = AgentLogger.get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


# Stat ID mappings from Yahoo Fantasy API
# Reference: stat_id_mappings.txt
STAT_ID_GAMES_PLAYED = 0  # For skaters
STAT_ID_GAMES_STARTED = 18  # For goalies
STAT_ID_GOALIE_GAMES = 30  # Alternative goalie games stat


def parse_stat_value(value) -> float:
    """
    Parse a stat value from Yahoo API into a float.

    Yahoo API can return stats as int, float, string, or None.

    Args:
        value: Raw stat value from Yahoo API

    Returns:
        Parsed float value, or 0 if None/invalid
    """
    if value is None:
        return 0

    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse stat value: {value}")
        return 0


def get_player_stats_from_yahoo(player, is_goalie: bool) -> dict[str, float] | None:
    """
    Extract stat values from a Yahoo Fantasy player object.

    Args:
        player: Yahoo Fantasy player object from yfpy
        is_goalie: True if player is a goalie

    Returns:
        Dictionary with stat_id -> value mappings, or None if no stats available
        Example: {0: 10.0, 1: 5.0, 2: 8.0} for games_played, goals, assists
    """
    if not hasattr(player, 'player_stats') or not player.player_stats:
        return None

    stats_dict = {}

    # Yahoo API structure: player.player_stats.stats is a list of stat objects
    # Each stat object has: stat_id, value
    if hasattr(player.player_stats, 'stats') and player.player_stats.stats:
        stats_list = player.player_stats.stats

        # Handle both list and dict formats
        if isinstance(stats_list, list):
            for stat in stats_list:
                if hasattr(stat, 'stat_id') and hasattr(stat, 'value'):
                    stat_id = int(stat.stat_id)
                    value = parse_stat_value(stat.value)
                    stats_dict[stat_id] = value
        elif isinstance(stats_list, dict):
            for stat_id, value in stats_list.items():
                stats_dict[int(stat_id)] = parse_stat_value(value)

    return stats_dict if stats_dict else None


def get_games_played_from_yahoo(player, is_goalie: bool) -> int | None:
    """
    Extract games played/started from Yahoo Fantasy player stats.

    Uses Yahoo API as the source of truth for games played.
    For skaters: uses stat_id 0 (Games Played)
    For goalies: uses stat_id 18 (Games Started), fallback to stat_id 30 (Goalie Games)

    Args:
        player: Yahoo Fantasy player object from yfpy
        is_goalie: True if player is a goalie

    Returns:
        Games played/started as integer, or None if not available
    """
    stats = get_player_stats_from_yahoo(player, is_goalie)

    if not stats:
        return None

    if is_goalie:
        # Try games started first (stat_id 18)
        games = stats.get(STAT_ID_GAMES_STARTED)
        if games is not None and games > 0:
            return int(games)

        # Fallback to goalie games (stat_id 30)
        games = stats.get(STAT_ID_GOALIE_GAMES)
        if games is not None and games > 0:
            return int(games)

        return None
    else:
        # For skaters, use stat_id 0 (Games Played)
        games = stats.get(STAT_ID_GAMES_PLAYED)
        return int(games) if games is not None else None
