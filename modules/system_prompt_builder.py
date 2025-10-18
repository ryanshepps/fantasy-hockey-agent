"""System prompt builder with prefetch data support."""

import json
from typing import Any


class SystemPromptBuilder:
    """
    Builds system prompt blocks with optional prefetch data caching.

    Handles the complex logic of:
    - Creating text blocks with proper cache_control placement
    - Formatting prefetch data as JSON
    - Ensuring last block is always cached
    """

    def __init__(self, instruction_text: str):
        """
        Initialize builder with instruction text.

        Args:
            instruction_text: Core instructions for the agent
        """
        self.instruction_text = instruction_text

    def build(self, prefetch_data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Build system prompt blocks.

        Args:
            prefetch_data: Optional pre-fetched data to include

        Returns:
            List of prompt blocks suitable for Anthropic API
        """
        blocks = [{"type": "text", "text": self.instruction_text}]

        if prefetch_data:
            data_text = self._format_prefetch_data(prefetch_data)
            blocks.append(
                {"type": "text", "text": data_text, "cache_control": {"type": "ephemeral"}}
            )
        else:
            # Cache instructions if no prefetch data
            blocks[0]["cache_control"] = {"type": "ephemeral"}

        return blocks

    def _format_prefetch_data(self, prefetch_data: dict[str, Any]) -> str:
        """
        Format prefetch data as structured text.

        Args:
            prefetch_data: Dictionary of prefetched data

        Returns:
            Formatted string with JSON-serialized data
        """
        sections = ["\n\n=== PRE-FETCHED DATA (already retrieved, do not call these tools) ===\n"]

        for key, value in prefetch_data.items():
            sections.append(f"\n{key.upper().replace('_', ' ')}:\n")
            sections.append(json.dumps(value, indent=2))
            sections.append("\n")

        return "".join(sections)
