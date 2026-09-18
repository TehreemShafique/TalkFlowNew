"""Structured logging via structlog with request trace-ids."""
from __future__ import annotations

import logging
import sys

import structlog


def _add_user_id(logger, method_name, event_dict):
    cls = event_dict.get("user_id")
    if cls:
        event_dict["user_id"] = str(cls)
    return event_dict


def configure_logging() -> None:
    """Configure the app-wide structlog pipeline once."""
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _add_user_id,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "talkflow") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)