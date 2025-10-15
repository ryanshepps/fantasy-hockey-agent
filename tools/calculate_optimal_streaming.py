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
        roster=roster,
        available_players=available_players,
        schedule=schedule
    )
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from models.game import Game
from models.player import Player, PlayerPosition, PlayerQuality, PlayerTier
from models.roster import Roster
from models.schedule import Schedule
from models.streaming import StreamingOpportunity, StreamingRecommendation
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


def _get_player_team_abbr(player: Player) -> str | None:
    """
    Extract team abbreviation from player model.

    Args:
        player: Player model

    Returns:
        Normalized team abbreviation or None
    """
    team = player.nhl_team
    return _normalize_team_abbr(team) if team else None


def _calculate_games_for_player(
    player: Player,
    schedule: Schedule,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[Game]:
    """
    Get list of games for a specific player based on their team's schedule.

    Args:
        player: Player model with team information
        schedule: Schedule model from get_team_schedule tool
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        List of Game models
    """
    team_abbr = _get_player_team_abbr(player)
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
    drop_games = _calculate_games_for_player(drop_candidate, schedule)
    pickup_games = _calculate_games_for_player(pickup_candidate, schedule)

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


def _assess_player_quality(
    player: Player, schedule: Schedule | None = None, current_date: str | None = None
) -> PlayerQuality:
    """
    Assess player quality to determine if they should be considered droppable.

    Uses fantasy points per game and position to classify players.

    Args:
        player: Player model with stats
        schedule: Schedule model to calculate games played
        current_date: Current date string (YYYY-MM-DD) for calculating games played

    Returns:
        PlayerQuality model with quality metrics
    """
    # Extract fantasy points from player
    fantasy_points = player.fantasy_points

    # Calculate games played from team schedule
    games_played = 0
    if schedule and current_date:
        team_abbr = _get_player_team_abbr(player)
        if team_abbr:
            team_schedule = schedule.get_team_schedule(team_abbr)
            if team_schedule:
                # Count games before or on current date
                for game in team_schedule.games:
                    if game.date <= current_date:
                        games_played += 1

    # If we couldn't calculate games played, estimate 5 (early season default)
    if games_played == 0:
        games_played = 5

    # Calculate per-game metrics
    fantasy_ppg = fantasy_points / games_played if games_played > 0 else 0

    # Tier classification based on position
    is_goalie = player.position == PlayerPosition.GOALIE

    if is_goalie:
        # Goalies - different thresholds
        if fantasy_ppg >= 6.0:
            tier = PlayerTier.ELITE
        elif fantasy_ppg >= 4.5:
            tier = PlayerTier.HIGH_END
        elif fantasy_ppg >= 3.0:
            tier = PlayerTier.MID_TIER
        else:
            tier = PlayerTier.STREAMABLE
    else:
        # Skaters
        if fantasy_ppg >= 4.5:
            tier = PlayerTier.ELITE
        elif fantasy_ppg >= 3.5:
            tier = PlayerTier.HIGH_END
        elif fantasy_ppg >= 2.5:
            tier = PlayerTier.MID_TIER
        else:
            tier = PlayerTier.STREAMABLE

    # Only consider streamable/mid-tier players as droppable
    droppable = tier in [PlayerTier.STREAMABLE, PlayerTier.MID_TIER]

    return PlayerQuality(
        fantasy_ppg=round(fantasy_ppg, 2),
        games_played=games_played,
        tier=tier,
        droppable=droppable,
    )


def _build_droppable_candidates(
    roster: Roster, schedule: Schedule, current_date: str
) -> list[Player]:
    """
    Build list of droppable players from roster based on quality assessment.

    Args:
        roster: Current roster model
        schedule: Schedule model for games played calculation
        current_date: Current date string (YYYY-MM-DD)

    Returns:
        List of Player models with quality assessments populated
    """
    drop_candidates = []

    for player in roster.players:
        # Skip injured/IR players
        if player.is_injured or player.is_on_ir():
            continue

        # Assess player quality
        quality = _assess_player_quality(player, schedule, current_date)

        if quality.droppable:
            # Add quality assessment to player
            player.quality_assessment = quality
            drop_candidates.append(player)
        else:
            logger.info(f"Skipping {player.name} - tier: {quality.tier.value} (not droppable)")

    return drop_candidates


def _build_pickup_candidates(
    available_players: list[Player], schedule: Schedule, current_date: str
) -> list[Player]:
    """
    Build list of pickup candidates from available players with quality assessment.

    Args:
        available_players: List of available free agent Player models
        schedule: Schedule model for games played calculation
        current_date: Current date string (YYYY-MM-DD)

    Returns:
        List of Player models with quality assessments populated
    """
    pickup_candidates = []

    for player in available_players:
        quality = _assess_player_quality(player, schedule, current_date)
        player.quality_assessment = quality
        pickup_candidates.append(player)

    return pickup_candidates


def _positions_are_compatible(
    drop_position: PlayerPosition | None, pickup_position: PlayerPosition | None
) -> bool:
    """
    Check if two positions are compatible for streaming (simplified matching).

    Args:
        drop_position: Position of player being dropped
        pickup_position: Position of player being picked up

    Returns:
        True if positions are compatible for streaming
    """
    # Simplified position matching - both must be goalies or both must be non-goalies
    if not drop_position or not pickup_position:
        return False
    return (drop_position == PlayerPosition.GOALIE) == (pickup_position == PlayerPosition.GOALIE)


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
    drop_games = _calculate_games_for_player(drop_player, schedule)
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
            if not _positions_are_compatible(drop_player.position, pickup_player.position):
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


class CalculateOptimalStreaming(BaseTool):
    """Tool for calculating optimal player streaming opportunities."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "calculate_optimal_streaming",
        "description": "Calculate optimal player streaming opportunities to maximize total games played over a 2-week period. This tool analyzes your roster, available free agents, and team schedules to recommend EXACT drop/pickup timing. For example: 'Drop Frank Vatrano on Oct 15 after 3 games, pick up Alex Lafreniere who has 4 games remaining = 7 total games vs 4 if you keep Vatrano'. ONLY recommends dropping streamable-tier players (never elite/high-end players). This is the KEY tool for game-maximization strategy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "roster": {
                    "type": "object",
                    "description": "Current roster model from get_current_roster tool",
                },
                "available_players": {
                    "type": "array",
                    "description": "List of available free agent Player models from get_available_players tool",
                    "items": {"type": "object"},
                },
                "schedule": {
                    "type": "object",
                    "description": "Schedule model from get_team_schedule tool",
                },
                "max_recommendations": {
                    "type": "integer",
                    "description": "Maximum number of streaming recommendations to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["roster", "available_players", "schedule"],
        },
    }

    @classmethod
    def run(
        cls,
        roster: Roster,
        available_players: list[Player],
        schedule: Schedule,
        max_recommendations: int = 10,
    ) -> StreamingRecommendation:
        """
        Calculate optimal player streaming opportunities to maximize games played.

        Analyzes roster vs available free agents and team schedules to find
        drop/pickup combinations that maximize total games played over the
        schedule period.

        IMPORTANT: Only considers "streamable" players (mid-tier or below) as drop
        candidates. Elite players like Cale Makar will never be recommended for
        dropping, even if they have fewer games.

        Args:
            roster: Current Roster model from get_current_roster tool
            available_players: List of Player models from get_available_players tool
            schedule: Schedule model from get_team_schedule tool
            max_recommendations: Maximum number of recommendations to return

        Returns:
            StreamingRecommendation model with opportunities and analysis

        Raises:
            Exception: If streaming calculation fails
        """
        schedule_start = schedule.start_date
        schedule_end = schedule.end_date

        logger.info(f"Calculating streaming opportunities for {schedule_start} to {schedule_end}")

        # Get current date for games played calculation
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Build drop and pickup candidate lists
        drop_candidates = _build_droppable_candidates(roster, schedule, current_date)
        pickup_candidates = _build_pickup_candidates(available_players, schedule, current_date)

        logger.info(
            f"Found {len(drop_candidates)} droppable players and {len(pickup_candidates)} pickup candidates"
        )

        # Find all streaming opportunities
        opportunities = _find_all_streaming_opportunities(
            drop_candidates,
            pickup_candidates,
            schedule,
            schedule_start,
            schedule_end,
        )

        # Sort by improvement (descending) and limit results
        opportunities.sort(key=lambda x: (x.improvement, x.total_games), reverse=True)
        opportunities = opportunities[:max_recommendations]

        # Create summary message
        summary = _create_summary_message(
            opportunities, len(drop_candidates), len(pickup_candidates)
        )

        # Return validated StreamingRecommendation model
        return StreamingRecommendation(
            opportunities=opportunities,
            total_opportunities=len(opportunities),
            droppable_players_analyzed=len(drop_candidates),
            pickup_candidates_analyzed=len(pickup_candidates),
            summary=summary,
        )


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
