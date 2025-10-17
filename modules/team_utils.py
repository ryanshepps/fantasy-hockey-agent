#!/usr/bin/env python3
"""Utilities for NHL team abbreviation handling."""


def normalize_team_abbr(abbr: str) -> str:
    """
    Normalize team abbreviations to match NHL API format.

    Yahoo Fantasy uses short forms (TB, NJ, SJ, LA) while NHL API uses
    full forms (TBL, NJD, SJS, LAK). This function converts between them.

    Args:
        abbr: Team abbreviation (may be Yahoo short form like 'TB')

    Returns:
        Normalized abbreviation matching NHL API format (like 'TBL')

    Examples:
        >>> normalize_team_abbr('TB')
        'TBL'
        >>> normalize_team_abbr('TBL')
        'TBL'
        >>> normalize_team_abbr('EDM')
        'EDM'
    """
    # Mapping from Yahoo/short forms to NHL API forms
    abbr_map = {
        "TB": "TBL",  # Tampa Bay Lightning
        "NJ": "NJD",  # New Jersey Devils
        "SJ": "SJS",  # San Jose Sharks
        "LA": "LAK",  # Los Angeles Kings
    }
    return abbr_map.get(abbr, abbr)
