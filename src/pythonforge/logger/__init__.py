from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from ..config import LoggerConfig
from .formatter import ContextFilter, JSONFormatter, TextFormatter
from .sanitizer import redact

DEFAULT_LOGGER_NAME = "pythonforge"


def configure_logging(
    config: LoggerConfig, *, logger_name: str = DEFAULT_LOGGER_NAME
) -> logging.Logger:
    """(Re)configure the named logger from a :class:`LoggerConfig`.

    Idempotent: calling it again (e.g. on every ``create_app``) replaces the
    previous handlers instead of stacking duplicates.
    """
    logger = logging.getLogger(logger_name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(config.level)
    logger.propagate = False

    formatter: logging.Formatter = (
        JSONFormatter(config.sensitive_keys)
        if config.format == "json"
        else TextFormatter(config.sensitive_keys)
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(ContextFilter())
    logger.addHandler(stream_handler)

    if config.file_path:
        file_handler = RotatingFileHandler(
            config.file_path, maxBytes=config.max_bytes, backupCount=config.backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(ContextFilter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = DEFAULT_LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    process: str | None = None,
    method: str | None = None,
    latency_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit a schema-shaped log line without colliding with reserved ``LogRecord`` names."""
    logger.log(
        level,
        message,
        extra={
            "process_name": process,
            "method": method,
            "latency_ms": latency_ms,
            "details": details or {},
        },
    )


__all__ = ["configure_logging", "get_logger", "log_event", "redact"]
