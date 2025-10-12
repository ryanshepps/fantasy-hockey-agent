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

from modules.logger import AgentLogger
from fantasy_tools import TOOL_FUNCTIONS, TOOLS
from tools.get_recommendation_history import (
    format_history_summary,
    get_recommendation_history,
)

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Model to use
MODEL = "claude-sonnet-4-20250514"

logger = AgentLogger.get_logger(__name__)
AgentLogger.set_library_log_level("yfpy", logging.WARNING)
AgentLogger.set_library_log_level("urllib3", logging.WARNING)


def load_recent_history_for_prompt() -> str:
    """
    Load recent recommendation history to include in the system prompt.

    Returns:
        Formatted string of recent recommendations (last 4 weeks for context)
    """
    try:
        history_data = get_recommendation_history(weeks_back=4)
        if history_data.get("success") and history_data.get("total_entries", 0) > 0:
            summary = format_history_summary(history_data)
            return f"\n\nRECENT RECOMMENDATION HISTORY:\n{summary}\n"
        else:
            return "\n\nRECENT RECOMMENDATION HISTORY: No previous recommendations found.\n"
    except Exception as e:
        return f"\n\nRECENT RECOMMENDATION HISTORY: Unable to load history ({e!s})\n"


def get_system_prompt() -> str:
    """
    Generate the system prompt with recent history included.

    Returns:
        Complete system prompt string
    """
    history_context = load_recent_history_for_prompt()

    return f"""You are an expert fantasy hockey analyst for a points-based league.

LEAGUE SCORING: Goals(5), Assists(2), PPP(2-stack), SHG(3), SOG/Hit/Block(0.5) | Goalie: W(6), GA(-3.5), Save(0.5), SO(6)
ROSTER: 6F, 4D, 1U, 2G, 6Bench, 2IR | Weekly limits: 4 acquisitions, 3 goalie starts minimum

{history_context}

STRATEGY:
Maximize games played via strategic streaming of LOWER-TIER players only. Use tools: get_current_roster → get_available_players → get_team_schedule → calculate_optimal_streaming. Never drop elite talent (Makar, McDavid, etc.) for schedule reasons. Elite talent > extra games.

ANALYSIS PRINCIPLES:
- Avoid small sample overreaction (1-2 weeks)
- Balance hot streaks vs established value
- Focus on sustainable opportunity (top-6 F, top-4 D, starting G)
- Check recommendation history to avoid repetition
- Verify drop candidates are truly droppable

TASK:
1. Fetch roster, top 100 free agents, team schedules (2 weeks)
2. Use calculate_optimal_streaming for recommendations with EXACT dates/math
3. Contextualize with performance trends, position needs, history check
4. Send email with recommendations (plain text, no HTML)
5. Save recommendations using save_recommendations tool

EMAIL STRUCTURE (PLAIN TEXT ONLY - NO HTML):
SUMMARY | STREAMING STRATEGY (exact dates with game math) | PLAYER CONTEXT | TIMING OPTIMIZATION (stay under 4/week) | ALTERNATIVES | NOTES"""


def process_tool_call(tool_name: str, tool_input: dict, dry_run: bool = False) -> tuple[dict, float]:
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
    cached_tools = TOOLS[:-1] + [{**TOOLS[-1], "cache_control": {"type": "ephemeral"}}]

    api_call_count = 0
    while True:
        api_call_count += 1
        api_call_start = time.time()

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
                    tool_result, execution_time_ms = process_tool_call(block.name, block.input, dry_run)

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
