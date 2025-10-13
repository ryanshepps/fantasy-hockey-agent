#!/usr/bin/env python3
"""
Tool functions for the Fantasy Hockey AI Agent.
These tools allow Claude to interact with Yahoo Fantasy Hockey API and send emails.

Implementations are in the tools/ directory for easy individual testing.
Each tool file contains both the implementation and its TOOL_DEFINITION.
"""

# Import the actual tool implementations and their definitions
from tools.calculate_optimal_streaming import TOOL_DEFINITION as CALCULATE_OPTIMAL_STREAMING_DEF
from tools.calculate_optimal_streaming import calculate_optimal_streaming
from tools.get_available_players import TOOL_DEFINITION as GET_AVAILABLE_PLAYERS_DEF
from tools.get_available_players import get_available_players
from tools.get_player_stats import TOOL_DEFINITION as GET_PLAYER_STATS_DEF
from tools.get_player_stats import get_player_stats
from tools.get_recommendation_history import TOOL_DEFINITION as GET_RECOMMENDATION_HISTORY_DEF
from tools.get_recommendation_history import get_recommendation_history
from tools.get_roster import TOOL_DEFINITION as GET_CURRENT_ROSTER_DEF
from tools.get_roster import get_current_roster
from tools.get_team_schedule import TOOL_DEFINITION as GET_TEAM_SCHEDULE_DEF
from tools.get_team_schedule import get_team_schedule
from tools.save_recommendations import TOOL_DEFINITION as SAVE_RECOMMENDATIONS_DEF
from tools.save_recommendations import save_recommendations
from tools.send_email import TOOL_DEFINITION as SEND_EMAIL_DEF
from tools.send_email import send_email

# Tool definitions for Claude Agent SDK
# These are imported from individual tool files to maintain a single source of truth
TOOLS = [
    GET_AVAILABLE_PLAYERS_DEF,
    GET_CURRENT_ROSTER_DEF,
    SEND_EMAIL_DEF,
    SAVE_RECOMMENDATIONS_DEF,
    GET_RECOMMENDATION_HISTORY_DEF,
    GET_TEAM_SCHEDULE_DEF,
    GET_PLAYER_STATS_DEF,
    CALCULATE_OPTIMAL_STREAMING_DEF,
]


# Tool execution mapping
TOOL_FUNCTIONS = {
    "get_available_players": get_available_players,
    "get_current_roster": get_current_roster,
    "send_email": send_email,
    "save_recommendations": save_recommendations,
    "get_recommendation_history": get_recommendation_history,
    "get_team_schedule": get_team_schedule,
    "get_player_stats": get_player_stats,
    "calculate_optimal_streaming": calculate_optimal_streaming,
}
