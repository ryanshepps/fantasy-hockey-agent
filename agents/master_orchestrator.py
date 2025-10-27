"""Master orchestrator coordinating sub-agents."""

import logging
import os

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.anthropic import Anthropic

from agents.historical_analyst_agent import HistoricalAnalystAgent
from agents.player_evaluator_agent import PlayerEvaluatorAgent
from agents.strategy_planner_agent import StrategyPlannerAgent
from indexing.vector_store_manager import VectorStoreManager
from tools.llama_tools import get_llama_tools

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """Master agent coordinating specialized sub-agents."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        llm_model: str = "claude-sonnet-4-20250514",
        dry_run: bool = False,
    ):
        """
        Initialize MasterOrchestrator.

        Args:
            vector_manager: VectorStoreManager instance
            llm_model: Anthropic model name
            dry_run: If True, skip email sending
        """
        self.vector_manager = vector_manager
        self.dry_run = dry_run
        self.llm = Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=llm_model,
        )

        # Initialize sub-agents
        self.player_evaluator = PlayerEvaluatorAgent(
            vector_manager=vector_manager,
            llm_model=llm_model,
        )
        self.strategy_planner = StrategyPlannerAgent(
            vector_manager=vector_manager,
            llm_model=llm_model,
        )
        self.historical_analyst = HistoricalAnalystAgent(
            vector_manager=vector_manager,
            llm_model=llm_model,
        )

        # Create master agent
        self.agent = self._create_master_agent()

    def _create_master_agent(self) -> ReActAgent:
        """Create master ReActAgent with sub-agent tools."""
        # Wrap sub-agents as tools
        player_eval_tool = FunctionTool.from_defaults(
            fn=self.player_evaluator.assess_droppable_players,
            name="consult_player_evaluator",
            description=(
                "Consult the PlayerEvaluator sub-agent to assess which roster players "
                "are droppable. Provide roster data as input."
            ),
        )

        strategy_tool = FunctionTool.from_defaults(
            fn=self.strategy_planner.create_streaming_plan,
            name="consult_strategy_planner",
            description=(
                "Consult the StrategyPlanner sub-agent to create optimal streaming plan. "
                "Provide droppable players, schedule, and available players."
            ),
        )

        historical_tool = FunctionTool.from_defaults(
            fn=self.historical_analyst.query_similar_situations,
            name="consult_historical_analyst",
            description=(
                "Consult the HistoricalAnalyst sub-agent to find similar past situations "
                "and learn from historical recommendations."
            ),
        )

        # Add operational tools
        operational_tools = get_llama_tools()

        all_tools = [
            player_eval_tool,
            strategy_tool,
            historical_tool,
        ] + operational_tools

        system_prompt = """You are the master fantasy hockey analyst coordinating specialized sub-agents.

Your workflow:
1. Consult HistoricalAnalyst for context on similar past situations
2. Consult PlayerEvaluator to assess droppable players
3. Consult StrategyPlanner to create optimal streaming plan
4. Synthesize their insights into actionable recommendations
5. Format as HTML email and send using send_email tool
6. Save recommendations using save_recommendations tool

You coordinate the sub-agents but they have the domain expertise.
Make decisions based on their combined insights."""

        agent = ReActAgent(
            name="MasterOrchestrator",
            description="Master coordinator for fantasy hockey analysis",
            tools=all_tools,
            llm=self.llm,
            verbose=True,
            system_prompt=system_prompt,
        )

        logger.info("Created MasterOrchestrator with 3 sub-agents")
        return agent

    def run(self, prompt: str) -> str:
        """
        Run the master orchestrator.

        Args:
            prompt: User prompt (e.g., "Please proceed with the analysis")

        Returns:
            Final response
        """
        logger.info("Master orchestrator starting analysis...")
        response = self.agent.run(prompt)
        logger.info("Master orchestrator completed")
        return str(response)
