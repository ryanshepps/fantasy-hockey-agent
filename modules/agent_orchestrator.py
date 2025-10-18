"""Agent orchestrator for conversation loop management."""

import json
import logging
import time
from typing import Any
from anthropic import Anthropic

from modules.logger import AgentLogger
from modules.rate_limiter import RateLimiter
from modules.message_handler import MessageHandler
from modules.tool_executor import ToolExecutor


logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates the agent conversation loop.

    Responsibilities:
    - Make API calls to Claude
    - Handle rate limiting
    - Process assistant responses
    - Execute tools
    - Manage conversation flow
    """

    def __init__(
        self,
        client: Anthropic,
        system_blocks: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_functions: dict[str, Any],
        initial_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        dry_run: bool = False,
        verbose: bool = True,
    ):
        """
        Initialize orchestrator.

        Args:
            client: Anthropic API client
            system_blocks: System prompt blocks
            tools: Tool definitions for API
            tool_functions: Mapping of tool name to function
            initial_prompt: Initial user prompt
            model: Model to use
            dry_run: If True, skip side-effect tools
            verbose: If True, log detailed info
        """
        self.client = client
        self.system_blocks = system_blocks
        self.tools = self._prepare_cached_tools(tools)
        self.model = model
        self.dry_run = dry_run
        self.verbose = verbose

        self.rate_limiter = RateLimiter()
        self.message_handler = MessageHandler(initial_prompt)
        self.tool_executor = ToolExecutor(tool_functions, dry_run)

        self.api_call_count = 0

    def _prepare_cached_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Add cache_control to last tool definition.

        Args:
            tools: List of tool definitions

        Returns:
            Tools with cache_control on last tool
        """
        if not tools:
            return []

        cached_tools = tools[:-1] + [{**tools[-1], "cache_control": {"type": "ephemeral"}}]
        return cached_tools

    def run(self) -> str:
        """
        Run the agent conversation loop.

        Returns:
            Final text response from Claude
        """
        if self.verbose:
            mode = "DRY-RUN MODE" if self.dry_run else ""
            logger.info(f"Starting Fantasy Hockey Agent {mode}".strip())

        while True:
            self.api_call_count += 1

            # Rate limiting
            self.rate_limiter.throttle_if_needed()

            # Make API call
            api_call_start = time.time()
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16384,
                system=self.system_blocks,
                tools=self.tools,
                messages=self.message_handler.get_messages(),
            )
            api_call_time_ms = (time.time() - api_call_start) * 1000

            # Log token usage
            if hasattr(response, "usage"):
                usage = response.usage
                AgentLogger.log_token_usage(
                    step=f"claude_api_call_{self.api_call_count}",
                    input_tokens=getattr(usage, "input_tokens", 0),
                    output_tokens=getattr(usage, "output_tokens", 0),
                    cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0),
                    cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
                    execution_time_ms=api_call_time_ms,
                )

                # Update rate limiter
                self.rate_limiter.record_usage(getattr(usage, "input_tokens", 0))

            if self.verbose:
                logger.info(f"Stop reason: {response.stop_reason}")

            # Extract content blocks
            assistant_content = []
            for block in response.content:
                if block.type in ["text", "tool_use"]:
                    if block.type == "tool_use" and self.verbose:
                        logger.info(f"Tool: {block.name}")
                    assistant_content.append(block)

            # Add assistant response to messages
            self.message_handler.add_assistant_response(assistant_content)

            # Handle stop reasons
            if response.stop_reason == "end_turn":
                return self.message_handler.extract_final_text(response.content)

            elif response.stop_reason == "tool_use":
                tool_blocks = self.message_handler.extract_tool_uses(response.content)
                tool_results = self._process_tool_blocks(tool_blocks)
                self.message_handler.add_tool_results(tool_results)

            else:
                # Unexpected stop reason - return last text
                break

        # Fallback if loop exits unexpectedly
        for block in reversed(response.content):
            if block.type == "text":
                return block.text

        return "Agent completed without final response."

    def _process_tool_blocks(self, tool_blocks: list[Any]) -> list[dict[str, Any]]:
        """
        Process tool use blocks and return tool results.

        Args:
            tool_blocks: List of tool_use blocks

        Returns:
            List of tool result dictionaries
        """
        tool_results = []

        for block in tool_blocks:
            tool_result, execution_time_ms = self.tool_executor.execute(block.name, block.input)

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

        return tool_results
