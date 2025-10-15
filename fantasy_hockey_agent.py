#!/usr/bin/env python3
"""
Fantasy Hockey AI Agent using Claude and the Anthropic SDK.

This agent analyzes your fantasy hockey team, compares it to available free agents,
and provides pickup/drop recommendations via email.
"""

import argparse
import json
import logging
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv

from fantasy_tools import TOOL_FUNCTIONS, TOOLS
from modules.logger import AgentLogger

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Model to use
MODEL = "claude-sonnet-4-20250514"

# Rate limiting configuration
# Anthropic's rate limit is 30,000 input tokens per minute
ANTHROPIC_RATE_LIMIT_TPM = 30000

# Throttle API calls if the previous call used more than this many input tokens
# This threshold triggers delay calculation to prevent hitting rate limits
RATE_LIMIT_TOKEN_THRESHOLD = 10000

# Safety buffer multiplier to account for clock skew between local system and Anthropic's servers
# A 1.1x buffer means we wait 10% longer than the calculated minimum to ensure reliability
RATE_LIMIT_SAFETY_BUFFER = 1.1

logger = AgentLogger.get_logger(__name__)
AgentLogger.set_library_log_level("yfpy", logging.WARNING)
AgentLogger.set_library_log_level("urllib3", logging.WARNING)


def get_system_prompt() -> str:
    """
    Generate the system prompt for the fantasy hockey agent.

    Returns:
        Complete system prompt string
    """
    return """You are an expert fantasy hockey analyst for a points-based league.

LEAGUE SCORING: Goals(5), Assists(2), PPP(2-stack), SHG(3), SOG/Hit/Block(0.5) | Goalie: W(6), GA(-3.5), Save(0.5), SO(6)
ROSTER: 6F, 4D, 1U, 2G, 6Bench, 2IR | Weekly limits: 4 acquisitions, 3 goalie starts minimum

STRATEGY:
Maximize games played via strategic streaming of LOWER-TIER players only. Use tools: get_current_roster → get_available_players → get_team_schedule → calculate_optimal_streaming. Never drop elite talent (Makar, McDavid, etc.) for schedule reasons. Elite talent > extra games.

ANALYSIS PRINCIPLES:
- Avoid small sample overreaction (1-2 weeks)
- Balance hot streaks vs established value
- Focus on sustainable opportunity (top-6 F, top-4 D, starting G)
- Check recommendation history for context, but prioritize highest-conviction picks
- It's fine to repeat recommendations if conviction remains strong, or pivot to better opportunities
- Verify drop candidates are truly droppable

TASK:
1. Check recommendation_history for context on recent picks
2. Fetch roster, top 100 free agents, team schedules (2 weeks)
3. Use calculate_optimal_streaming for recommendations with EXACT dates/math. You MUST recommend an exact date for when to drop/pickup a new player (and what team to pickup from) to maximize the total number of games played in the current week.
4. Contextualize with performance trends, position needs, and explain continuity or changes from recent history
5. Send email with recommendations (very simple HTML)
6. Save recommendations using save_recommendations tool

EMAIL STRUCTURE (VERY SIMPLE HTML):
SUMMARY | STREAMING STRATEGY (exact dates with game math) | PLAYER CONTEXT | TIMING OPTIMIZATION (stay under 4/week) | ALTERNATIVES | NOTES"""


def process_tool_call(
    tool_name: str, tool_input: dict, dry_run: bool = False
) -> tuple[dict, float]:
    """
    Execute a tool function and return the result with execution time.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        dry_run: If True, skip execution of send_email and save_recommendations

    Returns:
        Tuple of (tool execution result as a dictionary, execution time in ms)
    """
    if tool_name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {tool_name}"}, 0.0

    # In dry-run mode, skip send_email and save_recommendations
    if dry_run and tool_name in ["send_email", "save_recommendations"]:
        logger.info(f"DRY-RUN: Skipping '{tool_name}' execution")

        if tool_name == "send_email":
            subject = tool_input.get("subject", "")
            body = tool_input.get("body", "")
            logger.info(f"DRY-RUN: Would send email with subject: {subject}")
            logger.info(f"DRY-RUN: Email body ({len(body)} chars):")
            logger.info("=" * 80)
            logger.info(body)
            logger.info("=" * 80)
            return {
                "success": True,
                "message": f"DRY-RUN: Email would be sent (subject: {subject})",
                "dry_run": True,
            }, 0.0

        elif tool_name == "save_recommendations":
            subject = tool_input.get("subject", "")
            logger.info(f"DRY-RUN: Would save recommendation with subject: {subject}")
            return {
                "success": True,
                "message": "DRY-RUN: Recommendations would be saved to history",
                "dry_run": True,
            }, 0.0

    try:
        start_time = time.time()
        result = TOOL_FUNCTIONS[tool_name](**tool_input)
        execution_time_ms = (time.time() - start_time) * 1000

        logger.info(f"Tool '{tool_name}' executed in {execution_time_ms:.2f}ms")
        return result, execution_time_ms
    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed: {e!s}")
        return {"error": str(e)}, 0.0


def run_agent(prompt: str, verbose: bool = True, dry_run: bool = False) -> str:
    """
    Run the fantasy hockey agent with the given prompt.

    Args:
        prompt: Initial prompt for the agent
        verbose: Print conversation details
        dry_run: If True, skip sending emails and saving recommendations

    Returns:
        Final response from Claude
    """
    messages = [{"role": "user", "content": prompt}]
    mode = "DRY-RUN MODE" if dry_run else ""
    if verbose:
        logger.info(f"Starting Fantasy Hockey Agent {mode}".strip())

    system_prompt_text = get_system_prompt()
    cached_tools = [*TOOLS[:-1], {**TOOLS[-1], "cache_control": {"type": "ephemeral"}}]

    api_call_count = 0
    previous_input_tokens = 0  # Track tokens from previous API call for rate limiting
    while True:
        api_call_count += 1
        api_call_start = time.time()

        # Rate limiting: Check if previous call exceeded threshold
        if previous_input_tokens > RATE_LIMIT_TOKEN_THRESHOLD:
            # Calculate delay: (tokens_used / rate_limit) * 60 seconds * safety_buffer
            calculated_delay = (previous_input_tokens / ANTHROPIC_RATE_LIMIT_TPM) * 60
            actual_delay = calculated_delay * RATE_LIMIT_SAFETY_BUFFER

            logger.info(
                f"Rate limiting: Previous call used {previous_input_tokens:,} tokens "
                f"(>{RATE_LIMIT_TOKEN_THRESHOLD:,} threshold). "
                f"Waiting {actual_delay:.1f} seconds to avoid rate limit "
                f"(calculated: {calculated_delay:.1f}s + {(RATE_LIMIT_SAFETY_BUFFER - 1) * 100:.0f}% safety buffer)"
            )
            time.sleep(actual_delay)

        response = client.messages.create(
            model=MODEL,
            max_tokens=16384,
            system=[
                {"type": "text", "text": system_prompt_text, "cache_control": {"type": "ephemeral"}}
            ],
            tools=cached_tools,
            messages=messages,
        )

        api_call_time_ms = (time.time() - api_call_start) * 1000

        if hasattr(response, "usage"):
            usage = response.usage
            AgentLogger.log_token_usage(
                step=f"claude_api_call_{api_call_count}",
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
                cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0),
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
                execution_time_ms=api_call_time_ms,
            )

            # Update token tracking for rate limiting
            previous_input_tokens = getattr(usage, "input_tokens", 0)

        if verbose:
            logger.info(f"Stop reason: {response.stop_reason}")

        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append(block)
            elif block.type == "tool_use":
                if verbose:
                    logger.info(f"Tool: {block.name}")
                assistant_content.append(block)

        # Add assistant's response to messages
        messages.append({"role": "assistant", "content": assistant_content})

        # If Claude is done (no more tool calls), break
        if response.stop_reason == "end_turn":
            # Extract final text response
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
            return final_text

        # Process tool calls
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_result, execution_time_ms = process_tool_call(
                        block.name, block.input, dry_run
                    )

                    AgentLogger.log_token_usage(
                        step=f"tool_{block.name}",
                        input_tokens=0,
                        output_tokens=0,
                        execution_time_ms=execution_time_ms,
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result),
                        }
                    )

            # Send tool results back to Claude
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason
            break

    # If we exit the loop without returning, return the last text
    for block in reversed(response.content):
        if block.type == "text":
            return block.text

    return "Agent completed without final response."


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
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY not found in environment variables")
        logger.error("Please add it to your .env file")
        return

    prompt = "Please proceed with the analysis and send me the email."

    mode_msg = " (DRY-RUN)" if args.dry_run else ""
    logger.info(f"Starting Fantasy Hockey Analysis{mode_msg}...")

    result = run_agent(prompt, verbose=True, dry_run=args.dry_run)

    logger.info("Analysis complete!")
    logger.info(result)

    AgentLogger.print_usage_summary()


if __name__ == "__main__":
    main()
