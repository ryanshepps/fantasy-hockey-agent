import pytest
from agents.historical_analyst_agent import HistoricalAnalystAgent
from indexing.vector_store_manager import VectorStoreManager


def test_historical_analyst_agent_creation():
    """Test that HistoricalAnalystAgent can be created."""
    manager = VectorStoreManager(persist_dir="./test_data/vector_db")
    agent = HistoricalAnalystAgent(vector_manager=manager)

    assert agent is not None
    assert agent.agent is not None
