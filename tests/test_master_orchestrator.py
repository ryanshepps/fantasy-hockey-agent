from agents.master_orchestrator import MasterOrchestrator
from indexing.vector_store_manager import VectorStoreManager


def test_master_orchestrator_creation():
    """Test that MasterOrchestrator can be created."""
    manager = VectorStoreManager(persist_dir="./test_data/vector_db")
    orchestrator = MasterOrchestrator(vector_manager=manager)

    assert orchestrator is not None
    assert orchestrator.agent is not None
