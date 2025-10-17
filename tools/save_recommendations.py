#!/usr/bin/env python3
"""
Save sent email to the history file.

This tool allows the agent to persist emails sent to users for future reference.
"""

import json
import os
from datetime import datetime
from typing import Any, ClassVar

from tools.base_tool import BaseTool


class SaveRecommendations(BaseTool):
    """Tool for saving sent emails to history."""

    TOOL_DEFINITION: ClassVar[dict[str, Any]] = {
        "name": "save_recommendations",
        "description": "Save the sent email to the history file. This should be called AFTER sending the email to persist it for future reference. This allows the agent to remember what it recommended in previous weeks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The subject line of the sent email",
                },
                "body": {
                    "type": "string",
                    "description": "The body content of the sent email",
                },
            },
            "required": ["subject", "body"],
        },
    }

    @classmethod
    def run(cls, subject: str, body: str) -> dict[str, Any]:
        """
        Save sent email to the history file.

        Args:
            subject: The email subject line
            body: The email body content

        Returns:
            Dictionary with success status and message
        """
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            history_file = os.path.join(project_root, "data", "recommendations_history.json")

            if os.path.exists(history_file):
                with open(history_file) as f:
                    history = json.load(f)
            else:
                history = []

            now = datetime.now()
            email_entry = {
                "timestamp": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "subject": subject,
                "body": body,
            }

            history.append(email_entry)

            os.makedirs(os.path.dirname(history_file), exist_ok=True)
            with open(history_file, "w") as f:
                json.dump(history, f, indent=2)

            return {
                "success": True,
                "message": f"Email saved successfully. Total entries in history: {len(history)}",
                "timestamp": email_entry["timestamp"],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to save email: {e!s}",
            }


if __name__ == "__main__":
    test_subject = "Fantasy Hockey Weekly Analysis - Week of Oct 12"
    test_body = """Hi there!

Here are this week's recommendations:

*Connor McDavid* (C, EDM)
He's heating up with 5 goals in last 3 games. Edmonton has 4 games this week.

Consider dropping: _John Doe_ - Cold streak, only 2 games this week."""

    result = save_recommendations(subject=test_subject, body=test_body)
    print(json.dumps(result, indent=2))
