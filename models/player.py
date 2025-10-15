"""Player data models."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PlayerPosition(str, Enum):
    """Valid player positions."""

    CENTER = "C"
    LEFT_WING = "LW"
    RIGHT_WING = "RW"
    FORWARD = "F"  # Generic forward
    DEFENSE = "D"
    GOALIE = "G"
    UTILITY = "U"  # Utility slot (any skater)


class PlayerStatus(str, Enum):
    """Player injury/availability status."""

    HEALTHY = "Healthy"
    INJURED = "INJ"
    OUT = "O"
    DAY_TO_DAY = "DTD"
    INJURED_RESERVE = "IR"
    IR_PLUS = "IR+"
    SUSPENDED = "SUSP"
    NOT_ACTIVE = "NA"


class RosterSlot(str, Enum):
    """Roster slot assignments."""

    CENTER = "C"
    LEFT_WING = "LW"
    RIGHT_WING = "RW"
    DEFENSE = "D"
    UTILITY = "U"
    GOALIE = "G"
    BENCH = "BN"
    INJURED_RESERVE = "IR"
    IR_PLUS = "IR+"


class PlayerTier(str, Enum):
    """Player quality tiers based on fantasy performance."""

    ELITE = "Elite"
    HIGH_END = "High-End"
    MID_TIER = "Mid-Tier"
    STREAMABLE = "Streamable"
    DEEP_LEAGUE = "Deep League"


class PlayerQuality(BaseModel):
    """Assessment of player quality and droppability."""

    fantasy_ppg: float = Field(description="Fantasy points per game average", ge=0.0)
    games_played: int = Field(description="Number of games played this season", ge=0)
    tier: PlayerTier = Field(description="Player quality tier")
    droppable: bool = Field(
        description="Whether this player should be considered for streaming (typically Streamable or Deep League tier)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "fantasy_ppg": 3.45,
                "games_played": 12,
                "tier": "Mid-Tier",
                "droppable": True,
            }
        }


class Player(BaseModel):
    """Standardized player representation used across all tools."""

    player_id: str | None = Field(default=None, description="Yahoo or NHL player ID")
    name: str = Field(description="Player's full name")
    position: PlayerPosition | None = Field(default=None, description="Primary position")
    eligible_positions: list[PlayerPosition] = Field(
        default_factory=list,
        description="All positions player is eligible for",
    )
    selected_position: RosterSlot | None = Field(
        default=None,
        description="Current roster slot assignment (for rostered players)",
    )
    nhl_team: str | None = Field(
        default=None,
        description="NHL team abbreviation (e.g., 'TOR', 'EDM')",
    )
    fantasy_points: float = Field(
        default=0.0,
        description="Total fantasy points accumulated this season (can be negative for goalies)",
    )
    status: PlayerStatus = Field(
        default=PlayerStatus.HEALTHY,
        description="Current injury/availability status",
    )
    is_injured: bool = Field(
        default=False,
        description="Quick check if player is injured",
    )
    quality_assessment: PlayerQuality | None = Field(
        default=None,
        description="Quality assessment (populated when needed for drop decisions)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "player_id": "3637",
                "name": "Connor McDavid",
                "position": "C",
                "eligible_positions": ["C", "LW"],
                "selected_position": "C",
                "nhl_team": "EDM",
                "fantasy_points": 45.5,
                "status": "Healthy",
                "is_injured": False,
                "quality_assessment": {
                    "fantasy_ppg": 5.68,
                    "games_played": 8,
                    "tier": "Elite",
                    "droppable": False,
                },
            }
        }

    def is_goalie(self) -> bool:
        """Check if player is a goalie."""
        return self.position == PlayerPosition.GOALIE

    def is_skater(self) -> bool:
        """Check if player is a skater (not a goalie)."""
        return self.position != PlayerPosition.GOALIE

    def is_active(self) -> bool:
        """Check if player is in an active roster slot (not bench/IR)."""
        return self.selected_position not in [
            RosterSlot.BENCH,
            RosterSlot.INJURED_RESERVE,
            RosterSlot.IR_PLUS,
            None,
        ]

    def is_on_ir(self) -> bool:
        """Check if player is on injured reserve."""
        return self.selected_position in [
            RosterSlot.INJURED_RESERVE,
            RosterSlot.IR_PLUS,
        ]
