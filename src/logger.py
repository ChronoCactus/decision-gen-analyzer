"""Logging configuration for Decision Analyzer."""

import logging
import sys
from typing import Any

import structlog

from src.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure structlog
    if settings.log_format == "json":
        # JSON logging for production
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # Human-readable logging for development
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


class ConsoleRenderer:
    """Custom console renderer with colors."""

    def __init__(self, colors: bool = True):
        self.colors = colors

    def __call__(self, logger, name, event_dict):
        """Render log entry for console output."""
        level = event_dict.get("level", "info")
        timestamp = event_dict.get("timestamp", "")
        logger_name = event_dict.get("logger", "")
        event = event_dict.get("event", "")

        # Remove processed fields
        remaining = {
            k: v
            for k, v in event_dict.items()
            if k not in {"level", "timestamp", "logger", "event"}
        }

        # Format message
        if self.colors:
            level_colors = {
                "debug": "\033[36m",  # Cyan
                "info": "\033[32m",  # Green
                "warning": "\033[33m",  # Yellow
                "error": "\033[31m",  # Red
                "critical": "\033[35m",  # Magenta
            }
            reset = "\033[0m"
            color = level_colors.get(level.lower(), "")
            level_str = f"{color}{level.upper()}{reset}"
        else:
            level_str = level.upper()

        parts = [f"{timestamp} {level_str} {logger_name}: {event}"]

        if remaining:
            parts.append(f" {remaining}")

        return "".join(parts)


def get_logger(name: str) -> Any:
    """Get a configured logger instance."""
    return structlog.get_logger(name)
