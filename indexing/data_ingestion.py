"""Data ingestion pipeline for vector indexes."""

import logging
import os

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding

from indexing.document_loaders import (
    LeagueKnowledgeLoader,
    RecommendationHistoryLoader,
    load_league_knowledge,
)
from indexing.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)


class DataIngestionPipeline:
    """Ingests data into vector stores for RAG."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        recommendations_path: str = "recommendations_history.json",
    ):
        """
        Initialize ingestion pipeline.

        Args:
            vector_manager: VectorStoreManager instance
            recommendations_path: Path to recommendations history JSON
        """
        self.vector_manager = vector_manager
        self.recommendations_path = recommendations_path
        self.embed_model = OpenAIEmbedding(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="text-embedding-3-small",
        )

    def setup_indexes(self) -> dict[str, VectorStoreIndex]:
        """
        Set up all vector indexes.

        Returns:
            Dictionary mapping collection name to VectorStoreIndex
        """
        indexes = {}

        # 1. Recommendations archive
        logger.info("Ingesting recommendations history...")
        rec_loader = RecommendationHistoryLoader(self.recommendations_path)
        rec_docs = rec_loader.load()

        if rec_docs:
            rec_vector_store = self.vector_manager.get_vector_store(
                "recommendations_archive"
            )
            rec_index = VectorStoreIndex.from_documents(
                rec_docs,
                vector_store=rec_vector_store,
                embed_model=self.embed_model,
            )
            indexes["recommendations_archive"] = rec_index
            logger.info(f"Indexed {len(rec_docs)} recommendations")

        # 2. League knowledge
        logger.info("Ingesting league knowledge...")
        knowledge_text = load_league_knowledge()
        knowledge_loader = LeagueKnowledgeLoader(knowledge_text)
        knowledge_docs = knowledge_loader.load()

        knowledge_vector_store = self.vector_manager.get_vector_store(
            "league_knowledge"
        )
        knowledge_index = VectorStoreIndex.from_documents(
            knowledge_docs,
            vector_store=knowledge_vector_store,
            embed_model=self.embed_model,
        )
        indexes["league_knowledge"] = knowledge_index
        logger.info("Indexed league knowledge")

        return indexes

    def refresh_recommendations(self) -> VectorStoreIndex:
        """
        Refresh recommendations archive (call after new recommendations saved).

        Returns:
            Updated VectorStoreIndex
        """
        logger.info("Refreshing recommendations archive...")
        self.vector_manager.reset_collection("recommendations_archive")

        rec_loader = RecommendationHistoryLoader(self.recommendations_path)
        rec_docs = rec_loader.load()

        rec_vector_store = self.vector_manager.get_vector_store(
            "recommendations_archive"
        )
        rec_index = VectorStoreIndex.from_documents(
            rec_docs,
            vector_store=rec_vector_store,
            embed_model=self.embed_model,
        )

        logger.info(f"Refreshed index with {len(rec_docs)} recommendations")
        return rec_index
