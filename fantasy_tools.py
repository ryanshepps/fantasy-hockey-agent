#!/usr/bin/env python3
"""
Tool functions for the Fantasy Hockey AI Agent.
These tools allow Claude to interact with Yahoo Fantasy Hockey API and send emails.

Implementations are in the tools/ directory for easy individual testing.
Each tool file contains both the implementation and its TOOL_DEFINITION.
"""

# Import the actual tool implementations and their definitions
from tools.assess_droppable_players import TOOL_DEFINITION as ASSESS_DROPPABLE_DEF
from tools.assess_droppable_players import assess_droppable_players
from tools.find_streaming_matches import TOOL_DEFINITION as FIND_STREAMING_DEF
from tools.find_streaming_matches import find_streaming_matches
from tools.get_player_stats import TOOL_DEFINITION as GET_PLAYER_STATS_DEF
from tools.get_player_stats import get_player_stats
from tools.get_players_from_teams import TOOL_DEFINITION as GET_PLAYERS_FROM_TEAMS_DEF
from tools.get_players_from_teams import get_players_from_teams
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
    GET_RECOMMENDATION_HISTORY_DEF,
    GET_CURRENT_ROSTER_DEF,
    GET_TEAM_SCHEDULE_DEF,
    GET_PLAYERS_FROM_TEAMS_DEF,
    ASSESS_DROPPABLE_DEF,
    FIND_STREAMING_DEF,
    GET_PLAYER_STATS_DEF,
    SEND_EMAIL_DEF,
    SAVE_RECOMMENDATIONS_DEF,
]


# Tool execution mapping
TOOL_FUNCTIONS = {
    "get_current_roster": get_current_roster,
    "get_team_schedule": get_team_schedule,
    "get_players_from_teams": get_players_from_teams,
    "assess_droppable_players": assess_droppable_players,
    "find_streaming_matches": find_streaming_matches,
    "get_player_stats": get_player_stats,
    "send_email": send_email,
    "save_recommendations": save_recommendations,
    "get_recommendation_history": get_recommendation_history,
}
