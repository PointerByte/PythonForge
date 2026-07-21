"""The log schema shared by every PythonForge sink, in both HTTP and gRPC.

Fields: ``level``, ``timestamp``, ``trace_id``, ``message``, ``details``,
``process``, ``method``, ``line``, ``latency_ms``. Bodies are never part of
this schema by default -- see ``LoggerConfig.include_body``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_FIELDS = (
    "level",
    "timestamp",
    "trace_id",
    "message",
    "details",
    "process",
    "method",
    "line",
    "latency_ms",
)


@dataclass(frozen=True)
class LogSchema:
    level: str
    timestamp: str
    message: str
    trace_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    process: str | None = None
    method: str | None = None
    line: int | None = None
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in SCHEMA_FIELDS}
