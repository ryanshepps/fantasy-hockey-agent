"""Game and schedule data models."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Game(BaseModel):
    """Represents a single NHL game."""

    date: str = Field(
        description="Game date in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    opponent: str = Field(description="Opponent team abbreviation (e.g., 'TOR', 'EDM')")
    is_home: bool = Field(description="True if this is a home game, False if away")

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Ensure date is in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError as e:
            raise ValueError(f"Date must be in YYYY-MM-DD format: {v}") from e

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-10-15",
                "opponent": "TOR",
                "is_home": True,
            }
        }

    def __str__(self) -> str:
        """Human-readable game description."""
        location = "vs" if self.is_home else "@"
        return f"{self.date} {location} {self.opponent}"
