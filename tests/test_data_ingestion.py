import json
import tempfile
from pathlib import Path

from indexing.data_ingestion import DataIngestionPipeline
from indexing.vector_store_manager import VectorStoreManager


def test_data_ingestion_creates_indexes():
    """Test that ingestion pipeline creates vector indexes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary recommendations file
        rec_file = Path(tmpdir) / "recommendations.json"
        rec_file.write_text(json.dumps({
            "recommendations": [
                {
                    "date": "2025-10-20",
                    "pickups": ["Player A"],
                    "drops": ["Player B"],
                    "reasoning": "Test recommendation"
                }
            ]
        }))

        manager = VectorStoreManager(persist_dir=tmpdir)
        pipeline = DataIngestionPipeline(
            vector_manager=manager,
            recommendations_path=str(rec_file)
        )

        # Should not raise
        pipeline.setup_indexes()

        # Verify collections exist
        collections = manager.list_collections()
        assert "recommendations_archive" in collections
        assert "league_knowledge" in collections
