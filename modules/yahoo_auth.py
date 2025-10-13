#!/usr/bin/env python3
"""
Yahoo OAuth token management with better error handling for CI/CD environments.

This module provides robust token management including:
- JSON-based token storage (cleaner than individual env vars)
- Automatic token refresh with error handling
- Clear error messages when re-authentication is needed
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery

# Handle imports for both direct execution and module import
try:
    from modules.logger import AgentLogger
except ModuleNotFoundError:
    # Add parent directory to path when running as a script
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.logger import AgentLogger

load_dotenv()

# Initialize logger for this module
logger = AgentLogger.get_logger(__name__)


def get_yahoo_query(
    league_id: str | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token_json: str | None = None,
) -> YahooFantasySportsQuery:
    """
    Initialize Yahoo Fantasy Sports Query with robust token handling.

    Args:
        league_id: Yahoo Fantasy League ID (defaults to env var)
        consumer_key: Yahoo OAuth consumer key (defaults to env var)
        consumer_secret: Yahoo OAuth consumer secret (defaults to env var)
        access_token_json: JSON string containing all token data (defaults to env var)

    Returns:
        Configured YahooFantasySportsQuery object

    Raises:
        ValueError: If required credentials are missing
        RuntimeError: If token refresh fails
    """
    logger.info("Initializing Yahoo Fantasy Sports Query")

    league_id = league_id or os.getenv("LEAGUE_ID")
    consumer_key = consumer_key or os.getenv("YAHOO_CLIENT_ID")
    consumer_secret = consumer_secret or os.getenv("YAHOO_CLIENT_SECRET")

    if not all([league_id, consumer_key, consumer_secret]):
        missing = []
        if not league_id:
            missing.append("LEAGUE_ID")
        if not consumer_key:
            missing.append("YAHOO_CLIENT_ID")
        if not consumer_secret:
            missing.append("YAHOO_CLIENT_SECRET")
        logger.error(f"Missing required credentials: {', '.join(missing)}")
        raise ValueError(f"Missing required credentials: {', '.join(missing)}")

    access_token_json = access_token_json or os.getenv("YAHOO_ACCESS_TOKEN_JSON")

    if access_token_json:
        try:
            token_data = json.loads(access_token_json.strip())

            if token_data.get("token_time"):
                token_age_hours = (datetime.now().timestamp() - token_data["token_time"]) / 3600
                if token_age_hours > 1:
                    logger.info(
                        f"Access token expired ({token_age_hours:.1f}h old, will auto-refresh)"
                    )

            return _create_query_with_token(league_id, consumer_key, consumer_secret, token_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid YAHOO_ACCESS_TOKEN_JSON format: {e}")
            logger.error(f"JSON parse error at position {e.pos}")
            logger.error("Common causes:")
            logger.error("  - Newlines in GitHub secret (must be single-line JSON)")
            logger.error("  - Missing quotes around the secret value in .env file")
            logger.error("  - Special characters not properly escaped")

    access_token = os.getenv("YAHOO_ACCESS_TOKEN")
    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
    token_time = os.getenv("YAHOO_TOKEN_TIME")
    token_type = os.getenv("YAHOO_TOKEN_TYPE", "bearer")

    if access_token and refresh_token:
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_time": float(token_time) if token_time else None,
            "token_type": token_type,
        }
        return _create_query_with_token(league_id, consumer_key, consumer_secret, token_data)

    logger.warning(
        "No token data found - starting OAuth flow (requires interactive authentication)"
    )
    logger.info("To authenticate for CI/CD:")
    logger.info("  1. Run locally: python fantasy_hockey_agent.py --dry-run")
    logger.info("  2. Complete OAuth flow in browser")
    logger.info("  3. Export tokens: python modules/yahoo_auth.py export")
    logger.info("  4. Add YAHOO_ACCESS_TOKEN_JSON to GitHub secrets")

    return YahooFantasySportsQuery(
        league_id=league_id,
        game_code="nhl",
        game_id=None,
        yahoo_consumer_key=consumer_key,
        yahoo_consumer_secret=consumer_secret,
        env_file_location=Path("."),
        save_token_data_to_env_file=True,
    )


def _create_query_with_token(
    league_id: str, consumer_key: str, consumer_secret: str, token_data: dict
) -> YahooFantasySportsQuery:
    """
    Create YahooFantasySportsQuery with existing token data.

    Args:
        league_id: Yahoo Fantasy League ID
        consumer_key: Yahoo OAuth consumer key
        consumer_secret: Yahoo OAuth consumer secret
        token_data: Dictionary containing token information

    Returns:
        Configured YahooFantasySportsQuery object
    """
    try:
        full_token_data = {
            **token_data,
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
            "guid": None,
        }

        return YahooFantasySportsQuery(
            league_id=league_id,
            game_code="nhl",
            game_id=None,
            yahoo_consumer_key=consumer_key,
            yahoo_consumer_secret=consumer_secret,
            yahoo_access_token_json=full_token_data,
            env_file_location=Path("."),
            save_token_data_to_env_file=True,
        )
    except Exception as e:
        logger.error(f"Failed to create Yahoo query: {e}")
        logger.error(
            "Token may be expired or invalid. Re-authenticate locally and update GitHub secrets."
        )
        raise


def export_tokens_to_json() -> str | None:
    """
    Export current token data from .env to JSON format for GitHub secrets.

    Returns:
        JSON string containing all token data, or None if tokens not found
    """
    load_dotenv()

    access_token = os.getenv("YAHOO_ACCESS_TOKEN")
    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
    token_time = os.getenv("YAHOO_TOKEN_TIME")
    token_type = os.getenv("YAHOO_TOKEN_TYPE", "bearer")

    if not access_token or not refresh_token:
        logger.error("Token data not found in .env file")
        logger.error("Run: python fantasy_hockey_agent.py --dry-run")
        return None

    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_time": float(token_time) if token_time else None,
        "token_type": token_type,
    }

    json_str = json.dumps(token_data)

    print("\n" + "=" * 80)
    print("GitHub Secret: YAHOO_ACCESS_TOKEN_JSON")
    print("=" * 80)
    print(json_str)
    print("=" * 80)
    print("\nSteps:")
    print("1. Copy the JSON above")
    print("2. GitHub → Settings → Secrets → New repository secret")
    print("3. Name: YAHOO_ACCESS_TOKEN_JSON")
    print("4. Value: Paste the JSON")
    print("=" * 80)

    return json_str


def check_token_health() -> dict:
    """
    Check the health of current OAuth tokens.

    Returns:
        Dictionary with token status information
    """
    load_dotenv()

    access_token = os.getenv("YAHOO_ACCESS_TOKEN")
    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
    token_time_str = os.getenv("YAHOO_TOKEN_TIME")

    if not access_token or not refresh_token:
        return {
            "status": "missing",
            "message": "No token data found",
            "needs_reauth": True,
        }

    token_time = float(token_time_str) if token_time_str else 0
    token_age_hours = (datetime.now().timestamp() - token_time) / 3600

    if token_age_hours > 1:
        return {
            "status": "expired",
            "message": f"Token expired {token_age_hours:.1f}h ago (will auto-refresh)",
            "needs_reauth": False,
            "token_age_hours": token_age_hours,
            "has_refresh_token": True,
        }

    return {
        "status": "valid",
        "message": f"Token valid (expires in {1 - token_age_hours:.1f}h)",
        "needs_reauth": False,
        "token_age_hours": token_age_hours,
        "has_refresh_token": True,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "export":
        # Export tokens to JSON format
        export_tokens_to_json()
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        # Check token health
        health = check_token_health()
        print("\n" + "=" * 80)
        print("Token Health Check")
        print("=" * 80)
        print(f"Status: {health['status']}")
        print(f"Message: {health['message']}")
        print(f"Has refresh token: {health['has_refresh_token']}")
        if "token_age_hours" in health:
            print(f"Token age: {health['token_age_hours']:.1f} hours")
        print("=" * 80)
    else:
        print("Usage:")
        print("  python tools/yahoo_auth.py export  # Export tokens to JSON")
        print("  python tools/yahoo_auth.py check   # Check token health")
