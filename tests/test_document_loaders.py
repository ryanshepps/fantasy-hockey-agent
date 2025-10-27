import json
import tempfile
from pathlib import Path

import pytest
from indexing.document_loaders import RecommendationHistoryLoader
from llama_index.core import Document


def test_recommendation_history_loader():
    """Test loading recommendations_history.json into LlamaIndex documents."""
    # Create temp JSON file
    test_data = {
        "recommendations": [
            {
                "date": "2025-10-20",
                "pickups": ["Player A"],
                "drops": ["Player B"],
                "reasoning": "Player A has better schedule"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f)
        temp_path = f.name

    try:
        loader = RecommendationHistoryLoader(temp_path)
        documents = loader.load()

        assert len(documents) > 0
        assert isinstance(documents[0], Document)
        assert "Player A" in documents[0].text
        assert "2025-10-20" in documents[0].text
    finally:
        Path(temp_path).unlink()
