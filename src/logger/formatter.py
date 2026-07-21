"""Formatters and the context-injecting filter shared by every log handler.

Structured fields are passed through ``logging``'s ``extra=`` mechanism using
non-reserved attribute names (``process_name`` rather than ``process``, since
the stdlib ``LogRecord`` already owns ``process``/``processName`` for the OS
PID) -- see :func:`pythonforge.logger.log_event`, the supported entry point
for emitting schema-shaped log lines.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from ..context import RequestContext
from .sanitizer import redact


class ContextFilter(logging.Filter):
    """Injects the current request's trace/request id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = RequestContext()
        trace = ctx.trace_context
        record.trace_id = trace.trace_id if trace else None
        record.request_id = ctx.request_id
        return True


def _schema_payload(record: logging.LogRecord, sensitive_keys: Sequence[str]) -> dict[str, object]:
    details = redact(getattr(record, "details", None) or {}, sensitive_keys)
    if record.exc_info:
        details = {**details, "exception": logging.Formatter().formatException(record.exc_info)}
    return {
        "level": record.levelname,
        "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
        "trace_id": getattr(record, "trace_id", None),
        "request_id": getattr(record, "request_id", None),
        "message": record.getMessage(),
        "details": details,
        "process": getattr(record, "process_name", None),
        "method": getattr(record, "method", None),
        "line": record.lineno,
        "latency_ms": getattr(record, "latency_ms", None),
    }


class JSONFormatter(logging.Formatter):
    def __init__(self, sensitive_keys: Sequence[str] = ()) -> None:
        super().__init__()
        self._sensitive_keys = tuple(sensitive_keys)

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(_schema_payload(record, self._sensitive_keys), default=str)


class TextFormatter(logging.Formatter):
    def __init__(self, sensitive_keys: Sequence[str] = ()) -> None:
        super().__init__()
        self._sensitive_keys = tuple(sensitive_keys)

    def format(self, record: logging.LogRecord) -> str:
        payload = _schema_payload(record, self._sensitive_keys)
        parts = [
            f"{payload['timestamp']}",
            f"[{payload['level']}]",
        ]
        if payload["process"]:
            parts.append(f"process={payload['process']}")
        if payload["method"]:
            parts.append(f"method={payload['method']}")
        if payload["trace_id"]:
            parts.append(f"trace_id={payload['trace_id']}")
        if payload["latency_ms"] is not None:
            parts.append(f"latency_ms={payload['latency_ms']:.2f}")
        parts.append(str(payload["message"]))
        if payload["details"]:
            parts.append(f"details={payload['details']}")
        return " ".join(parts)
