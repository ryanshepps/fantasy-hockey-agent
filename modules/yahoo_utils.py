#!/usr/bin/env python3
"""Shared utilities for Yahoo Fantasy API tools."""

import os
from pathlib import Path

from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery

load_dotenv()

YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID")
YAHOO_CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET")
LEAGUE_ID = os.getenv("LEAGUE_ID")
TEAM_ID = os.getenv("TEAM_ID")


def initialize_yahoo_query():
    """Initialize Yahoo Fantasy Sports Query object."""
    try:
        from modules.yahoo_auth import get_yahoo_query

        return get_yahoo_query()
    except ImportError:
        return YahooFantasySportsQuery(
            league_id=LEAGUE_ID,
            game_code="nhl",
            game_id=None,
            yahoo_consumer_key=YAHOO_CLIENT_ID,
            yahoo_consumer_secret=YAHOO_CLIENT_SECRET,
            env_file_location=Path("."),
            save_token_data_to_env_file=True,
        )


def extract_player_name(player) -> str:
    """Extract player name from Yahoo API player object."""
    if hasattr(player, "name"):
        if isinstance(player.name, str):
            return player.name
        elif hasattr(player.name, "full"):
            return player.name.full
        else:
            return str(player.name)
    return "Unknown"


def extract_player_position_info(player) -> dict:
    """Extract position information from Yahoo API player object."""
    position = None
    eligible_positions = []
    selected_position = None

    if hasattr(player, "primary_position"):
        position = player.primary_position
    elif hasattr(player, "display_position"):
        position = player.display_position
    elif hasattr(player, "position_type"):
        position = player.position_type

    if hasattr(player, "eligible_positions") and player.eligible_positions:
        pos = player.eligible_positions
        eligible_positions = pos if isinstance(pos, list) else [pos]
        if not position and eligible_positions:
            position = eligible_positions[0]

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


def extract_player_fantasy_points(player) -> float:
    """Extract fantasy points from Yahoo API player object."""
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


def get_league_context_info(yahoo_query) -> dict:
    """Get league context information (name, week, season)."""
    league_info = {}
    try:
        league = yahoo_query.get_league_info()
        if league:
            league_name = getattr(league, "name", None)
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
