"""Integration test for LlamaIndex multi-agent system."""

import asyncio
import os
import tempfile

import pytest
from agents.master_orchestrator import MasterOrchestrator
from indexing.data_ingestion import DataIngestionPipeline
from indexing.vector_store_manager import VectorStoreManager


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"),
    reason="Requires API keys",
)
@pytest.mark.asyncio
async def test_full_llamaindex_workflow():
    """Test complete workflow: ingestion -> orchestration -> recommendation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        manager = VectorStoreManager(persist_dir=tmpdir)
        pipeline = DataIngestionPipeline(
            vector_manager=manager,
            recommendations_path="recommendations_history.json",
        )
        pipeline.setup_indexes()

        # Create orchestrator
        orchestrator = MasterOrchestrator(
            vector_manager=manager,
            dry_run=True,  # Don't actually send email
        )

        # Run simple query
        response = await orchestrator.run(
            "What are the key principles for evaluating droppable players?"
        )

        # Verify response exists
        assert response is not None
        assert len(response) > 0
        assert isinstance(response, str)
