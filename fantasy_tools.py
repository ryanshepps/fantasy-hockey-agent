#!/usr/bin/env python3
"""
Tool functions for the Fantasy Hockey AI Agent.
These tools allow Claude to interact with Yahoo Fantasy Hockey API and send emails.

Implementations are in the tools/ directory for easy individual testing.
Each tool file contains both the implementation and its TOOL_DEFINITION.
"""

# Import the actual tool implementations and their definitions
from tools.calculate_optimal_streaming import TOOL_DEFINITION as calculate_optimal_streaming_def
from tools.calculate_optimal_streaming import calculate_optimal_streaming
from tools.get_available_players import TOOL_DEFINITION as get_available_players_def
from tools.get_available_players import get_available_players
from tools.get_player_stats import TOOL_DEFINITION as get_player_stats_def
from tools.get_player_stats import get_player_stats
from tools.get_recommendation_history import TOOL_DEFINITION as get_recommendation_history_def
from tools.get_recommendation_history import get_recommendation_history
from tools.get_roster import TOOL_DEFINITION as get_current_roster_def
from tools.get_roster import get_current_roster
from tools.get_team_schedule import TOOL_DEFINITION as get_team_schedule_def
from tools.get_team_schedule import get_team_schedule
from tools.save_recommendations import TOOL_DEFINITION as save_recommendations_def
from tools.save_recommendations import save_recommendations
from tools.send_email import TOOL_DEFINITION as send_email_def
from tools.send_email import send_email

# Tool definitions for Claude Agent SDK
# These are imported from individual tool files to maintain a single source of truth
TOOLS = [
    get_available_players_def,
    get_current_roster_def,
    send_email_def,
    save_recommendations_def,
    get_recommendation_history_def,
    get_team_schedule_def,
    get_player_stats_def,
    calculate_optimal_streaming_def,
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
