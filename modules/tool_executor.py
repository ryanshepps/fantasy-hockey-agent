"""Tool executor with dry-run support."""

import logging
import time
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tool functions with dry-run support and result serialization.

    Responsibilities:
    - Execute tool functions
    - Handle dry-run mode for side-effect tools
    - Serialize Pydantic models to dicts
    - Track execution time
    """

    SIDE_EFFECT_TOOLS: ClassVar[list[str]] = ["send_email", "save_recommendations"]

    def __init__(self, tool_functions: dict[str, Callable], dry_run: bool = False):
        """
        Initialize executor.

        Args:
            tool_functions: Mapping of tool name to tool function
            dry_run: If True, skip side-effect tools
        """
        self.tool_functions = tool_functions
        self.dry_run = dry_run

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[dict, float]:
        """
        Execute a tool function and return result with execution time.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tuple of (tool result as dict, execution time in ms)
        """
        if tool_name not in self.tool_functions:
            return {"error": f"Unknown tool: {tool_name}"}, 0.0

        # Handle dry-run for side-effect tools
        if self.dry_run and tool_name in self.SIDE_EFFECT_TOOLS:
            return self._handle_dry_run(tool_name, tool_input)

        try:
            start_time = time.time()
            result = self.tool_functions[tool_name](**tool_input)
            execution_time_ms = (time.time() - start_time) * 1000

            # Serialize Pydantic models
            result = self._serialize_result(result)

            logger.info(f"Tool '{tool_name}' executed in {execution_time_ms:.2f}ms")
            return result, execution_time_ms

        except Exception as e:
            logger.error(f"Tool '{tool_name}' failed: {e!s}")
            return {"error": str(e)}, 0.0

    def _handle_dry_run(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[dict, float]:
        """Handle dry-run for side-effect tools."""
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

        return {"error": f"Unknown side-effect tool: {tool_name}"}, 0.0

    def _serialize_result(self, result: Any) -> dict | list | Any:
        """Serialize Pydantic models to JSON-compatible dicts."""
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
        elif isinstance(result, list) and result and isinstance(result[0], BaseModel):
            return [item.model_dump(mode="json") for item in result]
        return result
