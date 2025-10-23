#!/usr/bin/env python3
"""
NHL Player ID Mapping and Stats Fetching Module.

This module manages the mapping between Yahoo Fantasy player IDs and NHL API player IDs,
with persistent caching to minimize API calls and allow manual corrections.
"""

import json
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

try:
    from modules.logger import AgentLogger

    logger = AgentLogger.get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


# Cache file location
CACHE_FILE = Path(__file__).parent.parent / "data" / "player_id_mappings.json"

# NHL API base URL
NHL_API_BASE = "https://api-web.nhle.com/v1"

# In-memory cache for current session (avoid repeated file I/O)
_session_cache: dict[str, dict[str, Any]] = {}
_cache_loaded = False


def _load_cache() -> dict[str, dict[str, Any]]:
    """Load player ID mappings from cache file."""
    global _session_cache, _cache_loaded

    if _cache_loaded:
        return _session_cache

    if not CACHE_FILE.exists():
        logger.info("No player ID cache found, will create new cache")
        _session_cache = {"mappings": {}, "metadata": {"version": "1.0"}}
        _cache_loaded = True
        return _session_cache

    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
            _session_cache = data
            _cache_loaded = True
            num_mappings = len(data.get("mappings", {}))
            logger.info(f"Loaded {num_mappings} player ID mappings from cache")
            return _session_cache
    except Exception as e:
        logger.error(f"Failed to load player ID cache: {e}")
        _session_cache = {"mappings": {}, "metadata": {"version": "1.0"}}
        _cache_loaded = True
        return _session_cache


def _save_cache(cache: dict[str, dict[str, Any]]) -> None:
    """Save player ID mappings to cache file."""
    try:
        # Ensure data directory exists
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Update metadata
        cache["metadata"]["last_updated"] = datetime.now().isoformat()

        # Write to file
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)

        logger.info(f"Saved {len(cache.get('mappings', {}))} player mappings to cache")
    except Exception as e:
        logger.error(f"Failed to save player ID cache: {e}")


def _search_nhl_roster(player_name: str, team_abbr: str) -> int | None:
    """
    Search NHL team roster for player by name.

    Args:
        player_name: Player's full name (e.g., "Nick Schmaltz")
        team_abbr: NHL team abbreviation (e.g., "UTA", "TOR")

    Returns:
        NHL player ID if found, None otherwise
    """
    try:
        url = f"{NHL_API_BASE}/roster/{team_abbr}/current"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            logger.warning(f"NHL API returned {response.status_code} for team {team_abbr}")
            return None

        data = response.json()

        # Helper function to normalize names (remove accents, lowercase, remove punctuation)
        def normalize_name(name: str) -> str:
            # Remove accents (é -> e, à -> a, etc.)
            name = unicodedata.normalize("NFD", name)
            name = "".join(c for c in name if unicodedata.category(c) != "Mn")
            # Lowercase and remove punctuation
            return name.lower().replace(".", "").replace("'", "").replace("-", " ")

        # Normalize search name
        search_name_normalized = normalize_name(player_name)
        search_last_name = search_name_normalized.split()[-1] if search_name_normalized else ""

        # Search all position groups
        for position_group in ["forwards", "defensemen", "goalies"]:
            if position_group not in data:
                continue

            for player in data[position_group]:
                # Get player name from NHL API
                first_name = player.get("firstName", {}).get("default", "")
                last_name = player.get("lastName", {}).get("default", "")
                full_name_normalized = normalize_name(f"{first_name} {last_name}")
                last_name_normalized = normalize_name(last_name)

                # Match by last name (most reliable - handles accents and spelling variations)
                if search_last_name and (
                    last_name_normalized == search_last_name
                    or search_last_name in full_name_normalized
                    or last_name_normalized in search_name_normalized
                ):
                    nhl_id = player.get("id")
                    if nhl_id:
                        logger.info(
                            f"Found NHL ID {nhl_id} for {player_name} ({team_abbr}) "
                            f"matched as '{first_name} {last_name}'"
                        )
                        return nhl_id

        logger.warning(f"Could not find NHL ID for {player_name} on {team_abbr} roster")
        return None

    except Exception as e:
        logger.error(f"Error searching NHL roster for {player_name}: {e}")
        return None


def get_nhl_player_id(yahoo_id: str, player_name: str, team_abbr: str | None) -> int | None:
    """
    Get NHL player ID for a Yahoo Fantasy player.

    Checks cache first, then searches NHL API if needed.

    Args:
        yahoo_id: Yahoo Fantasy player ID
        player_name: Player's full name
        team_abbr: NHL team abbreviation (e.g., "UTA", "TOR")

    Returns:
        NHL player ID if found, None otherwise
    """
    cache = _load_cache()

    # Check cache first
    if yahoo_id in cache.get("mappings", {}):
        mapping = cache["mappings"][yahoo_id]
        nhl_id = mapping.get("nhl_id")

        # If manual mapping, always trust it
        if mapping.get("source") == "manual":
            logger.debug(f"Using manual mapping for {player_name}: NHL ID {nhl_id}")
            return nhl_id

        # For auto mappings, use cached value
        logger.debug(f"Using cached mapping for {player_name}: NHL ID {nhl_id}")
        return nhl_id

    # Not in cache - search NHL API
    if not team_abbr:
        logger.warning(f"No team abbreviation for {player_name}, cannot search NHL API")
        return None

    nhl_id = _search_nhl_roster(player_name, team_abbr)

    if nhl_id:
        # Save to cache
        cache["mappings"][yahoo_id] = {
            "yahoo_id": yahoo_id,
            "nhl_id": nhl_id,
            "player_name": player_name,
            "nhl_team": team_abbr,
            "last_verified": datetime.now().strftime("%Y-%m-%d"),
            "source": "auto",
        }
        _save_cache(cache)

    return nhl_id


def get_player_games_played(nhl_id: int, is_goalie: bool) -> int | None:
    """
    Fetch games played (or games started for goalies) from NHL API.

    Args:
        nhl_id: NHL player ID
        is_goalie: True if player is a goalie (use games started)

    Returns:
        Games played/started, or None if not available
    """
    try:
        url = f"{NHL_API_BASE}/player/{nhl_id}/landing"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            logger.warning(f"NHL API returned {response.status_code} for player {nhl_id}")
            return None

        data = response.json()

        # Get current season stats
        if "featuredStats" not in data or "regularSeason" not in data["featuredStats"]:
            logger.warning(f"No season stats found for NHL player {nhl_id}")
            return None

        season_stats = data["featuredStats"]["regularSeason"].get("subSeason", {})

        if is_goalie:
            # For goalies, use games started (more accurate than games played)
            games = season_stats.get("gamesStarted")
            if games is None:
                # Fallback to games played if games started not available
                games = season_stats.get("gamesPlayed")
                logger.debug(f"Using gamesPlayed for goalie {nhl_id} (gamesStarted not available)")
        else:
            # For skaters, use games played
            games = season_stats.get("gamesPlayed")

        if games is not None:
            logger.debug(
                f"NHL player {nhl_id}: {games} games {'started' if is_goalie else 'played'}"
            )
            return int(games)

        logger.warning(f"No games played data for NHL player {nhl_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching stats for NHL player {nhl_id}: {e}")
        return None


def refresh_mapping(yahoo_id: str, player_name: str, team_abbr: str) -> int | None:
    """
    Force refresh a player mapping from NHL API.

    Useful when a player changes teams or the cached mapping is incorrect.

    Args:
        yahoo_id: Yahoo Fantasy player ID
        player_name: Player's full name
        team_abbr: NHL team abbreviation

    Returns:
        New NHL player ID if found, None otherwise
    """
    cache = _load_cache()

    # Remove from cache
    if yahoo_id in cache.get("mappings", {}):
        del cache["mappings"][yahoo_id]
        logger.info(f"Removed cached mapping for {player_name}")

    # Search NHL API
    nhl_id = _search_nhl_roster(player_name, team_abbr)

    if nhl_id:
        # Save to cache
        cache["mappings"][yahoo_id] = {
            "yahoo_id": yahoo_id,
            "nhl_id": nhl_id,
            "player_name": player_name,
            "nhl_team": team_abbr,
            "last_verified": datetime.now().strftime("%Y-%m-%d"),
            "source": "auto",
        }
        _save_cache(cache)

    return nhl_id


def main():
    """Test the NHL player mapper."""
    print("Testing NHL Player Mapper...\n")

    # Test cases
    test_players = [
        ("6386", "Nick Schmaltz", "UTA"),
        ("4588", "Cale Makar", "COL"),
        ("5465", "Anthony Stolarz", "TOR"),
    ]

    for yahoo_id, name, team in test_players:
        print(f"\n=== {name} ({team}) ===")

        # Get NHL ID
        nhl_id = get_nhl_player_id(yahoo_id, name, team)
        if nhl_id:
            print(f"NHL ID: {nhl_id}")

            # Get games played
            is_goalie = "Stolarz" in name
            gp = get_player_games_played(nhl_id, is_goalie)
            if gp:
                print(f"Games {'Started' if is_goalie else 'Played'}: {gp}")
        else:
            print("NHL ID not found")

    print(f"\n\nCache saved to: {CACHE_FILE}")


if __name__ == "__main__":
    main()
