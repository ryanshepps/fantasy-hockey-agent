"""Manages ChromaDB vector store for LlamaIndex."""

import logging
import os
from typing import Any

import chromadb
from chromadb.config import Settings
from llama_index.vector_stores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages ChromaDB collections for fantasy hockey agent."""

    def __init__(self, persist_dir: str = "./data/vector_db"):
        """
        Initialize ChromaDB client.

        Args:
            persist_dir: Directory to persist vector database
        """
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        logger.info(f"Initialized ChromaDB at {persist_dir}")

    def get_collection(self, name: str) -> Any:
        """
        Get or create a ChromaDB collection.

        Args:
            name: Collection name

        Returns:
            ChromaDB collection
        """
        try:
            collection = self.client.get_or_create_collection(name)
            logger.info(f"Retrieved collection: {name}")
            return collection
        except Exception as e:
            logger.error(f"Failed to get collection {name}: {e}")
            raise

    def get_vector_store(self, collection_name: str) -> ChromaVectorStore:
        """
        Create LlamaIndex ChromaVectorStore wrapper.

        Args:
            collection_name: Name of the collection

        Returns:
            ChromaVectorStore instance
        """
        collection = self.get_collection(collection_name)
        return ChromaVectorStore(chroma_collection=collection)

    def reset_collection(self, name: str) -> None:
        """
        Delete and recreate a collection (useful for testing).

        Args:
            name: Collection name
        """
        try:
            self.client.delete_collection(name)
            logger.info(f"Reset collection: {name}")
        except Exception:
            pass  # Collection might not exist

    def list_collections(self) -> list[str]:
        """List all collection names."""
        collections = self.client.list_collections()
        return [c.name for c in collections]
