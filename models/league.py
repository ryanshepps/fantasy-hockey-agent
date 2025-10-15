"""League context data models."""

from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class LeagueContext(BaseModel):
    """League information and context."""

    league_id: str | None = Field(
        default=None,
        description="Yahoo league ID",
    )
    league_key: str | None = Field(
        default=None,
        description="Yahoo league key (includes season and game code)",
    )
    league_name: str | None = Field(
        default=None,
        description="Human-readable league name",
    )
    season: str | None = Field(
        default=None,
        description="Season year (e.g., '2024')",
    )
    current_week: int | None = Field(
        default=None,
        description="Current fantasy week number",
        ge=1,
    )
    game_code: str | None = Field(
        default=None,
        description="Yahoo game code (e.g., 'nhl')",
    )

    @field_validator("season", mode="before")
    @classmethod
    def convert_season_to_string(cls, v):
        """Convert season to string if it's an integer."""
        if v is not None and not isinstance(v, str):
            return str(v)
        return v

    class Config:
        json_schema_extra: ClassVar = {
            "example": {
                "league_id": "12345",
                "league_key": "nhl.l.12345",
                "league_name": "Fantasy Hockey League 2024",
                "season": "2024",
                "current_week": 3,
                "game_code": "nhl",
            }
        }
