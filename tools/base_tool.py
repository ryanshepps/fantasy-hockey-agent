#!/usr/bin/env python3
"""Base class for Fantasy Hockey tools."""

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class BaseTool(ABC):
    """Abstract base class for fantasy hockey tools."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]]

    def __init_subclass__(cls, **kwargs):
        """Validate that subclasses define TOOL_DEFINITION."""
        super().__init_subclass__(**kwargs)

        if "TOOL_DEFINITION" not in cls.__dict__:
            raise TypeError(f"Tool '{cls.__name__}' must define TOOL_DEFINITION")

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
        """Execute the tool with the given parameters."""
        raise NotImplementedError(f"Tool '{cls.__name__}' must implement run() method")
