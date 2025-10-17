#!/usr/bin/env python3
"""Tool to assess which roster players are safe to drop for streaming."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

# Add project root to path for imports when running standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.player import Player, PlayerPosition, PlayerQuality, PlayerTier
from models.roster import Roster
from models.schedule import Schedule
from modules.player_utils import get_player_team_abbr
from tools.base_tool import BaseTool

try:
    from modules.logger import AgentLogger
    logger = AgentLogger.get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


def _assess_player_quality(
    player: Player, schedule: Schedule | None = None, current_date: str | None = None
) -> PlayerQuality:
    """
    Assess player quality to determine if they should be considered droppable.

    Uses fantasy points per game and position to classify players into tiers.

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
        team_abbr = get_player_team_abbr(player)
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


class AssessDroppablePlayers(BaseTool):
    """Tool for assessing which roster players are safe to drop for streaming."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "assess_droppable_players",
        "description": "Analyze roster to identify which players are safe to drop for streaming. Returns players classified as STREAMABLE or MID_TIER (never recommends dropping elite/high-end players like McDavid or Makar). Each player includes quality metrics: fantasy PPG, tier classification, games played. Automatically skips injured/IR players.",
        "input_schema": {
            "type": "object",
            "properties": {
                "roster": {
                    "type": "object",
                    "description": "Current roster model from get_current_roster tool",
                },
                "schedule": {
                    "type": "object",
                    "description": "Schedule model from get_team_schedule tool (used to calculate games played)",
                },
            },
            "required": ["roster", "schedule"],
        },
    }

    @classmethod
    def run(cls, roster: Roster, schedule: Schedule) -> list[Player]:
        """
        Assess which roster players are droppable for streaming.

        Analyzes each roster player's fantasy PPG and classifies them into tiers.
        Only returns STREAMABLE or MID_TIER players (safe to drop). Elite and
        high-end players are never returned as droppable.

        Args:
            roster: Current Roster model from get_current_roster tool
            schedule: Schedule model from get_team_schedule tool

        Returns:
            List of Player models with quality_assessment populated, filtered to
            only droppable players (STREAMABLE or MID_TIER tier)

        Raises:
            Exception: If assessment fails
        """
        drop_candidates = []
        current_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Assessing roster players for droppability (current date: {current_date})")

        for player in roster.players:
            # Skip injured/IR players
            if player.is_injured or player.is_on_ir():
                logger.info(f"Skipping {player.name} - injured or on IR")
                continue

            # Assess player quality
            quality = _assess_player_quality(player, schedule, current_date)

            if quality.droppable:
                # Add quality assessment to player
                player.quality_assessment = quality
                drop_candidates.append(player)
                logger.info(
                    f"Droppable: {player.name} - {quality.tier.value} "
                    f"({quality.fantasy_ppg} PPG in {quality.games_played} GP)"
                )
            else:
                logger.info(
                    f"Keep: {player.name} - {quality.tier.value} "
                    f"({quality.fantasy_ppg} PPG) - NOT droppable"
                )

        logger.info(f"Found {len(drop_candidates)} droppable players out of {len(roster.players)} total")

        return drop_candidates


TOOL_DEFINITION = AssessDroppablePlayers.TOOL_DEFINITION
assess_droppable_players = AssessDroppablePlayers.run


def main():
    """Test function to run the tool standalone."""
    print("Testing assess_droppable_players tool...\n")
    print("This tool requires actual roster and schedule data.")
    print("Run the full agent or integration tests to test this tool in context.\n")


if __name__ == "__main__":
    main()
