#!/usr/bin/env python3
"""
Tool to get detailed NHL player statistics for player quality assessment.

This tool fetches season-long stats for players to help determine their skill level
and value, which is critical for avoiding bad drop recommendations (e.g., don't drop
Cale Makar just because he has fewer games).

Example Usage:
    from tools.get_player_stats import get_player_stats

    # Get stats for specific players
    result = get_player_stats(player_names=["Connor McDavid", "Cale Makar"])

    # Get stats for a team's players
    result = get_player_stats(team_abbr="EDM")
"""

import sys
from pathlib import Path
from typing import Any, ClassVar

from tools.base_tool import BaseTool

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from modules.logger import AgentLogger

    logger = AgentLogger.get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

try:
    from nhlpy import NHLClient

    NHL_API_AVAILABLE = True
except ImportError:
    NHL_API_AVAILABLE = False


def _calculate_fantasy_points_per_game(stats: dict, position: str) -> float:
    """
    Calculate fantasy points per game based on league scoring settings.

    League Scoring:
    - Skaters:
        - 5 points for a goal
        - 2 points for an assist
        - 2 points for a power play point (stacking)
        - 3 points for a short handed goal
        - 0.5 points for a shot on goal
        - 0.5 points for a hit
        - 0.5 points for a block
    - Goalies:
        - 6 points for a win
        - -3.5 points for a goal against
        - 0.5 points for a save
        - 6 points for a shutout

    Args:
        stats: Player statistics dictionary
        position: Player position (F, D, or G)

    Returns:
        Fantasy points per game
    """
    games_played = stats.get("gamesPlayed", 0)
    if games_played == 0:
        return 0.0

    if position == "G":
        # Goalie scoring
        wins = stats.get("wins", 0)
        goals_against = stats.get("goalsAgainst", 0)
        saves = stats.get("saves", 0)
        shutouts = stats.get("shutouts", 0)

        total_points = (wins * 6) + (goals_against * -3.5) + (saves * 0.5) + (shutouts * 6)
    else:
        # Skater scoring
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        powerplay_points = stats.get("powerPlayPoints", 0)
        shorthanded_goals = stats.get("shorthandedGoals", 0)
        shots = stats.get("shots", 0)
        hits = stats.get("hits", 0)
        blocks = stats.get("blockedShots", 0)

        total_points = (
            (goals * 5)
            + (assists * 2)
            + (powerplay_points * 2)
            + (shorthanded_goals * 3)
            + (shots * 0.5)
            + (hits * 0.5)
            + (blocks * 0.5)
        )

    return round(total_points / games_played, 2)


def _get_player_tier(fantasy_ppg: float, position: str) -> str:
    """
    Classify player into tiers based on fantasy points per game.

    Args:
        fantasy_ppg: Fantasy points per game
        position: Player position

    Returns:
        Player tier (Elite, High-End, Mid-Tier, Streamable, Deep League)
    """
    if position == "G":
        # Goalie tiers
        if fantasy_ppg >= 6.0:
            return "Elite"
        elif fantasy_ppg >= 4.5:
            return "High-End"
        elif fantasy_ppg >= 3.0:
            return "Mid-Tier"
        elif fantasy_ppg >= 1.5:
            return "Streamable"
        else:
            return "Deep League"
    else:
        # Skater tiers
        if fantasy_ppg >= 4.5:
            return "Elite"
        elif fantasy_ppg >= 3.5:
            return "High-End"
        elif fantasy_ppg >= 2.5:
            return "Mid-Tier"
        elif fantasy_ppg >= 1.5:
            return "Streamable"
        else:
            return "Deep League"


class GetPlayerStats(BaseTool):
    """Tool for fetching NHL player statistics."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "get_player_stats",
        "description": "Get detailed season statistics for NHL players to assess their quality and value. This helps determine which players are 'droppable' vs 'must-keep' based on their performance level. Use this to avoid recommending drops of elite players like Cale Makar or Connor McDavid just because they have fewer games in a given week.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_names": {
                    "type": "array",
                    "description": "List of player names to fetch stats for",
                    "items": {"type": "string"},
                },
                "player_ids": {
                    "type": "array",
                    "description": "List of NHL player IDs to fetch stats for",
                    "items": {"type": "integer"},
                },
                "team_abbr": {
                    "type": "string",
                    "description": "Team abbreviation to fetch all players from (e.g., 'EDM', 'TOR')",
                },
            },
            "required": [],
        },
    }

    @classmethod
    def run(
        cls,
        player_names: list[str] | None = None,
        player_ids: list[int] | None = None,
        team_abbr: str | None = None,
    ) -> dict[str, Any]:
        """
        Get detailed season statistics for NHL players.

        Fetches current season stats and calculates fantasy value metrics to help
        assess player quality and avoid dropping valuable players.

        Args:
            player_names: List of player names to fetch stats for
            player_ids: List of NHL player IDs to fetch stats for
            team_abbr: Team abbreviation to fetch all players from (e.g., "EDM", "TOR")

        Returns:
            Dictionary with structure:
            {
                'success': bool,
                'players': [
                    {
                        'id': int,
                        'name': str,
                        'team': str,
                        'position': str,
                        'stats': {
                            'gamesPlayed': int,
                            'goals': int,
                            'assists': int,
                            'points': int,
                            'powerPlayPoints': int,
                            'shots': int,
                            'hits': int,
                            'blockedShots': int,
                            # ... other stats
                        },
                        'fantasy_ppg': float,
                        'tier': str,  # Elite, High-End, Mid-Tier, Streamable, Deep League
                        'droppable': bool  # Recommendation on whether this player is droppable
                    }
                ],
                'summary': str
            }
        """
        if not NHL_API_AVAILABLE:
            return {
                "success": False,
                "error": "nhl-api-py library is not installed. Install with: pip install nhl-api-py",
            }

        if not player_names and not player_ids and not team_abbr:
            return {
                "success": False,
                "error": "Must provide player_names, player_ids, or team_abbr",
            }

        try:
            client = NHLClient()
            players_data = []

            # For now, we'll use a simplified approach - fetch roster by team
            # The NHL API doesn't have a great player search, so we'll work with team rosters

            if team_abbr:
                logger.info(f"Fetching stats for team: {team_abbr}")
                # This is a placeholder - you'll need to implement team roster fetching
                # For now, return a message
                return {
                    "success": False,
                    "error": "Team roster fetching not yet implemented. Use player_names instead.",
                }

            # For player names, we need to search and match
            # This is also limited by the NHL API - in practice, you'd want to use
            # the Yahoo Fantasy API to get player IDs and then fetch NHL stats
            if player_names:
                logger.info(f"Fetching stats for players: {player_names}")

                # Placeholder implementation
                # In a real implementation, you'd:
                # 1. Search for each player name to get their NHL ID
                # 2. Fetch their season stats
                # 3. Calculate fantasy metrics

                return {
                    "success": False,
                    "error": "Player name search not yet implemented. This tool needs integration with Yahoo Fantasy player IDs.",
                }

            if player_ids:
                logger.info(f"Fetching stats for player IDs: {player_ids}")

                for player_id in player_ids:
                    try:
                        # Fetch player info and stats
                        # Note: This is a placeholder - actual API calls depend on nhlpy structure
                        player_info = client.players.player_landing(player_id)

                        if not player_info:
                            continue

                        # Extract stats (structure depends on API response)
                        stats = player_info.get("stats", {})
                        position = player_info.get("position", "F")

                        # Calculate fantasy value
                        fantasy_ppg = _calculate_fantasy_points_per_game(stats, position)
                        tier = _get_player_tier(fantasy_ppg, position)

                        # Determine droppability
                        # Elite and High-End players should never be dropped for streaming
                        droppable = tier in ["Streamable", "Deep League"]

                        players_data.append(
                            {
                                "id": player_id,
                                "name": player_info.get("name", "Unknown"),
                                "team": player_info.get("team", "Unknown"),
                                "position": position,
                                "stats": stats,
                                "fantasy_ppg": fantasy_ppg,
                                "tier": tier,
                                "droppable": droppable,
                            }
                        )

                    except Exception as e:
                        logger.warning(f"Error fetching stats for player ID {player_id}: {e}")
                        continue

            # Sort by fantasy PPG
            players_data.sort(key=lambda x: x["fantasy_ppg"], reverse=True)

            # Create summary
            if players_data:
                elite_count = sum(1 for p in players_data if p["tier"] == "Elite")
                droppable_count = sum(1 for p in players_data if p["droppable"])

                summary = (
                    f"Fetched stats for {len(players_data)} players:\n"
                    f"- Elite/High-End players: {elite_count}\n"
                    f"- Streamable/droppable players: {droppable_count}\n"
                    f"- Top player: {players_data[0]['name']} ({players_data[0]['fantasy_ppg']} FPts/G)"
                )
            else:
                summary = "No player stats found"

            return {
                "success": True,
                "players": players_data,
                "total_players": len(players_data),
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error fetching player stats: {e}")
            return {"success": False, "error": f"Failed to fetch player stats: {e!s}"}


# Export for backwards compatibility
TOOL_DEFINITION = GetPlayerStats.TOOL_DEFINITION
get_player_stats = GetPlayerStats.run


def main():
    """
    Test function to run the tool standalone.
    """
    print("Testing get_player_stats tool...\n")

    # Test with player IDs (you'd need real NHL player IDs)
    result = get_player_stats(player_ids=[8478402, 8477934])  # Example IDs

    if result["success"]:
        print(f"✓ {result['summary']}\n")

        for player in result["players"]:
            print(f"{player['name']} ({player['team']}):")
            print(f"  Position: {player['position']}")
            print(f"  Fantasy PPG: {player['fantasy_ppg']}")
            print(f"  Tier: {player['tier']}")
            print(f"  Droppable: {player['droppable']}")
            print()
    else:
        print(f"✗ Error: {result['error']}")


if __name__ == "__main__":
    main()
