"""Roster data models."""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from models.league import LeagueContext
from models.player import Player, PlayerPosition


class RosterCounts(BaseModel):
    """Statistics about roster composition."""

    total: int = Field(description="Total number of players", ge=0)
    forwards: int = Field(
        description="Number of forwards (C, LW, RW, F positions)",
        ge=0,
    )
    defense: int = Field(description="Number of defensemen", ge=0)
    goalies: int = Field(description="Number of goalies", ge=0)
    active: int = Field(
        description="Number of players in active lineup (not bench/IR)",
        ge=0,
    )
    bench: int = Field(description="Number of players on bench", ge=0)
    injured_reserve: int = Field(
        description="Number of players on IR",
        ge=0,
    )

    class Config:
        json_schema_extra: ClassVar = {
            "example": {
                "total": 16,
                "forwards": 9,
                "defense": 5,
                "goalies": 2,
                "active": 13,
                "bench": 2,
                "injured_reserve": 1,
            }
        }


class Roster(BaseModel):
    """Complete roster information for a fantasy team."""

    team_id: str | None = Field(
        default=None,
        description="Fantasy team ID",
    )
    league_context: LeagueContext | None = Field(
        default=None,
        description="League information",
    )
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp when roster was retrieved",
    )
    players: list[Player] = Field(
        description="List of all players on the roster",
        default_factory=list,
    )
    roster_counts: RosterCounts = Field(
        description="Summary statistics about roster composition",
    )

    class Config:
        json_schema_extra: ClassVar = {
            "example": {
                "team_id": "456",
                "league_context": {
                    "league_id": "12345",
                    "league_name": "My League",
                },
                "retrieved_at": "2024-10-13T10:30:00",
                "players": [
                    {
                        "name": "Connor McDavid",
                        "position": "C",
                        "nhl_team": "EDM",
                        "fantasy_points": 45.5,
                    }
                ],
                "roster_counts": {
                    "total": 16,
                    "forwards": 9,
                    "defense": 5,
                    "goalies": 2,
                    "active": 13,
                    "bench": 2,
                    "injured_reserve": 1,
                },
            }
        }

    def get_active_players(self) -> list[Player]:
        """Get all players in active lineup (not bench/IR)."""
        return [p for p in self.players if p.is_active()]

    def get_bench_players(self) -> list[Player]:
        """Get all players on bench."""
        return [p for p in self.players if p.selected_position and "BN" in str(p.selected_position)]

    def get_ir_players(self) -> list[Player]:
        """Get all players on injured reserve."""
        return [p for p in self.players if p.is_on_ir()]

    def get_players_by_position(self, position: PlayerPosition) -> list[Player]:
        """
        Get all players with a specific position.

        Args:
            position: Position to filter by

        Returns:
            List of players with that position
        """
        return [p for p in self.players if p.position == position]

    def get_forwards(self) -> list[Player]:
        """Get all forward players (C, LW, RW, F)."""
        forward_positions = [
            PlayerPosition.CENTER,
            PlayerPosition.LEFT_WING,
            PlayerPosition.RIGHT_WING,
            PlayerPosition.FORWARD,
        ]
        return [p for p in self.players if p.position in forward_positions]

    def get_defensemen(self) -> list[Player]:
        """Get all defensemen."""
        return self.get_players_by_position(PlayerPosition.DEFENSE)

    def get_goalies(self) -> list[Player]:
        """Get all goalies."""
        return self.get_players_by_position(PlayerPosition.GOALIE)

    def get_player_by_name(self, name: str) -> Player | None:
        """
        Find a player by name (case-insensitive).

        Args:
            name: Player name to search for

        Returns:
            Player if found, None otherwise
        """
        name_lower = name.lower()
        for player in self.players:
            if player.name.lower() == name_lower:
                return player
        return None
