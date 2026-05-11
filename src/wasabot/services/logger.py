"""
Structured JSON logging with correlation ID support.

🐍 PYTHON NATIVE: Custom logging.Handler outputs strict flat JSON format
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import UTC, datetime
import json
import logging
from typing import Any
import uuid

# 🐍 PYTHON NATIVE: ContextVar for async-safe correlation ID propagation
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str | None = None) -> str:
    """
    Set correlation ID in current context.

    Args:
        correlation_id: Optional ID to set. If None, generates new UUID.

    Returns:
        The correlation ID that was set.
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_id.set(correlation_id)
    return correlation_id


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs strict JSON log lines.

    🐍 PYTHON NATIVE: Flat structure with no nested correlation_id
    """

    def __init__(self) -> None:
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Map Python log levels to lowercase strings
        level_map = {
            logging.DEBUG: "debug",
            logging.INFO: "info",
            logging.WARNING: "warning",
            logging.ERROR: "error",
            logging.CRITICAL: "critical",
        }
        level_str = level_map.get(record.levelno, "info")

        # Build flat log entry - CORRELATION_ID IS ALWAYS FLAT STRING
        log_entry: dict[str, Any] = {
            "level": level_str,
            "event": record.getMessage(),
            "correlation_id": get_correlation_id() or "",
            "timestamp": datetime.now(UTC).isoformat(),
            "meta": {},
        }

        # Add extra fields to meta if present
        if hasattr(record, "meta") and isinstance(record.meta, dict):
            log_entry["meta"] = record.meta

        # Add exception info if present
        if record.exc_info:
            log_entry["meta"]["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class JSONHandler(logging.StreamHandler[str]):
    """Stream handler that uses JSON formatter."""

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JSONFormatter())


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure root logger with JSON handler.

    Args:
        level: Minimum log level (default: INFO)

    Returns:
        Configured logger instance
    """
    # Remove any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Add JSON handler
    json_handler = JSONHandler()
    json_handler.setLevel(level)
    root_logger.addHandler(json_handler)
    root_logger.setLevel(level)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class CorrelationContext:
    """
    Context manager for setting correlation ID within a scope.

    🐍 PYTHON NATIVE: Context manager pattern for clean async task isolation
    """

    def __init__(self, correlation_id: str | None = None) -> None:
        self._correlation_id = correlation_id
        self._token: Any = None

    def __enter__(self) -> str:
        """Enter context and set correlation ID."""
        if self._correlation_id is None:
            self._correlation_id = str(uuid.uuid4())
        self._token = _correlation_id.set(self._correlation_id)
        return self._correlation_id

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and restore previous correlation ID."""
        if self._token is not None:
            _correlation_id.reset(self._token)
