#!/usr/bin/env python3
"""Utilities for schedule calculations and date handling."""

from datetime import datetime, timedelta

from models.game import Game
from models.player import Player
from models.schedule import Schedule


def get_fantasy_week_boundaries(weeks: int = 2) -> tuple[datetime, datetime, list[tuple[datetime, datetime]]]:
    """
    Get start/end dates for fantasy weeks (Monday-Sunday), starting from today.

    This function returns the date range from TODAY through the end of the next N-1
    fantasy weeks. For example, if weeks=2 and today is Wednesday, it will return:
    - Week 1: Wednesday (today) through Sunday (end of current fantasy week)
    - Week 2: Monday through Sunday (next full fantasy week)

    Args:
        weeks: Number of fantasy weeks to include (default 2)
               Week 1 = rest of current week (today -> Sunday)
               Week 2+ = full fantasy weeks (Monday -> Sunday)

    Returns:
        Tuple of (start_date, end_date, week_boundaries_list)
        where:
        - start_date is TODAY
        - end_date is the Sunday of the (weeks-1)th week from now
        - week_boundaries_list is [(week1_start, week1_end), (week2_start, week2_end), ...]

    Examples:
        >>> # If today is Wednesday Oct 18, 2025
        >>> start, end, boundaries = get_fantasy_week_boundaries(weeks=2)
        >>> len(boundaries)
        2
        >>> boundaries[0][0]  # Today (Wednesday)
        datetime.datetime(2025, 10, 18, 0, 0)
        >>> boundaries[0][1].weekday()  # Sunday
        6
        >>> boundaries[1][0].weekday()  # Next Monday
        0
        >>> boundaries[1][1].weekday()  # Next Sunday
        6
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_until_sunday = 6 - today.weekday()  # 0 = Monday, 6 = Sunday

    week_boundaries = []

    # Week 1: Today through end of current fantasy week (Sunday)
    current_week_end = today + timedelta(days=days_until_sunday)
    week_boundaries.append((today, current_week_end))

    # Week 2+: Full fantasy weeks (Monday-Sunday)
    for i in range(1, weeks):
        week_start = current_week_end + timedelta(days=1)  # Monday after previous Sunday
        week_end = week_start + timedelta(days=6)  # Sunday
        week_boundaries.append((week_start, week_end))
        current_week_end = week_end

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
