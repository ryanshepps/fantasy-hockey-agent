#!/usr/bin/env python3
"""
Retrieve email history from the storage file.

This tool allows the agent to query past emails to avoid repeating
suggestions and to track trends over time.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, ClassVar

from tools.base_tool import BaseTool


class GetRecommendationHistory(BaseTool):
    """Tool for retrieving past sent emails."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "get_recommendation_history",
        "description": "Retrieve past sent emails from history. Use this to check what was recommended in previous weeks to avoid repeating suggestions and to track player trends over time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks_back": {
                    "type": "integer",
                    "description": "Number of weeks of history to retrieve (default 4)",
                    "default": 4,
                },
                "search_term": {
                    "type": "string",
                    "description": "Optional - filter to only emails mentioning this term (case insensitive)",
                },
            },
            "required": [],
        },
    }

    @classmethod
    def run(cls, weeks_back: int = 4, search_term: str | None = None) -> dict[str, Any]:
        """
        Retrieve email history.

        Args:
            weeks_back: Number of weeks of history to retrieve (default 4)
            search_term: Optional - filter to only emails containing this term

        Returns:
            Dictionary with success status and history data
        """
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            history_file = os.path.join(project_root, "data", "recommendations_history.json")

            if not os.path.exists(history_file):
                return {
                    "success": True,
                    "message": "No email history found yet",
                    "history": [],
                    "total_entries": 0,
                }

            with open(history_file) as f:
                history = json.load(f)

            if weeks_back:
                cutoff_date = datetime.now() - timedelta(weeks=weeks_back)
                history = [
                    entry
                    for entry in history
                    if datetime.fromisoformat(entry["timestamp"]) >= cutoff_date
                ]

            if search_term:
                search_lower = search_term.lower()
                history = [
                    entry
                    for entry in history
                    if search_lower in entry.get("subject", "").lower()
                    or search_lower in entry.get("body", "").lower()
                ]

            history.sort(key=lambda x: x["timestamp"], reverse=True)

            return {
                "success": True,
                "message": f"Retrieved {len(history)} email entries",
                "history": history,
                "total_entries": len(history),
                "weeks_back": weeks_back,
                "filtered_by_search": search_term,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to retrieve email history: {e!s}",
                "history": [],
            }


def format_history_summary(history_data: dict[str, Any]) -> str:
    """
    Format history data into a readable text summary.

    Args:
        history_data: Output from get_recommendation_history()

    Returns:
        Formatted string summary
    """
    if not history_data.get("success"):
        return f"Error: {history_data.get('message', 'Unknown error')}"

    history = history_data.get("history", [])
    if not history:
        return "No email history available."

    summary_lines = [f"Email History ({len(history)} entries):", ""]

    for entry in history:
        timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M")
        entry_date = entry.get("date", "Unknown date")
        summary_lines.append(f"=== Email from {entry_date} (sent {timestamp}) ===")
        summary_lines.append(f"Subject: {entry.get('subject', 'No subject')}")
        summary_lines.append("")
        summary_lines.append(entry.get("body", "No body content"))
        summary_lines.append("")
        summary_lines.append("=" * 60)
        summary_lines.append("")

    return "\n".join(summary_lines)


if __name__ == "__main__":
    print("Testing get_recommendation_history()...\n")

    result = get_recommendation_history(weeks_back=4)
    print(json.dumps(result, indent=2))

    print("\n\nFormatted Summary:\n")
    print(format_history_summary(result))

    print("\n\n=== Testing search term filter ===\n")
    result2 = get_recommendation_history(weeks_back=4, search_term="McDavid")
    print(format_history_summary(result2))
