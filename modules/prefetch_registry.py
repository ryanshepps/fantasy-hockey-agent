"""Registry for prefetchable tools with declarative configuration."""

from typing import Any, Callable
import logging
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class ToolMetadata(BaseModel):
    """Metadata for a prefetchable tool."""

    tool_name: str
    tool_function: Callable[..., Any]
    data_key: str
    description: str


class PrefetchRegistry:
    """
    Central registry for tools that can be prefetched.

    Provides single source of truth for:
    - Which tools are prefetchable
    - How to execute them
    - What data key they populate
    - Tool filtering for API calls
    """

    def __init__(self):
        """Initialize empty registry."""
        self._registry: dict[str, ToolMetadata] = {}

    def register(
        self, tool_name: str, tool_function: Callable[..., Any], data_key: str, description: str
    ) -> None:
        """
        Register a tool as prefetchable.

        Args:
            tool_name: Name of the tool (must match TOOLS definition)
            tool_function: Callable that executes the tool
            data_key: Key to use in prefetch_data dict
            description: Human-readable description of what this tool fetches
        """
        self._registry[tool_name] = ToolMetadata(
            tool_name=tool_name,
            tool_function=tool_function,
            data_key=data_key,
            description=description,
        )
        logger.debug(f"Registered prefetchable tool: {tool_name} -> {data_key}")

    def get_metadata(self, tool_name: str) -> dict[str, Any]:
        """Get metadata for a registered tool."""
        if tool_name not in self._registry:
            raise ValueError(f"Tool '{tool_name}' not registered")
        return self._registry[tool_name].model_dump()

    def get_tool_names(self) -> list[str]:
        """Get list of all registered tool names."""
        return list(self._registry.keys())

    def execute_all(self) -> dict[str, Any]:
        """
        Execute all registered tools and return data keyed by data_key.

        Returns:
            Dictionary mapping data_key -> tool result
        """
        data = {}
        for metadata in self._registry.values():
            try:
                result = metadata.tool_function()
                data[metadata.data_key] = result
                logger.info(f"Prefetched '{metadata.tool_name}' -> '{metadata.data_key}'")
            except Exception as e:
                logger.error(f"Failed to prefetch '{metadata.tool_name}': {e}")
                raise
        return data
