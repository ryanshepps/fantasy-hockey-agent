#!/usr/bin/env python3
"""
Fantasy Hockey AI Agent using Claude and the Anthropic SDK.

This agent analyzes your fantasy hockey team, compares it to available free agents,
and provides pickup/drop recommendations via email.
"""

import argparse
import logging
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from fantasy_tools import TOOL_FUNCTIONS, TOOLS
from modules.agent_orchestrator import AgentOrchestrator
from modules.logger import AgentLogger
from modules.prefetch_registry import PrefetchRegistry
from modules.system_prompt_builder import SystemPromptBuilder

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Model to use
MODEL = "claude-sonnet-4-20250514"

# Configure logger
logger = AgentLogger.get_logger(__name__)
AgentLogger.set_library_log_level("yfpy", logging.WARNING)
AgentLogger.set_library_log_level("urllib3", logging.WARNING)


def run_llamaindex_agent(
    prompt: str,
    verbose: bool = True,
    dry_run: bool = False,
) -> str:
    """
    Run the fantasy hockey agent using LlamaIndex multi-agent architecture.

    Args:
        prompt: Initial prompt for the agent
        verbose: Print conversation details
        dry_run: If True, skip sending emails

    Returns:
        Final response from master orchestrator
    """
    from agents.master_orchestrator import MasterOrchestrator
    from indexing.data_ingestion import DataIngestionPipeline
    from indexing.vector_store_manager import VectorStoreManager

    # Setup vector store
    vector_manager = VectorStoreManager(persist_dir="./data/vector_db")

    # Ingest data
    if verbose:
        logger.info("Setting up vector indexes...")
    pipeline = DataIngestionPipeline(
        vector_manager=vector_manager,
        recommendations_path="recommendations_history.json",
    )
    pipeline.setup_indexes()

    # Create orchestrator
    orchestrator = MasterOrchestrator(
        vector_manager=vector_manager,
        dry_run=dry_run,
    )

    # Run
    return orchestrator.run(prompt)


def setup_prefetch_registry() -> PrefetchRegistry:
    """
    Configure which tools can be prefetched.

    To add a new prefetchable tool:
    1. Import the tool function from TOOL_FUNCTIONS
    2. Call registry.register() with:
       - tool_name: Must match key in TOOLS
       - tool_function: The actual function to call
       - data_key: Key to use in prefetch_data dict
       - description: What this tool fetches

    Returns:
        Configured PrefetchRegistry
    """
    registry = PrefetchRegistry()

    registry.register(
        tool_name="get_recommendation_history",
        tool_function=TOOL_FUNCTIONS["get_recommendation_history"],
        data_key="recommendation_history",
        description="Recent recommendation history from file",
    )

    registry.register(
        tool_name="get_current_roster",
        tool_function=TOOL_FUNCTIONS["get_current_roster"],
        data_key="roster",
        description="Current roster from Yahoo API",
    )

    registry.register(
        tool_name="get_team_schedule",
        tool_function=lambda: TOOL_FUNCTIONS["get_team_schedule"](weeks=2),
        data_key="schedule",
        description="Team schedule for next 2 weeks from NHL API",
    )

    return registry


def get_system_prompt(prefetch_data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """
    Generate the system prompt for the fantasy hockey agent.

    Args:
        prefetch_data: Optional pre-fetched data to embed in system prompt

    Returns:
        List of system prompt blocks
    """
    instruction_text = """You are an expert fantasy hockey analyst for a points-based league.

LEAGUE SCORING: Goals(5), Assists(2), PPP(2-stack), SHG(3), SOG/Hit/Block(0.5) | Goalie: W(6), GA(-3.5), Save(0.5), SO(6)
ROSTER: 6F, 4D, 1U, 2G, 6Bench, 2IR | Weekly limits: 4 acquisitions, 3 goalie starts minimum

STRATEGY:
Maximize games played via strategic streaming of MID-TIER and STREAMABLE players only. Use tools: get_team_schedule → get_players_from_teams → get_current_roster → assess_droppable_players → find_streaming_matches. Never drop elite talent (Makar, McDavid, etc.) for schedule reasons. Elite talent > extra games.

ANALYSIS PRINCIPLES:
- Avoid making major decisions based on small sample sizes (1-2 weeks)
- Balance hot streaks vs established value
- Check recommendation history for context and make new high-conviction picks if the opportunity is there

TASK:
1. Check recommendation_history for context on recent picks
2. Assess which roster players are droppable using assess_droppable_players tool (returns list of droppable Player models)
3. Find optimal streaming matches using find_streaming_matches tool with droppable players, available players, and schedule
4. Think through a streaming strategy step by step and come up with a plan for streaming players to maximize games played
5. Format your plan into a simple HTML email with the following structure:
  - STREAMING STRATEGY: Must provide exact dates that will maximize total games played
  - ALTERNATIVES: If there are no optimal streaming matches, provide a list of alternatives
  - NOTES: Any additional notes or context
6. Send the email using the send_email tool
7. Save the recommendations using the save_recommendations tool"""

    builder = SystemPromptBuilder(instruction_text)
    return builder.build(prefetch_data)


def prefetch_static_data(registry: PrefetchRegistry) -> dict[str, Any]:
    """
    Pre-fetch data using the configured registry.

    Args:
        registry: Configured PrefetchRegistry

    Returns:
        Dictionary mapping data_key -> tool result
    """
    logger.info("Pre-fetching static data...")

    import time

    prefetch_start = time.time()

    try:
        data = registry.execute_all()

        # Serialize Pydantic models
        from pydantic import BaseModel

        for key, value in data.items():
            if isinstance(value, BaseModel):
                data[key] = value.model_dump(mode="json")

        prefetch_time = (time.time() - prefetch_start) * 1000
        logger.info(f"Pre-fetch completed in {prefetch_time:.2f}ms")

        return data

    except Exception as e:
        logger.error(f"Pre-fetch failed: {e}")
        logger.warning("Falling back to tool-based fetching")
        return {}


def run_agent(
    prompt: str,
    prefetch_registry: PrefetchRegistry | None = None,
    prefetch_data: dict[str, Any] | None = None,
    verbose: bool = True,
    dry_run: bool = False,
) -> str:
    """
    Run the fantasy hockey agent with the given prompt.

    Args:
        prompt: Initial prompt for the agent
        prefetch_registry: Registry of prefetchable tools (for filtering)
        prefetch_data: Optional pre-fetched data to embed in system prompt
        verbose: Print conversation details
        dry_run: If True, skip sending emails and saving recommendations

    Returns:
        Final response from Claude
    """
    system_prompt_blocks = get_system_prompt(prefetch_data)

    # Filter out prefetched tools if data was provided
    if prefetch_data and prefetch_registry:
        prefetched_tool_names = prefetch_registry.get_tool_names()
        available_tools = [tool for tool in TOOLS if tool["name"] not in prefetched_tool_names]
        if verbose:
            logger.info(
                f"Pre-fetch enabled: {len(TOOLS) - len(available_tools)} tools removed from list"
            )
    else:
        available_tools = TOOLS

    orchestrator = AgentOrchestrator(
        client=client,
        system_blocks=system_prompt_blocks,
        tools=available_tools,
        tool_functions=TOOL_FUNCTIONS,
        initial_prompt=prompt,
        model=MODEL,
        dry_run=dry_run,
        verbose=verbose,
    )

    return orchestrator.run()


def main():
    """
    Main function to run the fantasy hockey agent.
    """
    parser = argparse.ArgumentParser(
        description="Fantasy Hockey AI Agent - Analyze your team and get recommendations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without sending email or saving recommendations",
    )
    parser.add_argument(
        "--skip-prefetch",
        action="store_true",
        help="Skip pre-fetching static data (use tools instead, useful for testing)",
    )
    parser.add_argument(
        "--use-llamaindex",
        action="store_true",
        help="Use LlamaIndex multi-agent architecture (experimental)",
    )
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY not found in environment variables")
        logger.error("Please add it to your .env file")
        return

    prompt = "Please proceed with the analysis and send me the email."

    mode_msg = " (DRY-RUN)" if args.dry_run else ""

    # Use LlamaIndex if flag set
    if args.use_llamaindex:
        logger.info(f"Starting Fantasy Hockey Analysis with LlamaIndex{mode_msg}...")
        result = run_llamaindex_agent(
            prompt,
            verbose=True,
            dry_run=args.dry_run,
        )
    else:
        # Existing prefetch logic
        prefetch_registry = setup_prefetch_registry()
        prefetch_data = None
        if not args.skip_prefetch:
            try:
                prefetch_data = prefetch_static_data(prefetch_registry)
                logger.info("Pre-fetch successful - data will be cached in system prompt")
            except Exception as e:
                logger.warning(f"Pre-fetch failed: {e}")
                logger.warning("Falling back to tool-based fetching")

        logger.info(f"Starting Fantasy Hockey Analysis{mode_msg}...")
        result = run_agent(
            prompt,
            prefetch_registry=prefetch_registry,
            prefetch_data=prefetch_data,
            verbose=True,
            dry_run=args.dry_run,
        )

    logger.info("Analysis complete!")
    logger.info(result)

    AgentLogger.print_usage_summary()


if __name__ == "__main__":
    main()
