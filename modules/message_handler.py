"""Message handler for agent conversation management."""

from typing import Any


class MessageHandler:
    """
    Manages conversation messages for the agent.

    Responsibilities:
    - Maintain message history
    - Add assistant responses
    - Add tool results
    - Extract final text from responses
    - Extract tool use blocks
    """

    def __init__(self, initial_prompt: str):
        """
        Initialize handler with initial user prompt.

        Args:
            initial_prompt: Initial user message to start conversation
        """
        self._messages = [{"role": "user", "content": initial_prompt}]

    def get_messages(self) -> list[dict[str, Any]]:
        """
        Get current message history.

        Returns:
            List of message dictionaries
        """
        return self._messages

    def add_assistant_response(self, content: list[Any]) -> None:
        """
        Add assistant's response to message history.

        Args:
            content: List of content blocks from API response
        """
        self._messages.append({"role": "assistant", "content": content})

    def add_tool_results(self, tool_results: list[dict[str, Any]]) -> None:
        """
        Add tool results to message history.

        Args:
            tool_results: List of tool result dictionaries
        """
        self._messages.append({"role": "user", "content": tool_results})

    def extract_final_text(self, content_blocks: list[Any]) -> str:
        """
        Extract and concatenate all text blocks.

        Args:
            content_blocks: List of content blocks from API response

        Returns:
            Concatenated text from all text blocks
        """
        text_parts = []
        for block in content_blocks:
            if block.type == "text":
                text_parts.append(block.text)
        return "".join(text_parts)

    def extract_tool_uses(self, content_blocks: list[Any]) -> list[Any]:
        """
        Extract tool use blocks from content.

        Args:
            content_blocks: List of content blocks from API response

        Returns:
            List of tool_use blocks
        """
        return [block for block in content_blocks if block.type == "tool_use"]
