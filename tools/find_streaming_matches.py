#!/usr/bin/env python3
"""
Tool to calculate optimal drop/pickup timing to maximize games played.

This tool takes pre-assessed droppable players and available free agents,
then calculates the exact drop/pickup timing that maximizes total games.
"""

import sys
from pathlib import Path
from typing import Any, ClassVar

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.player import Player
from models.schedule import Schedule
from models.streaming import StreamingOpportunity, StreamingRecommendation
from modules.player_utils import positions_are_compatible
from modules.schedule_utils import calculate_games_for_player
from tools.base_tool import BaseTool

try:
    from modules.logger import AgentLogger
    logger = AgentLogger.get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


def _calculate_streaming_opportunity(
    drop_candidate: Player,
    pickup_candidate: Player,
    schedule: Schedule,
    schedule_start: str,
    schedule_end: str,
) -> dict | None:
    """
    Calculate the optimal drop/pickup timing for a pair of players.

    Args:
        drop_candidate: Player currently on roster
        pickup_candidate: Available free agent
        schedule: Schedule model
        schedule_start: Start date of schedule period
        schedule_end: End date of schedule period

    Returns:
        Dictionary with timing info or None if not beneficial
    """
    # Get games for both players over entire period
    drop_games = calculate_games_for_player(drop_candidate, schedule)
    pickup_games = calculate_games_for_player(pickup_candidate, schedule)

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
        drop_date = game.date
        games_played_before_drop = i + 1  # Games 0 to i (inclusive)

        # Count pickup candidate's games AFTER drop date
        pickup_games_after_drop = [g for g in pickup_games if g.date > drop_date]
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


def _build_opportunity_recommendation(
    drop_player: Player,
    pickup_player: Player,
    timing: dict,
    schedule: Schedule,
) -> StreamingOpportunity:
    """
    Build a formatted recommendation from streaming opportunity data.

    Args:
        drop_player: Player being dropped
        pickup_player: Player being picked up
        timing: Timing information from _calculate_streaming_opportunity
        schedule: Schedule model for baseline calculation

    Returns:
        StreamingOpportunity model
    """
    # Get baseline (keeping drop player)
    drop_games = calculate_games_for_player(drop_player, schedule)
    baseline_games = len(drop_games)

    # Build reasoning
    if timing["drop_after_game_num"] == 0:
        drop_timing = f"Drop {drop_player.name} immediately"
    else:
        drop_timing = f"Drop {drop_player.name} on {timing['drop_date']} (after {timing['drop_after_game_num']} games played)"

    next_game_info = ""
    next_game_date = None
    if timing["next_pickup_game"]:
        next_game = timing["next_pickup_game"]
        next_game_date = next_game.date
        next_game_info = f" First game: {next_game.date} vs {next_game.opponent}"

    reasoning = (
        f"{drop_timing}, pick up {pickup_player.name} "
        f"({timing['pickup_games_remaining']} games remaining).{next_game_info} "
        f"Total: {timing['total_games']} games vs {baseline_games} games if kept."
    )

    return StreamingOpportunity(
        drop_player=drop_player,
        pickup_player=pickup_player,
        drop_date=timing["drop_date"],
        drop_after_games=timing["drop_after_game_num"],
        pickup_games_remaining=timing["pickup_games_remaining"],
        total_games=timing["total_games"],
        improvement=timing["improvement"],
        baseline_games=baseline_games,
        next_pickup_game=next_game_date,
        reasoning=reasoning,
    )


def _find_all_streaming_opportunities(
    drop_candidates: list[Player],
    pickup_candidates: list[Player],
    schedule: Schedule,
    schedule_start: str,
    schedule_end: str,
) -> list[StreamingOpportunity]:
    """
    Calculate all streaming opportunities between drop and pickup candidates.

    Args:
        drop_candidates: List of droppable Player models
        pickup_candidates: List of available pickup Player models
        schedule: Schedule model
        schedule_start: Start date of schedule period
        schedule_end: End date of schedule period

    Returns:
        List of StreamingOpportunity models
    """
    opportunities = []

    for drop_player in drop_candidates:
        for pickup_player in pickup_candidates:
            # Check position compatibility
            if not positions_are_compatible(drop_player.position, pickup_player.position):
                continue

            # Calculate streaming timing
            timing = _calculate_streaming_opportunity(
                drop_player, pickup_player, schedule, schedule_start, schedule_end
            )

            if timing and timing["improvement"] > 0:
                recommendation = _build_opportunity_recommendation(
                    drop_player, pickup_player, timing, schedule
                )
                opportunities.append(recommendation)

    return opportunities


def _create_summary_message(
    opportunities: list[StreamingOpportunity],
    drop_candidates_count: int,
    pickup_candidates_count: int,
) -> str:
    """
    Create a human-readable summary of streaming opportunities.

    Args:
        opportunities: List of StreamingOpportunity models
        drop_candidates_count: Number of droppable players analyzed
        pickup_candidates_count: Number of pickup candidates analyzed

    Returns:
        Summary string
    """
    if opportunities:
        best = opportunities[0]
        return (
            f"Found {len(opportunities)} streaming opportunities to maximize games played.\n"
            f"Best opportunity: {best.reasoning}\n"
            f"Total droppable players analyzed: {drop_candidates_count}\n"
            f"Total pickup candidates analyzed: {pickup_candidates_count}"
        )
    else:
        return (
            f"No beneficial streaming opportunities found.\n"
            f"Analyzed {drop_candidates_count} droppable players and {pickup_candidates_count} pickup candidates."
        )


class FindStreamingMatches(BaseTool):
    """Tool for calculating optimal drop/pickup timing to maximize games played."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "find_streaming_matches",
        "description": "Calculate optimal drop/pickup timing to maximize games played. For each droppable player and available free agent, determines exact date to drop/pickup and total games gained. Returns recommendations sorted by improvement. Example output: 'Drop Vatrano on Oct 15 after 3 games, pickup Lafreniere with 4 games remaining = +3 games total'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "droppable_players": {
                    "type": "array",
                    "description": "List of droppable Player models from assess_droppable_players tool",
                    "items": {"type": "object"},
                },
                "available_players": {
                    "type": "array",
                    "description": "List of available free agent Player models from get_players_from_teams tool",
                    "items": {"type": "object"},
                },
                "schedule": {
                    "type": "object",
                    "description": "Schedule model from get_team_schedule tool",
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Maximum number of streaming recommendations to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["droppable_players", "available_players", "schedule"],
        },
    }

    @classmethod
    def run(
        cls,
        droppable_players: list[Player],
        available_players: list[Player],
        schedule: Schedule,
        max_matches: int = 10,
    ) -> StreamingRecommendation:
        """
        Calculate optimal streaming matches to maximize games played.

        Takes pre-assessed droppable players and available free agents, then
        calculates the exact drop/pickup timing that maximizes total games.

        Args:
            droppable_players: List of droppable Player models from assess_droppable_players
            available_players: List of Player models from get_players_from_teams
            schedule: Schedule model from get_team_schedule tool
            max_matches: Maximum number of recommendations to return

        Returns:
            StreamingRecommendation model with opportunities and analysis

        Raises:
            Exception: If streaming calculation fails
        """
        schedule_start = schedule.start_date
        schedule_end = schedule.end_date

        logger.info(
            f"Calculating streaming matches for {schedule_start} to {schedule_end} "
            f"({len(droppable_players)} droppable, {len(available_players)} available)"
        )

        # Find all streaming opportunities
        opportunities = _find_all_streaming_opportunities(
            droppable_players,
            available_players,
            schedule,
            schedule_start,
            schedule_end,
        )

        # Sort by improvement (descending) and limit results
        opportunities.sort(key=lambda x: (x.improvement, x.total_games), reverse=True)
        opportunities = opportunities[:max_matches]

        # Create summary message
        summary = _create_summary_message(
            opportunities, len(droppable_players), len(available_players)
        )

        logger.info(f"Found {len(opportunities)} streaming opportunities")

        # Return validated StreamingRecommendation model
        return StreamingRecommendation(
            opportunities=opportunities,
            total_opportunities=len(opportunities),
            droppable_players_analyzed=len(droppable_players),
            pickup_candidates_analyzed=len(available_players),
            summary=summary,
        )


def main():
    """Test function to run the tool standalone."""
    print("Testing find_streaming_matches tool...\n")
    print("This tool requires droppable players, available players, and schedule data.")
    print("Run the full agent to test this tool in context.\n")


if __name__ == "__main__":
    main()
