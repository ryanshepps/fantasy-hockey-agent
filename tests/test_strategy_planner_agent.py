import pytest
from agents.strategy_planner_agent import StrategyPlannerAgent
from indexing.vector_store_manager import VectorStoreManager


def test_strategy_planner_agent_creation():
    """Test that StrategyPlannerAgent can be created."""
    manager = VectorStoreManager(persist_dir="./test_data/vector_db")
    agent = StrategyPlannerAgent(vector_manager=manager)

    assert agent is not None
    assert agent.agent is not None
