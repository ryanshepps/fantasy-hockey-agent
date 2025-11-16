"""Strategy planning sub-agent for schedule optimization."""

import logging
import os

from llama_index.core import VectorStoreIndex
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import QueryEngineTool
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.anthropic import Anthropic

from indexing.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)


class StrategyPlannerAgent:
    """Sub-agent specialized in streaming strategy and schedule optimization."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        llm_model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize StrategyPlannerAgent.

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

        # Query engine over league knowledge
        knowledge_vector_store = vector_manager.get_vector_store("league_knowledge")
        knowledge_index = VectorStoreIndex.from_vector_store(
            knowledge_vector_store,
            embed_model=self.embed_model,
        )
        self.knowledge_query_engine = knowledge_index.as_query_engine(llm=self.llm)

        self.agent = self._create_agent()

    def _create_agent(self) -> ReActAgent:
        """Create ReActAgent with strategy planning tools."""
        knowledge_tool = QueryEngineTool.from_defaults(
            query_engine=self.knowledge_query_engine,
            name="league_knowledge",
            description=(
                "Query league rules including weekly acquisition limits (4), "
                "roster constraints, and streaming strategy principles."
            ),
        )

        system_prompt = """You are an expert fantasy hockey strategist.

Your job is to create optimal streaming plans that maximize games played while respecting constraints.

Key principles:
- Respect weekly acquisition limit (4 max)
- Maximize total games played across the roster
- Provide specific dates for pickups/drops
- Calculate expected value gains
- Ensure recommendations respect roster limits

Use league_knowledge tool to verify constraints."""

        agent = ReActAgent(
            name="StrategyPlanner",
            description="Schedule optimization and streaming strategy agent",
            tools=[knowledge_tool],
            llm=self.llm,
            verbose=True,
            system_prompt=system_prompt,
        )

        logger.info("Created StrategyPlannerAgent")
        return agent

    def create_streaming_plan(
        self,
        droppable_players: list[str],
        schedule: dict,
        available_players: list[dict]
    ) -> str:
        """
        Create streaming strategy.

        Args:
            droppable_players: List of droppable player names
            schedule: Team schedule data
            available_players: List of available FA/waiver players

        Returns:
            Streaming plan with dates and expected value
        """
        query = f"""Create an optimal streaming plan:

Droppable players: {', '.join(droppable_players)}

Schedule windows: {schedule}

Available options: {len(available_players)} players

Provide:
1. Specific dates for each pickup/drop
2. Expected point value gain
3. Justification for timing"""

        response = self.agent.run(query)
        return str(response)
