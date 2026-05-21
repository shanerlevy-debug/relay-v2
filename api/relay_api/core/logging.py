"""Structured logging via structlog.

Dev gets colored console output; everything else gets JSON lines suitable
for journald + CloudWatch / similar aggregators downstream.
"""
from __future__ import annotations

import logging
import sys

import structlog

from relay_api.core.config import settings


def configure_logging() -> None:
    """Wire stdlib logging + structlog. Call once at app startup."""
    level = getattr(logging, settings.RELAY_LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    if settings.RELAY_ENV == "dev":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Return a bound logger. Prefer module-level `log = get_logger(__name__)`."""
    return structlog.get_logger(name)
