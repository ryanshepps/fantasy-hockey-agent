#!/usr/bin/env python3
"""
Tool to calculate optimal player streaming strategy to maximize games played.

This tool analyzes your roster, available players, and team schedules to determine
the exact drop/pickup timing that maximizes total games played over a 2-week period.

For example: "Drop Frank Vatrano on Oct 15 (after 3 games played) and pick up
Alex Lafreniere (who will play 4 more games after that date) = 7 total games vs
keeping Vatrano = only 4 total games"

Example Usage:
    from tools.calculate_optimal_streaming import calculate_optimal_streaming

    result = calculate_optimal_streaming(
        roster_data=roster_data,
        available_players=available_players,
        team_schedule=team_schedule
    )
"""

import json
import sys
from datetime import datetime
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


def _parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def _normalize_team_abbr(abbr: str) -> str:
    """
    Normalize team abbreviations to match schedule data format.

    Args:
        abbr: Team abbreviation (may be short form like 'TB')

    Returns:
        Normalized abbreviation matching schedule data (like 'TBL')
    """
    # Mapping from Yahoo/short forms to NHL API forms
    abbr_map = {
        "TB": "TBL",  # Tampa Bay
        "NJ": "NJD",  # New Jersey
        "SJ": "SJS",  # San Jose
        "LA": "LAK",  # Los Angeles
    }
    return abbr_map.get(abbr, abbr)


def _get_player_team_abbr(player: dict) -> str | None:
    """
    Extract team abbreviation from player data.

    Args:
        player: Player dictionary from roster or available players

    Returns:
        Normalized team abbreviation or None
    """
    # Try different possible fields
    team = (
        player.get("nhl_team")
        or player.get("team")
        or player.get("editorial_team_abbr")
        or player.get("team_abbr")
    )
    if isinstance(team, dict):
        team = team.get("abbreviation") or team.get("abbr")

    # Normalize the abbreviation to match schedule data
    return _normalize_team_abbr(team) if team else None


def _calculate_games_for_player(
    player: dict,
    team_schedule: dict,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """
    Get list of games for a specific player based on their team's schedule.

    Args:
        player: Player dictionary with team information
        team_schedule: Schedule data from get_team_schedule tool
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        List of game dictionaries with dates
    """
    team_abbr = _get_player_team_abbr(player)
    if not team_abbr:
        logger.warning(f"Could not determine team for player: {player.get('name')}")
        return []

    # Find team in schedule data
    team_data = None
    for team in team_schedule.get("teams", []):
        if team["abbr"] == team_abbr:
            team_data = team
            break

    if not team_data:
        logger.warning(f"Team {team_abbr} not found in schedule data")
        return []

    games = team_data.get("games", [])

    # Filter by date range if provided
    if start_date or end_date:
        filtered_games = []
        for game in games:
            game_date = game["date"]
            if start_date and game_date < start_date:
                continue
            if end_date and game_date > end_date:
                continue
            filtered_games.append(game)
        games = filtered_games

    return games


def _calculate_streaming_opportunity(
    drop_candidate: dict,
    pickup_candidate: dict,
    team_schedule: dict,
    schedule_start: str,
    schedule_end: str,
) -> dict | None:
    """
    Calculate the optimal drop/pickup timing for a pair of players.

    Args:
        drop_candidate: Player currently on roster
        pickup_candidate: Available free agent
        team_schedule: Schedule data
        schedule_start: Start date of schedule period
        schedule_end: End date of schedule period

    Returns:
        Dictionary with streaming recommendation or None if not beneficial
    """
    # Get games for both players over entire period
    drop_games = _calculate_games_for_player(drop_candidate, team_schedule)
    pickup_games = _calculate_games_for_player(pickup_candidate, team_schedule)

    if not drop_games or not pickup_games:
        return None

    drop_total = len(drop_games)
    pickup_total = len(pickup_games)

    # If pickup player doesn't have more games, not worth streaming
    if pickup_total <= drop_total:
        return None

    # Find optimal drop timing
    # Strategy: Keep drop candidate as long as beneficial, then switch
    best_timing = None
    best_total_games = drop_total  # Baseline: keep drop candidate entire time

    # Try each possible drop date (after each drop candidate's game)
    for i, game in enumerate(drop_games):
        drop_date = game["date"]
        games_played_before_drop = i + 1  # Games 0 to i (inclusive)

        # Count pickup candidate's games AFTER drop date
        pickup_games_after_drop = [g for g in pickup_games if g["date"] > drop_date]
        games_after_pickup = len(pickup_games_after_drop)

        total_games = games_played_before_drop + games_after_pickup

        if total_games > best_total_games:
            best_total_games = total_games
            best_timing = {
                "drop_date": drop_date,
                "drop_after_game_num": games_played_before_drop,
                "pickup_games_remaining": games_after_pickup,
                "total_games": total_games,
                "improvement": total_games - drop_total,
                "next_pickup_game": pickup_games_after_drop[0] if pickup_games_after_drop else None,
            }

    # Also consider dropping immediately (before first game)
    pickup_games_all = len(pickup_games)
    if pickup_games_all > best_total_games:
        best_total_games = pickup_games_all
        best_timing = {
            "drop_date": schedule_start,  # Drop immediately
            "drop_after_game_num": 0,
            "pickup_games_remaining": pickup_games_all,
            "total_games": pickup_games_all,
            "improvement": pickup_games_all - drop_total,
            "next_pickup_game": pickup_games[0] if pickup_games else None,
        }

    return best_timing if best_timing else None


def _assess_player_quality(
    player: dict, team_schedule: dict | None = None, current_date: str | None = None
) -> dict:
    """
    Assess player quality to determine if they should be considered droppable.

    Uses fantasy points per game and position to classify players.

    Args:
        player: Player dictionary with stats
        team_schedule: Schedule data to calculate games played
        current_date: Current date string (YYYY-MM-DD) for calculating games played

    Returns:
        Dictionary with quality metrics
    """
    # Extract fantasy points directly from player object
    fantasy_points = player.get("fantasy_points", 0)

    # Calculate games played from team schedule
    games_played = 0
    if team_schedule and current_date:
        team_abbr = _get_player_team_abbr(player)
        if team_abbr:
            for team in team_schedule.get("teams", []):
                if team["abbr"] == team_abbr:
                    # Count games before or on current date
                    for game in team.get("games", []):
                        if game["date"] <= current_date:
                            games_played += 1
                    break

    # If we couldn't calculate games played, estimate 5 (early season default)
    if games_played == 0:
        games_played = 5

    # Calculate per-game metrics
    fantasy_ppg = fantasy_points / games_played if games_played > 0 else 0

    # Tier classification
    position = player.get("selected_position") or player.get("position", "F")

    if position == "G":
        # Goalies - different thresholds
        if fantasy_ppg >= 6.0:
            tier = "Elite"
        elif fantasy_ppg >= 4.5:
            tier = "High-End"
        elif fantasy_ppg >= 3.0:
            tier = "Mid-Tier"
        else:
            tier = "Streamable"
    else:
        # Skaters
        if fantasy_ppg >= 4.5:
            tier = "Elite"
        elif fantasy_ppg >= 3.5:
            tier = "High-End"
        elif fantasy_ppg >= 2.5:
            tier = "Mid-Tier"
        else:
            tier = "Streamable"

    # Only consider streamable/mid-tier players as droppable
    droppable = tier in ["Streamable", "Mid-Tier"]

    return {
        "fantasy_ppg": round(fantasy_ppg, 2),
        "games_played": games_played,
        "tier": tier,
        "droppable": droppable,
    }


def _parse_and_validate_inputs(
    roster_data: dict, available_players: dict, team_schedule: dict
) -> dict:
    """
    Parse and validate input data from various tools.

    Args:
        roster_data: Current roster from get_current_roster tool
        available_players: Available FAs from get_available_players tool
        team_schedule: Schedule data from get_team_schedule tool

    Returns:
        Dictionary with parsed data or error information
    """
    # Parse team_schedule if it's a JSON string
    if isinstance(team_schedule, str):
        try:
            team_schedule = json.loads(team_schedule)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse team_schedule JSON: {e!s}",
            }

    # Validate all inputs have required data
    if (
        not roster_data.get("success")
        or not available_players.get("success")
        or not team_schedule.get("weeks")
    ):
        return {
            "success": False,
            "error": "One or more input tools failed. Check roster_data, available_players, and team_schedule.",
        }

    return {
        "success": True,
        "team_schedule": team_schedule,
        "schedule_start": team_schedule["start_date"],
        "schedule_end": team_schedule["end_date"],
    }


def _build_droppable_candidates(
    roster_data: dict, team_schedule: dict, current_date: str
) -> list[dict]:
    """
    Build list of droppable players from roster based on quality assessment.

    Args:
        roster_data: Current roster data
        team_schedule: Schedule data for games played calculation
        current_date: Current date string (YYYY-MM-DD)

    Returns:
        List of player dictionaries with quality assessments
    """
    drop_candidates = []
    roster_players = roster_data.get("data", {}).get("players", [])

    for player in roster_players:
        # Skip injured/IR players
        if player.get("status") in ["IR", "O", "DTD"]:
            continue

        # Assess player quality
        quality = _assess_player_quality(player, team_schedule, current_date)

        if quality["droppable"]:
            player["quality_assessment"] = quality
            drop_candidates.append(player)
        else:
            logger.info(f"Skipping {player['name']} - tier: {quality['tier']} (not droppable)")

    return drop_candidates


def _build_pickup_candidates(
    available_players: dict, team_schedule: dict, current_date: str
) -> list[dict]:
    """
    Build list of pickup candidates from available players with quality assessment.

    Args:
        available_players: Available free agents data
        team_schedule: Schedule data for games played calculation
        current_date: Current date string (YYYY-MM-DD)

    Returns:
        List of player dictionaries with quality assessments
    """
    pickup_candidates = []
    avail_players = available_players.get("data", {}).get("players", [])

    for player in avail_players:
        quality = _assess_player_quality(player, team_schedule, current_date)
        player["quality_assessment"] = quality
        pickup_candidates.append(player)

    return pickup_candidates


def _positions_are_compatible(drop_position: str, pickup_position: str) -> bool:
    """
    Check if two positions are compatible for streaming (simplified matching).

    Args:
        drop_position: Position of player being dropped
        pickup_position: Position of player being picked up

    Returns:
        True if positions are compatible for streaming
    """
    # Simplified position matching - both must be goalies or both must be non-goalies
    return (drop_position == "G") == (pickup_position == "G")


def _build_opportunity_recommendation(
    drop_player: dict,
    pickup_player: dict,
    timing: dict,
    team_schedule: dict,
) -> dict:
    """
    Build a formatted recommendation from streaming opportunity data.

    Args:
        drop_player: Player being dropped
        pickup_player: Player being picked up
        timing: Timing information from _calculate_streaming_opportunity
        team_schedule: Schedule data for baseline calculation

    Returns:
        Dictionary with formatted recommendation
    """
    # Get baseline (keeping drop player)
    drop_games = _calculate_games_for_player(drop_player, team_schedule)
    baseline_games = len(drop_games)

    # Build reasoning
    if timing["drop_after_game_num"] == 0:
        drop_timing = f"Drop {drop_player['name']} immediately"
    else:
        drop_timing = f"Drop {drop_player['name']} on {timing['drop_date']} (after {timing['drop_after_game_num']} games played)"

    next_game_info = ""
    if timing["next_pickup_game"]:
        next_game_info = f" First game: {timing['next_pickup_game']['date']} vs {timing['next_pickup_game']['opp']}"

    reasoning = (
        f"{drop_timing}, pick up {pickup_player['name']} "
        f"({timing['pickup_games_remaining']} games remaining).{next_game_info} "
        f"Total: {timing['total_games']} games vs {baseline_games} games if kept."
    )

    return {
        "drop_player": drop_player["name"],
        "drop_player_tier": drop_player["quality_assessment"]["tier"],
        "drop_player_fantasy_ppg": drop_player["quality_assessment"]["fantasy_ppg"],
        "pickup_player": pickup_player["name"],
        "pickup_player_tier": pickup_player["quality_assessment"]["tier"],
        "pickup_player_fantasy_ppg": pickup_player["quality_assessment"]["fantasy_ppg"],
        "drop_date": timing["drop_date"],
        "drop_after_games": timing["drop_after_game_num"],
        "pickup_games_remaining": timing["pickup_games_remaining"],
        "total_games": timing["total_games"],
        "improvement": timing["improvement"],
        "baseline_games": baseline_games,
        "next_pickup_game": timing["next_pickup_game"]["date"]
        if timing["next_pickup_game"]
        else None,
        "reasoning": reasoning,
    }


def _find_all_streaming_opportunities(
    drop_candidates: list[dict],
    pickup_candidates: list[dict],
    team_schedule: dict,
    schedule_start: str,
    schedule_end: str,
) -> list[dict]:
    """
    Calculate all streaming opportunities between drop and pickup candidates.

    Args:
        drop_candidates: List of droppable players
        pickup_candidates: List of available pickup players
        team_schedule: Schedule data
        schedule_start: Start date of schedule period
        schedule_end: End date of schedule period

    Returns:
        List of opportunity dictionaries
    """
    opportunities = []

    for drop_player in drop_candidates:
        for pickup_player in pickup_candidates:
            # Check position compatibility
            drop_pos = drop_player.get("selected_position", "F")
            pickup_pos = pickup_player.get("selected_position", "F")

            if not _positions_are_compatible(drop_pos, pickup_pos):
                continue

            # Calculate streaming timing
            timing = _calculate_streaming_opportunity(
                drop_player, pickup_player, team_schedule, schedule_start, schedule_end
            )

            if timing and timing["improvement"] > 0:
                recommendation = _build_opportunity_recommendation(
                    drop_player, pickup_player, timing, team_schedule
                )
                opportunities.append(recommendation)

    return opportunities


def _create_summary_message(
    opportunities: list[dict], drop_candidates_count: int, pickup_candidates_count: int
) -> str:
    """
    Create a human-readable summary of streaming opportunities.

    Args:
        opportunities: List of streaming opportunity recommendations
        drop_candidates_count: Number of droppable players analyzed
        pickup_candidates_count: Number of pickup candidates analyzed

    Returns:
        Summary string
    """
    if opportunities:
        best = opportunities[0]
        return (
            f"Found {len(opportunities)} streaming opportunities to maximize games played.\n"
            f"Best opportunity: {best['reasoning']}\n"
            f"Total droppable players analyzed: {drop_candidates_count}\n"
            f"Total pickup candidates analyzed: {pickup_candidates_count}"
        )
    else:
        return (
            f"No beneficial streaming opportunities found.\n"
            f"Analyzed {drop_candidates_count} droppable players and {pickup_candidates_count} pickup candidates."
        )


class CalculateOptimalStreaming(BaseTool):
    """Tool for calculating optimal player streaming opportunities."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "calculate_optimal_streaming",
        "description": "Calculate optimal player streaming opportunities to maximize total games played over a 2-week period. This tool analyzes your roster, available free agents, and team schedules to recommend EXACT drop/pickup timing. For example: 'Drop Frank Vatrano on Oct 15 after 3 games, pick up Alex Lafreniere who has 4 games remaining = 7 total games vs 4 if you keep Vatrano'. ONLY recommends dropping streamable-tier players (never elite/high-end players). This is the KEY tool for game-maximization strategy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "roster_data": {
                    "type": "object",
                    "description": "Current roster data from get_current_roster tool",
                },
                "available_players": {
                    "type": "object",
                    "description": "Available free agents from get_available_players tool",
                },
                "team_schedule": {
                    "type": "object",
                    "description": "Team schedule data from get_team_schedule tool",
                },
                "max_recommendations": {
                    "type": "integer",
                    "description": "Maximum number of streaming recommendations to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["roster_data", "available_players", "team_schedule"],
        },
    }

    @classmethod
    def run(
        cls,
        roster_data: dict,
        available_players: dict,
        team_schedule: dict,
        max_recommendations: int = 10,
    ) -> dict[str, Any]:
        """
        Calculate optimal player streaming opportunities to maximize games played.

        Analyzes roster vs available free agents and team schedules to find
        drop/pickup combinations that maximize total games played over the
        schedule period.

        IMPORTANT: Only considers "streamable" players (mid-tier or below) as drop
        candidates. Elite players like Cale Makar will never be recommended for
        dropping, even if they have fewer games.

        Args:
            roster_data: Current roster from get_current_roster tool
            available_players: Available FAs from get_available_players tool
            team_schedule: Schedule data from get_team_schedule tool
            max_recommendations: Maximum number of recommendations to return

        Returns:
            Dictionary with structure:
            {
                'success': bool,
                'opportunities': [
                    {
                        'drop_player': str,
                        'drop_player_tier': str,
                        'pickup_player': str,
                        'pickup_player_tier': str,
                        'drop_date': str,  # Exact date to drop
                        'drop_after_games': int,  # Number of games drop player will have played
                        'pickup_games_remaining': int,  # Games pickup will play after drop
                        'total_games': int,  # Total games this strategy yields
                        'improvement': int,  # Extra games vs keeping drop player
                        'baseline_games': int,  # Games if you keep drop player
                        'next_pickup_game': str,  # Date of pickup player's next game
                        'reasoning': str
                    }
                ],
                'summary': str
            }
        """
        try:
            # Parse and validate inputs
            validation_result = _parse_and_validate_inputs(
                roster_data, available_players, team_schedule
            )
            if not validation_result["success"]:
                return validation_result

            team_schedule = validation_result["team_schedule"]
            schedule_start = validation_result["schedule_start"]
            schedule_end = validation_result["schedule_end"]

            logger.info(
                f"Calculating streaming opportunities for {schedule_start} to {schedule_end}"
            )

            # Get current date for games played calculation
            from datetime import datetime

            current_date = datetime.now().strftime("%Y-%m-%d")

            # Build drop and pickup candidate lists
            drop_candidates = _build_droppable_candidates(roster_data, team_schedule, current_date)
            pickup_candidates = _build_pickup_candidates(
                available_players, team_schedule, current_date
            )

            logger.info(
                f"Found {len(drop_candidates)} droppable players and {len(pickup_candidates)} pickup candidates"
            )

            # Find all streaming opportunities
            opportunities = _find_all_streaming_opportunities(
                drop_candidates,
                pickup_candidates,
                team_schedule,
                schedule_start,
                schedule_end,
            )

            # Sort by improvement (descending) and limit results
            opportunities.sort(key=lambda x: (x["improvement"], x["total_games"]), reverse=True)
            opportunities = opportunities[:max_recommendations]

            # Create summary message
            summary = _create_summary_message(
                opportunities, len(drop_candidates), len(pickup_candidates)
            )

            return {
                "success": True,
                "opportunities": opportunities,
                "total_opportunities": len(opportunities),
                "droppable_players_analyzed": len(drop_candidates),
                "pickup_candidates_analyzed": len(pickup_candidates),
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Error calculating streaming opportunities: {e}")
            import traceback

            traceback.print_exc()
            return {
                "success": False,
                "error": f"Failed to calculate streaming opportunities: {e!s}",
            }


# Export for backwards compatibility
TOOL_DEFINITION = CalculateOptimalStreaming.TOOL_DEFINITION
calculate_optimal_streaming = CalculateOptimalStreaming.run


def main():
    """
    Test function to run the tool standalone.
    """
    print("Testing calculate_optimal_streaming tool...\n")
    print("This tool requires actual roster, available players, and schedule data.")
    print("Run the full agent to test this tool in context.\n")


if __name__ == "__main__":
    main()
