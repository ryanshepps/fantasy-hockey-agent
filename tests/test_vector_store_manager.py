import pytest
from indexing.vector_store_manager import VectorStoreManager


def test_vector_store_manager_creates_chroma_client():
    """Test that VectorStoreManager initializes ChromaDB client."""
    manager = VectorStoreManager(persist_dir="./test_data/vector_db")
    assert manager.client is not None
    assert manager.persist_dir == "./test_data/vector_db"


def test_vector_store_manager_creates_collection():
    """Test that manager can create/get a collection."""
    manager = VectorStoreManager(persist_dir="./test_data/vector_db")
    collection = manager.get_collection("test_collection")
    assert collection is not None
    assert collection.name == "test_collection"
