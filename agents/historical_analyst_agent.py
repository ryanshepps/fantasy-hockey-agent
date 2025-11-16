"""Historical analyst sub-agent with RAG over past recommendations."""

import logging
import os

from llama_index.core import VectorStoreIndex
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import QueryEngineTool
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.anthropic import Anthropic

from indexing.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)


class HistoricalAnalystAgent:
    """Sub-agent specialized in learning from past recommendations."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        llm_model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize HistoricalAnalystAgent.

        Args:
            vector_manager: VectorStoreManager instance
            llm_model: Anthropic model name
        """
        self.vector_manager = vector_manager
        self.llm = Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=llm_model,
        )
        self.embed_model = OpenAIEmbedding(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="text-embedding-3-small",
        )

        # Query engine over recommendations archive
        rec_vector_store = vector_manager.get_vector_store("recommendations_archive")
        rec_index = VectorStoreIndex.from_vector_store(
            rec_vector_store,
            embed_model=self.embed_model,
        )
        self.recommendations_query_engine = rec_index.as_query_engine(
            llm=self.llm,
            similarity_top_k=5,
        )

        self.agent = self._create_agent()

    def _create_agent(self) -> ReActAgent:
        """Create ReActAgent with historical analysis tools."""
        recommendations_tool = QueryEngineTool.from_defaults(
            query_engine=self.recommendations_query_engine,
            name="recommendations_history",
            description=(
                "Search past recommendations to find similar situations, "
                "learn from past decisions, and avoid repeated mistakes."
            ),
        )

        system_prompt = """You are an expert at learning from historical fantasy hockey decisions.

Your job is to provide context from past recommendations to inform current decisions.

Key principles:
- Identify similar past situations
- Highlight what worked vs what didn't
- Warn about repeated mistakes
- Provide confidence based on historical patterns

Use recommendations_history tool to query past decisions."""

        agent = ReActAgent(
            name="HistoricalAnalyst",
            description="Historical analysis and pattern recognition agent",
            tools=[recommendations_tool],
            llm=self.llm,
            verbose=True,
            system_prompt=system_prompt,
        )

        logger.info("Created HistoricalAnalystAgent")
        return agent

    def query_similar_situations(self, current_situation: str) -> str:
        """
        Find similar past situations.

        Args:
            current_situation: Description of current decision context

        Returns:
            Historical context and insights
        """
        query = f"""Find similar past situations to this current context:

{current_situation}

Provide:
1. Most similar past recommendations
2. What happened (if known)
3. Lessons learned
4. Warnings about repeated patterns"""

        response = self.agent.run(query)
        return str(response)
