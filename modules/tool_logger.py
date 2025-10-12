#!/usr/bin/env python3
"""Shared logger setup for tools."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from modules.logger import AgentLogger

    def get_logger(name):
        return AgentLogger.get_logger(name)
except ImportError:
    logging.basicConfig(level=logging.INFO)

    def get_logger(name):
        return logging.getLogger(name)
