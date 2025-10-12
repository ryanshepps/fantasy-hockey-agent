#!/usr/bin/env python3
"""Email utility for sending plain text emails with retry logic."""

import os
import smtplib
import time
from email.mime.text import MIMEText
from email.utils import parseaddr
from typing import Any

from dotenv import load_dotenv

from tools.base_tool import BaseTool
from modules.tool_logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# Email configuration
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", EMAIL_FROM)
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "30"))
SMTP_RETRY_ATTEMPTS = int(os.getenv("SMTP_RETRY_ATTEMPTS", "3"))
DRY_RUN = os.getenv("DRY_RUN", "").lower() == "true"


def _validate_email_address(email: str) -> bool:
    """Validate email address format."""
    if not email:
        return False
    name, addr = parseaddr(email)
    return "@" in addr and "." in addr.split("@")[1]


def _validate_configuration() -> dict[str, Any]:
    """Validate required environment variables are set."""
    errors = []

    if not EMAIL_FROM:
        errors.append("EMAIL_FROM is not set")
    elif not _validate_email_address(EMAIL_FROM):
        errors.append(f"EMAIL_FROM is not a valid email address: {EMAIL_FROM}")

    if not EMAIL_TO:
        errors.append("EMAIL_TO is not set")
    elif not _validate_email_address(EMAIL_TO):
        errors.append(f"EMAIL_TO is not a valid email address: {EMAIL_TO}")

    if not EMAIL_PASSWORD:
        errors.append("EMAIL_PASSWORD is not set")

    if not SMTP_USERNAME:
        errors.append("SMTP_USERNAME could not be determined")

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "message": "Email configuration is invalid. Please check your .env file.",
        }

    return {"valid": True}


class SendEmail(BaseTool):
    """Tool for sending emails with fantasy hockey recommendations."""

    # Tool definition for Claude Agent SDK
    TOOL_DEFINITION = {
        "name": "send_email",
        "description": "Send an email with fantasy hockey recommendations. Use plain text with markdown-style formatting (*bold*, _italic_) for readability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {
                    "type": "string",
                    "description": "Plain text email body with recommendations. Use markdown-style emphasis: *asterisks* for bold, _underscores_ for italic. Separate sections with blank lines for readability.",
                },
            },
            "required": ["subject", "body"],
        },
    }

    @classmethod
    def run(cls, subject: str, body: str) -> dict[str, Any]:
        """Send plain text email with retry logic and error handling."""
        # Validate configuration
        validation = _validate_configuration()
        if not validation["valid"]:
            error_msg = "; ".join(validation["errors"])
            logger.error(f"Configuration validation failed: {error_msg}")
            return {
                "success": False,
                "error": validation["message"],
                "details": validation["errors"],
                "smtp_server": SMTP_SERVER,
                "smtp_port": SMTP_PORT,
            }

        # Dry run mode
        if DRY_RUN:
            logger.info("DRY_RUN mode enabled - email will not be sent")
            logger.info(f"Subject: {subject}")
            logger.info(f"From: {EMAIL_FROM}")
            logger.info(f"To: {EMAIL_TO}")
            logger.info(f"Body length: {len(body)} characters")
            return {
                "success": True,
                "message": f"DRY_RUN: Email would be sent to {EMAIL_TO}",
                "smtp_server": SMTP_SERVER,
                "smtp_port": SMTP_PORT,
                "dry_run": True,
            }

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(1, SMTP_RETRY_ATTEMPTS + 1):
            try:
                logger.info(
                    f"Attempt {attempt}/{SMTP_RETRY_ATTEMPTS}: Connecting to {SMTP_SERVER}:{SMTP_PORT}"
                )

                # Create message
                msg = MIMEText(body, "plain", "utf-8")
                msg["Subject"] = subject
                msg["From"] = EMAIL_FROM
                msg["To"] = EMAIL_TO

                # Connect and send
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()

                    logger.debug(f"Authenticating as: {SMTP_USERNAME}")
                    server.login(SMTP_USERNAME, EMAIL_PASSWORD)

                    logger.info(f"Sending email to: {EMAIL_TO}")
                    server.send_message(msg)

                logger.info(f"Email sent successfully to {EMAIL_TO} via {SMTP_SERVER}")
                return {
                    "success": True,
                    "message": f"Email sent to {EMAIL_TO} via {SMTP_SERVER}",
                    "smtp_server": SMTP_SERVER,
                    "smtp_port": SMTP_PORT,
                    "attempt": attempt,
                }

            except smtplib.SMTPAuthenticationError as e:
                # Authentication errors should not be retried
                logger.error(f"SMTP authentication failed: {e}")
                return {
                    "success": False,
                    "error": "SMTP authentication failed. Check EMAIL_PASSWORD and SMTP_USERNAME.",
                    "details": str(e),
                    "smtp_server": SMTP_SERVER,
                    "smtp_port": SMTP_PORT,
                    "attempt": attempt,
                }

            except smtplib.SMTPConnectError as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed: Connection error - {e}")

            except smtplib.SMTPServerDisconnected as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed: Server disconnected - {e}")

            except smtplib.SMTPException as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed: SMTP error - {e}")

            except TimeoutError as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt} failed: Connection timeout after {SMTP_TIMEOUT}s"
                )

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed: Unexpected error - {e}")

            # Exponential backoff before retry (except on last attempt)
            if attempt < SMTP_RETRY_ATTEMPTS:
                wait_time = 2**attempt  # 2, 4, 8 seconds
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

        # All retries failed
        logger.error(f"Failed to send email after {SMTP_RETRY_ATTEMPTS} attempts")
        return {
            "success": False,
            "error": f"Failed to send email after {SMTP_RETRY_ATTEMPTS} attempts",
            "details": str(last_error),
            "smtp_server": SMTP_SERVER,
            "smtp_port": SMTP_PORT,
            "attempt": SMTP_RETRY_ATTEMPTS,
        }


# Export for backwards compatibility
TOOL_DEFINITION = SendEmail.TOOL_DEFINITION
send_email = SendEmail.run
