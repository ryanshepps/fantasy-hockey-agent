"""Player evaluation sub-agent with RAG over player stats."""

import logging
import os

from llama_index.core import VectorStoreIndex
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import QueryEngineTool
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.anthropic import Anthropic

from indexing.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)


class PlayerEvaluatorAgent:
    """Sub-agent specialized in player evaluation and droppability assessment."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        llm_model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize PlayerEvaluatorAgent.

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

        # Create query engine over league knowledge
        knowledge_vector_store = vector_manager.get_vector_store("league_knowledge")
        knowledge_index = VectorStoreIndex.from_vector_store(
            knowledge_vector_store,
            embed_model=self.embed_model,
        )
        self.knowledge_query_engine = knowledge_index.as_query_engine(llm=self.llm)

        # Create agent with tools
        self.agent = self._create_agent()

    def _create_agent(self) -> ReActAgent:
        """Create ReActAgent with player evaluation tools."""
        # Query engine tool for league knowledge
        knowledge_tool = QueryEngineTool.from_defaults(
            query_engine=self.knowledge_query_engine,
            name="league_knowledge",
            description=(
                "Query league scoring rules, roster constraints, and strategy principles. "
                "Use this to understand what makes a player valuable in this league."
            ),
        )

        system_prompt = """You are an expert fantasy hockey player evaluator.

Your job is to assess which players on a roster are droppable vs keepers.

Key principles:
- NEVER recommend dropping elite talent (Makar, McDavid, etc.) for schedule reasons
- Consider: recent performance trends, position scarcity, league scoring weights
- Provide confidence scores (0.0-1.0) for droppability assessments
- Explain your reasoning clearly

Use the league_knowledge tool to understand scoring and roster constraints."""

        agent = ReActAgent(
            name="PlayerEvaluator",
            description="Player evaluation and droppability assessment agent",
            tools=[knowledge_tool],
            llm=self.llm,
            verbose=True,
            system_prompt=system_prompt,
        )

        logger.info("Created PlayerEvaluatorAgent")
        return agent

    def assess_droppable_players(self, roster: list[dict]) -> str:
        """
        Assess which players are droppable.

        Args:
            roster: List of player dicts from current roster

        Returns:
            Analysis string with droppable players and reasoning
        """
        roster_text = "\n".join(
            [f"- {p.get('name', 'Unknown')} ({p.get('position', '?')})" for p in roster]
        )

        query = f"""Analyze this roster and identify which players are droppable:

{roster_text}

For each droppable player, provide:
1. Confidence score (0.0-1.0)
2. Reasoning based on recent performance and league scoring
3. Whether they're streamable vs keeper"""

        response = self.agent.run(query)
        return str(response)
