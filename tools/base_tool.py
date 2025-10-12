#!/usr/bin/env python3
"""
Base class for Fantasy Hockey tools.

This abstract base class enforces that each tool must define:
1. TOOL_DEFINITION - The tool schema for Claude
2. run() method - The tool implementation

Similar to Java abstract classes, this provides a contract that all tools must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseTool(ABC):
    """
    Abstract base class for fantasy hockey tools.

    All tool implementations must:
    1. Define TOOL_DEFINITION as a class variable
    2. Implement the run() class method

    Example:
        class MyTool(BaseTool):
            TOOL_DEFINITION = {
                "name": "my_tool",
                "description": "...",
                "input_schema": {...}
            }

            @classmethod
            def run(cls, **kwargs) -> Dict[str, Any]:
                # Implementation here
                return {"success": True}
    """

    # Class variable that must be defined by subclasses
    TOOL_DEFINITION: ClassVar[dict[str, Any]]

    def __init_subclass__(cls, **kwargs):
        """
        Validate that subclasses define TOOL_DEFINITION.

        This is called automatically when a class inherits from BaseTool.
        """
        super().__init_subclass__(**kwargs)

        # Check if TOOL_DEFINITION is defined (not inherited from ABC)
        if "TOOL_DEFINITION" not in cls.__dict__:
            raise TypeError(
                f"Tool '{cls.__name__}' must define TOOL_DEFINITION class variable. "
                f"See tools/base_tool.py for the required format."
            )

        # Validate TOOL_DEFINITION structure
        tool_def = cls.TOOL_DEFINITION
        if not isinstance(tool_def, dict):
            raise TypeError(f"TOOL_DEFINITION in '{cls.__name__}' must be a dictionary")

        required_keys = ["name", "description", "input_schema"]
        missing_keys = [key for key in required_keys if key not in tool_def]
        if missing_keys:
            raise ValueError(
                f"TOOL_DEFINITION in '{cls.__name__}' is missing required keys: {missing_keys}"
            )

    @classmethod
    @abstractmethod
    def run(cls, **kwargs) -> dict[str, Any]:
        """
        Execute the tool with the given parameters.

        This method must be implemented by all subclasses.

        Args:
            **kwargs: Tool-specific parameters defined in TOOL_DEFINITION's input_schema

        Returns:
            Dictionary with tool execution results. Should typically include:
            - success: bool indicating if the operation succeeded
            - Additional tool-specific data

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        raise NotImplementedError(f"Tool '{cls.__name__}' must implement run() method")
