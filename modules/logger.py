#!/usr/bin/env python3
"""
Centralized logging module for fantasy hockey agent.

Provides consistent logging across all tools and tracks:
- Token usage per API call and tool
- Execution time per tool
- Summary statistics for optimization analysis

Usage:
    from modules.logger import AgentLogger

    logger = AgentLogger.get_logger(__name__)
    logger.info("Starting tool execution")

    # Track token usage
    AgentLogger.log_token_usage(
        step="get_available_players",
        input_tokens=1500,
        output_tokens=300,
        cache_read=1000
    )

    # Get summary report
    report = AgentLogger.get_usage_summary()
"""

import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar


@dataclass
class TokenUsageRecord:
    """Record of token usage for a single operation."""

    timestamp: str
    step: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    execution_time_ms: float | None = None

    def __post_init__(self):
        """Calculate total tokens after initialization."""
        self.total_tokens = self.input_tokens + self.output_tokens + self.cache_creation_tokens


class AgentLogger:
    """
    Centralized logger for the fantasy hockey agent.

    Provides consistent logging interface and token usage tracking.
    """

    # Class-level storage for token usage records
    _usage_records: ClassVar[list[TokenUsageRecord]] = []
    _session_start: datetime = datetime.now()
    _loggers: ClassVar[dict[str, logging.Logger]] = {}

    # Log file paths
    _log_dir = Path("logs")
    _log_file = _log_dir / f"agent_{_session_start.strftime('%Y%m%d_%H%M%S')}.log"
    _token_log_file = _log_dir / f"tokens_{_session_start.strftime('%Y%m%d_%H%M%S')}.json"

    @classmethod
    def _ensure_log_dir(cls):
        """Ensure the log directory exists."""
        cls._log_dir.mkdir(exist_ok=True)

    @classmethod
    def _configure_root_logger(cls):
        """Configure the root logger to capture all logs from third-party libraries."""
        cls._ensure_log_dir()

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Clear any existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Console handler with consistent format
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_format)

        # File handler with detailed format
        file_handler = logging.FileHandler(cls._log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)

        # Add handlers to root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    @classmethod
    def get_logger(cls, name: str, level: int = logging.INFO) -> logging.Logger:
        """
        Get or create a logger with consistent formatting.

        Args:
            name: Logger name (typically __name__ from calling module)
            level: Logging level (default: INFO)

        Returns:
            Configured logger instance
        """
        # Configure root logger on first call
        if not cls._loggers:
            cls._configure_root_logger()

        if name in cls._loggers:
            return cls._loggers[name]

        # Get logger (will inherit from root logger)
        logger = logging.getLogger(name)
        logger.setLevel(level)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def log_token_usage(
        cls,
        step: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        execution_time_ms: float | None = None,
    ):
        """
        Log token usage for a specific step.

        Args:
            step: Name of the step (e.g., "get_roster", "claude_api_call_1")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_creation_tokens: Number of tokens used to create cache
            cache_read_tokens: Number of tokens read from cache
            execution_time_ms: Execution time in milliseconds
        """
        record = TokenUsageRecord(
            timestamp=datetime.now().isoformat(),
            step=step,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            execution_time_ms=execution_time_ms,
        )

        cls._usage_records.append(record)

        # Also log to file immediately
        cls._save_token_records()

        # Log summary to console
        logger = cls.get_logger("token_tracker")
        logger.info(
            f"[{step}] Tokens: in={input_tokens}, out={output_tokens}, "
            f"cache_create={cache_creation_tokens}, cache_read={cache_read_tokens}, "
            f"total={record.total_tokens}"
        )

    @classmethod
    def _save_token_records(cls):
        """Save token usage records to JSON file."""
        cls._ensure_log_dir()

        records_dict = {
            "session_start": cls._session_start.isoformat(),
            "records": [asdict(r) for r in cls._usage_records],
        }

        with open(cls._token_log_file, "w") as f:
            json.dump(records_dict, f, indent=2)

    @classmethod
    def get_usage_summary(cls, detailed: bool = False) -> dict[str, Any]:
        """
        Get summary statistics of token usage.

        Args:
            detailed: Include detailed per-step breakdown

        Returns:
            Dictionary with usage statistics
        """
        if not cls._usage_records:
            return {"total_calls": 0, "total_tokens": 0, "message": "No token usage recorded yet"}

        # Calculate totals
        total_input = sum(r.input_tokens for r in cls._usage_records)
        total_output = sum(r.output_tokens for r in cls._usage_records)
        total_cache_creation = sum(r.cache_creation_tokens for r in cls._usage_records)
        total_cache_read = sum(r.cache_read_tokens for r in cls._usage_records)
        total_tokens = sum(r.total_tokens for r in cls._usage_records)

        # Calculate per-step breakdowns
        step_stats = {}
        for record in cls._usage_records:
            if record.step not in step_stats:
                step_stats[record.step] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                    "total_tokens": 0,
                    "execution_time_ms": [],
                }

            stats = step_stats[record.step]
            stats["calls"] += 1
            stats["input_tokens"] += record.input_tokens
            stats["output_tokens"] += record.output_tokens
            stats["cache_creation_tokens"] += record.cache_creation_tokens
            stats["cache_read_tokens"] += record.cache_read_tokens
            stats["total_tokens"] += record.total_tokens

            if record.execution_time_ms:
                stats["execution_time_ms"].append(record.execution_time_ms)

        # Calculate averages for execution time
        for _step, stats in step_stats.items():
            if stats["execution_time_ms"]:
                times = stats["execution_time_ms"]
                stats["avg_execution_time_ms"] = sum(times) / len(times)
                stats["min_execution_time_ms"] = min(times)
                stats["max_execution_time_ms"] = max(times)
            del stats["execution_time_ms"]  # Remove raw list

        # Sort steps by total tokens (descending)
        sorted_steps = sorted(step_stats.items(), key=lambda x: x[1]["total_tokens"], reverse=True)

        summary = {
            "session_start": cls._session_start.isoformat(),
            "session_duration": str(datetime.now() - cls._session_start),
            "total_calls": len(cls._usage_records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_creation_tokens": total_cache_creation,
            "total_cache_read_tokens": total_cache_read,
            "total_tokens": total_tokens,
            "cache_efficiency": {
                "tokens_saved_by_cache": total_cache_read,
                "cache_creation_cost": total_cache_creation,
                "net_cache_benefit": total_cache_read - total_cache_creation,
            },
            "top_token_consumers": [
                {"step": step, **stats}
                for step, stats in sorted_steps[:10]  # Top 10
            ],
        }

        if detailed:
            summary["all_steps"] = dict(sorted_steps)
            summary["detailed_records"] = [asdict(r) for r in cls._usage_records]

        return summary

    @classmethod
    def print_usage_summary(cls):
        """Print a formatted usage summary to console."""
        summary = cls.get_usage_summary()

        print("\n" + "=" * 80)
        print("TOKEN USAGE SUMMARY")
        print("=" * 80)
        print(f"Session Start: {summary['session_start']}")
        print(f"Duration: {summary['session_duration']}")
        print(f"Total API Calls: {summary['total_calls']}")
        print("\nToken Breakdown:")
        print(f"  Input Tokens:         {summary['total_input_tokens']:>10,}")
        print(f"  Output Tokens:        {summary['total_output_tokens']:>10,}")
        print(f"  Cache Creation:       {summary['total_cache_creation_tokens']:>10,}")
        print(f"  Cache Read (saved):   {summary['total_cache_read_tokens']:>10,}")
        print(f"  {'─' * 40}")
        print(f"  Total Tokens:         {summary['total_tokens']:>10,}")

        cache_eff = summary["cache_efficiency"]
        print("\nCache Efficiency:")
        print(f"  Tokens Saved:         {cache_eff['tokens_saved_by_cache']:>10,}")
        print(f"  Creation Cost:        {cache_eff['cache_creation_cost']:>10,}")
        print(f"  Net Benefit:          {cache_eff['net_cache_benefit']:>10,}")

        print("\nTop Token Consumers:")
        print(f"{'─' * 80}")
        print(f"{'Step':<30} {'Calls':<8} {'Total Tokens':<15} {'Avg/Call':<12}")
        print(f"{'─' * 80}")

        for consumer in summary["top_token_consumers"]:
            step = consumer["step"]
            calls = consumer["calls"]
            total = consumer["total_tokens"]
            avg = total / calls
            print(f"{step:<30} {calls:<8} {total:<15,} {avg:<12,.1f}")

        print("=" * 80)
        print("Log files saved to:")
        print(f"  Main log: {cls._log_file}")
        print(f"  Token log: {cls._token_log_file}")
        print("=" * 80 + "\n")

    @classmethod
    def set_library_log_level(cls, library_name: str, level: int):
        """
        Set the logging level for a specific library.

        Useful for suppressing noisy third-party libraries.

        Args:
            library_name: Name of the library (e.g., 'yfpy', 'urllib3')
            level: Logging level (e.g., logging.WARNING, logging.ERROR)

        Example:
            AgentLogger.set_library_log_level('yfpy', logging.WARNING)
        """
        library_logger = logging.getLogger(library_name)
        library_logger.setLevel(level)

    @classmethod
    def reset(cls):
        """Reset all tracking data (useful for testing)."""
        cls._usage_records = []
        cls._session_start = datetime.now()


# Convenience function for backwards compatibility
def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a logger instance (convenience wrapper).

    Args:
        name: Logger name
        level: Logging level

    Returns:
        Configured logger
    """
    return AgentLogger.get_logger(name, level)
