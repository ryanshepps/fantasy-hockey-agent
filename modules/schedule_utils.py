#!/usr/bin/env python3
"""Utilities for schedule calculations and date handling."""

from datetime import datetime, timedelta

from models.game import Game
from models.player import Player
from models.schedule import Schedule


def get_fantasy_week_boundaries(weeks: int = 2) -> tuple[datetime, datetime, list[tuple[datetime, datetime]]]:
    """
    Get start/end dates for fantasy weeks (Monday-Sunday).

    Args:
        weeks: Number of fantasy weeks to look ahead (default 2)

    Returns:
        Tuple of (start_date, end_date, week_boundaries_list)
        where week_boundaries_list is [(week1_start, week1_end), (week2_start, week2_end), ...]

    Examples:
        >>> start, end, boundaries = get_fantasy_week_boundaries(weeks=2)
        >>> len(boundaries)
        2
        >>> boundaries[0][0].weekday()  # Monday
        0
        >>> boundaries[0][1].weekday()  # Sunday
        6
    """
    today = datetime.now()
    days_since_monday = today.weekday()
    current_week_monday = today - timedelta(days=days_since_monday)

    week_boundaries = []
    for i in range(weeks):
        week_start = current_week_monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        week_boundaries.append((week_start, week_end))

    start_date = week_boundaries[0][0]
    end_date = week_boundaries[-1][1]

    return (start_date, end_date, week_boundaries)


def get_date_range_from_boundaries(start_date: datetime, end_date: datetime) -> list[str]:
    """
    Generate list of dates between start and end (YYYY-MM-DD format).

    Args:
        start_date: Starting date (inclusive)
        end_date: Ending date (inclusive)

    Returns:
        List of date strings in YYYY-MM-DD format

    Examples:
        >>> from datetime import datetime
        >>> start = datetime(2025, 10, 13)
        >>> end = datetime(2025, 10, 15)
        >>> get_date_range_from_boundaries(start, end)
        ['2025-10-13', '2025-10-14', '2025-10-15']
    """
    dates = []
    current = start_date

    while current <= end_date:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return dates


def calculate_games_for_player(
    player: Player,
    schedule: Schedule,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[Game]:
    """
    Get list of games for a specific player based on their team's schedule.

    Args:
        player: Player model with nhl_team attribute
        schedule: Schedule model from get_team_schedule tool
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        List of Game models for this player's team

    Examples:
        >>> from models.player import Player
        >>> from models.schedule import Schedule
        >>> player = Player(name="McDavid", nhl_team="EDM")
        >>> # schedule = get_team_schedule(weeks=2)
        >>> # games = calculate_games_for_player(player, schedule)
    """
    from modules.player_utils import get_player_team_abbr

    try:
        from modules.logger import AgentLogger
        logger = AgentLogger.get_logger(__name__)
    except ImportError:
        import logging
        logger = logging.getLogger(__name__)

    team_abbr = get_player_team_abbr(player)
    if not team_abbr:
        logger.warning(f"Could not determine team for player: {player.name}")
        return []

    # Find team in schedule data
    team_schedule = schedule.get_team_schedule(team_abbr)
    if not team_schedule:
        logger.warning(f"Team {team_abbr} not found in schedule data")
        return []

    # Get games (optionally filtered by date range)
    if start_date and end_date:
        return team_schedule.games_in_period(start_date, end_date)
    elif start_date:
        return [g for g in team_schedule.games if g.date >= start_date]
    elif end_date:
        return [g for g in team_schedule.games if g.date <= end_date]
    else:
        return team_schedule.games
