from llama_index.core.tools import BaseTool

from tools.llama_tools import GetCurrentRosterTool, GetTeamScheduleTool


def test_get_current_roster_tool_is_base_tool():
    """Test that wrapped tool is valid LlamaIndex BaseTool."""
    tool = GetCurrentRosterTool()
    assert isinstance(tool, BaseTool)
    assert tool.metadata.name == "get_current_roster"


def test_get_team_schedule_tool_is_base_tool():
    """Test team schedule tool wrapping."""
    tool = GetTeamScheduleTool()
    assert isinstance(tool, BaseTool)
    assert tool.metadata.name == "get_team_schedule"
