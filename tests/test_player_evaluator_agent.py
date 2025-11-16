from agents.player_evaluator_agent import PlayerEvaluatorAgent
from indexing.vector_store_manager import VectorStoreManager


def test_player_evaluator_agent_creation():
    """Test that PlayerEvaluatorAgent can be created."""
    manager = VectorStoreManager(persist_dir="./test_data/vector_db")
    agent = PlayerEvaluatorAgent(vector_manager=manager)

    assert agent is not None
    assert agent.agent is not None
