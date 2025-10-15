"""Streaming opportunity data models."""

from typing import ClassVar

from pydantic import BaseModel, Field

from models.player import Player


class StreamingOpportunity(BaseModel):
    """Represents a single drop/pickup streaming opportunity."""

    drop_player: Player = Field(
        description="Player to drop from roster",
    )
    pickup_player: Player = Field(
        description="Player to pick up from free agents",
    )
    drop_date: str = Field(
        description="Date to drop player (YYYY-MM-DD format)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    drop_after_games: int = Field(
        description="Number of games drop player will have played before drop",
        ge=0,
    )
    pickup_games_remaining: int = Field(
        description="Number of games pickup player will play after pickup",
        ge=0,
    )
    total_games: int = Field(
        description="Total games this streaming strategy yields",
        ge=0,
    )
    improvement: int = Field(
        description="Extra games gained vs keeping drop player",
        ge=0,
    )
    baseline_games: int = Field(
        description="Games if you keep drop player entire period",
        ge=0,
    )
    next_pickup_game: str | None = Field(
        default=None,
        description="Date of pickup player's next game (YYYY-MM-DD format)",
    )
    reasoning: str = Field(
        description="Human-readable explanation of the streaming opportunity",
    )

    class Config:
        json_schema_extra: ClassVar = {
            "example": {
                "drop_player": {
                    "name": "Frank Vatrano",
                    "position": "RW",
                    "nhl_team": "ANA",
                    "fantasy_points": 12.5,
                    "quality_assessment": {
                        "fantasy_ppg": 2.1,
                        "tier": "Streamable",
                        "droppable": True,
                    },
                },
                "pickup_player": {
                    "name": "Alex Lafreniere",
                    "position": "LW",
                    "nhl_team": "NYR",
                    "fantasy_points": 15.0,
                    "quality_assessment": {
                        "fantasy_ppg": 2.5,
                        "tier": "Mid-Tier",
                        "droppable": False,
                    },
                },
                "drop_date": "2024-10-15",
                "drop_after_games": 3,
                "pickup_games_remaining": 4,
                "total_games": 7,
                "improvement": 3,
                "baseline_games": 4,
                "next_pickup_game": "2024-10-16",
                "reasoning": "Drop Frank Vatrano on 2024-10-15 (after 3 games played), pick up Alex Lafreniere (4 games remaining). First game: 2024-10-16 vs TOR. Total: 7 games vs 4 games if kept.",
            }
        }


class StreamingRecommendation(BaseModel):
    """Complete streaming analysis with multiple opportunities."""

    opportunities: list[StreamingOpportunity] = Field(
        description="All beneficial streaming opportunities found",
        default_factory=list,
    )
    total_opportunities: int = Field(
        description="Total number of opportunities found",
        ge=0,
    )
    droppable_players_analyzed: int = Field(
        description="Number of droppable players analyzed",
        ge=0,
    )
    pickup_candidates_analyzed: int = Field(
        description="Number of pickup candidates analyzed",
        ge=0,
    )
    summary: str = Field(
        description="Human-readable summary of analysis",
    )

    class Config:
        json_schema_extra: ClassVar = {
            "example": {
                "opportunities": [],
                "total_opportunities": 5,
                "droppable_players_analyzed": 4,
                "pickup_candidates_analyzed": 100,
                "summary": "Found 5 streaming opportunities to maximize games played. Best opportunity: Drop Frank Vatrano on 2024-10-15 (after 3 games), pick up Alex Lafreniere (4 games remaining) = 7 total games vs 4 if kept.",
            }
        }

    def get_best_opportunity(self) -> StreamingOpportunity | None:
        """
        Get the best streaming opportunity (highest improvement).

        Returns:
            Best opportunity if any exist, None otherwise
        """
        if not self.opportunities:
            return None
        return max(self.opportunities, key=lambda o: (o.improvement, o.total_games))

    def get_opportunities_for_player(self, player_name: str) -> list[StreamingOpportunity]:
        """
        Get all opportunities involving a specific player (drop or pickup).

        Args:
            player_name: Name of player to search for (case-insensitive)

        Returns:
            List of opportunities involving this player
        """
        name_lower = player_name.lower()
        return [
            opp
            for opp in self.opportunities
            if name_lower in opp.drop_player.name.lower()
            or name_lower in opp.pickup_player.name.lower()
        ]

    def get_top_opportunities(self, n: int = 5) -> list[StreamingOpportunity]:
        """
        Get top N opportunities by improvement.

        Args:
            n: Number of opportunities to return

        Returns:
            Top N opportunities
        """
        return sorted(
            self.opportunities,
            key=lambda o: (o.improvement, o.total_games),
            reverse=True,
        )[:n]
