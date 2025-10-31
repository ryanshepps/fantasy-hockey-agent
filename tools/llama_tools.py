"""Wrap existing fantasy tools as LlamaIndex BaseTool implementations."""

import logging

from llama_index.core.tools import FunctionTool

from fantasy_tools import TOOL_FUNCTIONS

logger = logging.getLogger(__name__)


def GetCurrentRosterTool() -> FunctionTool:
    """LlamaIndex wrapper for get_current_roster."""
    return FunctionTool.from_defaults(
        fn=TOOL_FUNCTIONS["get_current_roster"],
        name="get_current_roster",
        description="Get the current fantasy hockey roster from Yahoo API",
    )


def GetTeamScheduleTool(weeks: int = 2) -> FunctionTool:
    """LlamaIndex wrapper for get_team_schedule."""
    def _get_team_schedule(weeks: int = weeks) -> dict:
        logger.info(f"Calling get_team_schedule(weeks={weeks}) via LlamaIndex")
        return TOOL_FUNCTIONS["get_team_schedule"](weeks=weeks)

    return FunctionTool.from_defaults(
        fn=_get_team_schedule,
        name="get_team_schedule",
        description=f"Get team schedules for next {weeks} weeks from NHL API",
    )


def AssessDroppablePlayersTool() -> FunctionTool:
    """LlamaIndex wrapper for assess_droppable_players."""
    return FunctionTool.from_defaults(
        fn=TOOL_FUNCTIONS["assess_droppable_players"],
        name="assess_droppable_players",
        description="Assess which players on roster are droppable vs keepers",
    )


def FindStreamingMatchesTool() -> FunctionTool:
    """LlamaIndex wrapper for find_streaming_matches."""
    return FunctionTool.from_defaults(
        fn=TOOL_FUNCTIONS["find_streaming_matches"],
        name="find_streaming_matches",
        description="Find optimal streaming matches given droppable players and schedule",
    )


def SendEmailTool() -> FunctionTool:
    """LlamaIndex wrapper for send_email."""
    return FunctionTool.from_defaults(
        fn=TOOL_FUNCTIONS["send_email"],
        name="send_email",
        description="Send HTML email with recommendations",
    )


def SaveRecommendationsTool() -> FunctionTool:
    """LlamaIndex wrapper for save_recommendations."""
    return FunctionTool.from_defaults(
        fn=TOOL_FUNCTIONS["save_recommendations"],
        name="save_recommendations",
        description="Save recommendations to history file",
    )


def get_llama_tools() -> list[FunctionTool]:
    """
    Get all LlamaIndex-wrapped tools.

    Returns:
        List of FunctionTool instances
    """
    return [
        GetCurrentRosterTool(),
        GetTeamScheduleTool(),
        AssessDroppablePlayersTool(),
        FindStreamingMatchesTool(),
        SendEmailTool(),
        SaveRecommendationsTool(),
    ]
