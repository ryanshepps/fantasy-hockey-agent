"""Schedule data models."""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator

from models.game import Game


class WeekInfo(BaseModel):
    """Information about a fantasy week."""

    week_num: int = Field(description="Week number (1-indexed)", ge=1)
    start: str = Field(
        description="Week start date (Monday) in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    end: str = Field(
        description="Week end date (Sunday) in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )

    @field_validator("start", "end")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Ensure dates are in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError as e:
            raise ValueError(f"Date must be in YYYY-MM-DD format: {v}") from e


class TeamSchedule(BaseModel):
    """Schedule for a single NHL team."""

    abbr: str = Field(
        description="Team abbreviation (e.g., 'TOR', 'EDM')",
        min_length=2,
        max_length=3,
    )
    total_games: int = Field(
        description="Total number of games in the schedule period",
        ge=0,
        alias="total",
    )
    games_by_week: list[int] = Field(
        description="Number of games per fantasy week",
        alias="by_week",
    )
    games: list[Game] = Field(
        description="Detailed list of all games",
        default_factory=list,
    )

    class Config:
        populate_by_name = True
        json_schema_extra: ClassVar = {
            "example": {
                "abbr": "TOR",
                "total": 5,
                "by_week": [3, 2],
                "games": [
                    {"date": "2024-10-14", "opponent": "EDM", "is_home": True},
                    {"date": "2024-10-16", "opponent": "MTL", "is_home": False},
                ],
            }
        }

    def games_in_period(self, start_date: str, end_date: str) -> list[Game]:
        """
        Get games within a specific date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            List of games in the date range
        """
        return [game for game in self.games if start_date <= game.date <= end_date]

    def games_after_date(self, date: str) -> list[Game]:
        """
        Get games after a specific date.

        Args:
            date: Date in YYYY-MM-DD format (exclusive)

        Returns:
            List of games after the date
        """
        return [game for game in self.games if game.date > date]

    def games_count_after_date(self, date: str) -> int:
        """Count how many games are after a specific date."""
        return len(self.games_after_date(date))


class Schedule(BaseModel):
    """Complete schedule data for all NHL teams over a period."""

    weeks: int = Field(
        description="Number of fantasy weeks covered",
        ge=1,
    )
    start_date: str = Field(
        description="Schedule period start date in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    end_date: str = Field(
        description="Schedule period end date in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    week_info: list[WeekInfo] | None = Field(
        default=None,
        description="Detailed information about each fantasy week",
    )
    teams: list[TeamSchedule] = Field(
        description="Schedule for each NHL team",
        default_factory=list,
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Ensure dates are in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError as e:
            raise ValueError(f"Date must be in YYYY-MM-DD format: {v}") from e

    class Config:
        json_schema_extra: ClassVar = {
            "example": {
                "weeks": 2,
                "start_date": "2024-10-14",
                "end_date": "2024-10-27",
                "teams": [
                    {
                        "abbr": "TOR",
                        "total": 5,
                        "by_week": [3, 2],
                        "games": [],
                    }
                ],
            }
        }

    def get_team_schedule(self, team_abbr: str) -> TeamSchedule | None:
        """
        Get schedule for a specific team.

        Args:
            team_abbr: Team abbreviation (e.g., 'TOR', 'EDM')

        Returns:
            TeamSchedule if found, None otherwise
        """
        for team in self.teams:
            if team.abbr == team_abbr:
                return team
        return None

    def teams_sorted_by_games(self) -> list[TeamSchedule]:
        """Get teams sorted by total games (descending)."""
        return sorted(self.teams, key=lambda t: t.total_games, reverse=True)
