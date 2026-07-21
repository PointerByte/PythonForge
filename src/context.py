"""Transport-agnostic request context shared by the HTTP and gRPC adapters.

Everything here is backed by :mod:`contextvars` rather than instance state, so
any number of :class:`RequestContext` objects transparently observe the same
values for the currently executing asyncio task. Each incoming request runs in
its own task (created by the ASGI server / anyio), so values set here never
leak across concurrent requests as long as callers avoid mutating containers
returned from getters in place -- getters therefore hand back copies, and
mutation only ever happens through ``ContextVar.set()`` with a brand-new
object, never in place, so a task that never touches a var keeps observing the
untouched default.
"""

from __future__ import annotations

import contextvars
import re
import secrets
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

_VERSION_RE = re.compile(r"^[0-9a-f]{2}$")
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_PARENT_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_FLAGS_RE = re.compile(r"^[0-9a-f]{2}$")
_ZERO_TRACE_ID = "0" * 32
_ZERO_PARENT_ID = "0" * 16


@dataclass(frozen=True)
class TraceContext:
    """W3C Trace Context (https://www.w3.org/TR/trace-context/) carrier."""

    trace_id: str
    parent_id: str = field(default_factory=lambda: secrets.token_hex(8))
    trace_flags: str = "01"
    tracestate: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _TRACE_ID_RE.match(self.trace_id) or self.trace_id == _ZERO_TRACE_ID:
            raise ValueError(f"invalid W3C trace-id: {self.trace_id!r}")
        if not _PARENT_ID_RE.match(self.parent_id) or self.parent_id == _ZERO_PARENT_ID:
            raise ValueError(f"invalid W3C parent-id: {self.parent_id!r}")
        if not _FLAGS_RE.match(self.trace_flags):
            raise ValueError(f"invalid W3C trace-flags: {self.trace_flags!r}")

    def to_traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.parent_id}-{self.trace_flags}"

    def to_tracestate(self) -> str:
        return ",".join(f"{key}={value}" for key, value in self.tracestate.items())

    @classmethod
    def new(cls) -> TraceContext:
        """Start a fresh root trace (used when no valid traceparent is present)."""
        return cls(trace_id=secrets.token_hex(16))

    @classmethod
    def from_traceparent(cls, traceparent: str) -> TraceContext | None:
        """Parse a ``traceparent`` header value, or ``None`` if it is malformed.

        Per the W3C spec, a malformed traceparent must never be rejected with
        an error that aborts the request -- callers should fall back to
        :meth:`new` instead of propagating an invalid value downstream.
        """
        parts = traceparent.strip().split("-")
        if len(parts) < 4:
            return None
        version, trace_id, parent_id, flags = parts[0], parts[1], parts[2], parts[3]
        if not _VERSION_RE.match(version) or version == "ff":
            return None
        try:
            return cls(trace_id=trace_id, parent_id=parent_id, trace_flags=flags)
        except ValueError:
            return None

    @staticmethod
    def parse_tracestate(tracestate: str) -> dict[str, str]:
        """Best-effort parse of a ``tracestate`` header; malformed members are dropped."""
        result: dict[str, str] = {}
        for member in tracestate.split(","):
            if "=" not in member:
                continue
            key, _, value = member.partition("=")
            key, value = key.strip(), value.strip()
            if key and value:
                result[key] = value
        return result


@dataclass(frozen=True)
class DownstreamCall:
    """A single outbound call made while handling the current request."""

    system: str
    process: str
    method: str
    destination: str
    status: str
    latency_ms: float


_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pythonforge_request_id", default=None
)
_trace_context: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "pythonforge_trace_context", default=None
)
_claims: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "pythonforge_claims", default=None
)
_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "pythonforge_deadline", default=None
)
_attributes: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "pythonforge_attributes", default=None
)
_downstream_processes: contextvars.ContextVar[tuple[DownstreamCall, ...]] = contextvars.ContextVar(
    "pythonforge_downstream_processes", default=()
)

_UNSET: Any = object()


class RequestContext:
    """Proxy over the current task's request-scoped contextvars.

    Instances carry no state of their own -- constructing one is cheap and
    every instance observes the same values for the running asyncio task.
    Reusable/domain logic should depend on this type, never on a framework's
    ``Request`` or gRPC ``ServicerContext``.
    """

    @property
    def request_id(self) -> str | None:
        return _request_id.get()

    @request_id.setter
    def request_id(self, value: str | None) -> None:
        _request_id.set(value)

    @property
    def trace_context(self) -> TraceContext | None:
        return _trace_context.get()

    @trace_context.setter
    def trace_context(self, value: TraceContext | None) -> None:
        _trace_context.set(value)

    @property
    def claims(self) -> dict[str, Any] | None:
        claims = _claims.get()
        return dict(claims) if claims is not None else None

    @claims.setter
    def claims(self, value: dict[str, Any] | None) -> None:
        _claims.set(dict(value) if value is not None else None)

    @property
    def deadline(self) -> float | None:
        return _deadline.get()

    @deadline.setter
    def deadline(self, value: float | None) -> None:
        _deadline.set(value)

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(_attributes.get() or {})

    def merge_attributes(self, **attributes: Any) -> None:
        current = dict(_attributes.get() or {})
        current.update(attributes)
        _attributes.set(current)

    @property
    def downstream_processes(self) -> tuple[DownstreamCall, ...]:
        return _downstream_processes.get()

    def add_downstream_call(self, call: DownstreamCall) -> None:
        _downstream_processes.set((*_downstream_processes.get(), call))

    @contextmanager
    def bind(
        self,
        *,
        request_id: str | None = _UNSET,
        trace_context: TraceContext | None = _UNSET,
        claims: dict[str, Any] | None = _UNSET,
        deadline: float | None = _UNSET,
        attributes: dict[str, Any] | None = _UNSET,
    ) -> Iterator[RequestContext]:
        """Scoped, auto-resetting binding -- the previous values are restored on exit.

        Preferred over the plain property setters in middleware/interceptors,
        since it guarantees isolation even if the underlying task is reused.
        """
        tokens: list[tuple[contextvars.ContextVar[Any], contextvars.Token[Any]]] = []
        if request_id is not _UNSET:
            tokens.append((_request_id, _request_id.set(request_id)))
        if trace_context is not _UNSET:
            tokens.append((_trace_context, _trace_context.set(trace_context)))
        if claims is not _UNSET:
            tokens.append((_claims, _claims.set(dict(claims) if claims is not None else None)))
        if deadline is not _UNSET:
            tokens.append((_deadline, _deadline.set(deadline)))
        if attributes is not _UNSET:
            tokens.append((_attributes, _attributes.set(dict(attributes or {}))))
        try:
            yield self
        finally:
            for var, token in reversed(tokens):
                var.reset(token)
