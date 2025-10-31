"""Pytest configuration and fixtures."""

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables from .env file for all tests."""
    load_dotenv()
