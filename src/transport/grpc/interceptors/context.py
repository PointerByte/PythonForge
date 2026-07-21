"""Translates gRPC metadata into the same :class:`RequestContext` HTTP uses.

This is the gRPC counterpart of
``pythonforge.transport.http.middleware.RequestContextMiddleware``: the same
header names (``x-request-id``, ``traceparent``, ``tracestate``) carry the
same meaning, and a handler reads them through the identical API regardless
of which transport delivered the call.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from ....context import RequestContext, TraceContext
from .base import HandlerWrappingInterceptor


def _metadata_value(context: Any, key: str) -> str | None:
    metadata = context.invocation_metadata()
    if not metadata:
        return None
    for entry in metadata:
        if entry.key.lower() == key:
            value: str = entry.value
            return value
    return None


def read_context_from_metadata(context: Any) -> tuple[str, TraceContext, float | None]:
    """Extract request id, trace context and deadline from an RPC's metadata."""
    request_id = _metadata_value(context, "x-request-id") or str(uuid.uuid4())

    trace_context = None
    if traceparent := _metadata_value(context, "traceparent"):
        trace_context = TraceContext.from_traceparent(traceparent)
        if trace_context and (tracestate := _metadata_value(context, "tracestate")):
            trace_context = TraceContext(
                trace_id=trace_context.trace_id,
                parent_id=trace_context.parent_id,
                trace_flags=trace_context.trace_flags,
                tracestate=TraceContext.parse_tracestate(tracestate),
            )
    if trace_context is None:
        trace_context = TraceContext.new()

    # gRPC gives the remaining time; RequestContext stores an absolute epoch
    # deadline so HTTP and gRPC downstream calls agree on the same units.
    deadline: float | None = None
    remaining = context.time_remaining()
    if remaining is not None:
        import time

        deadline = time.time() + remaining

    return request_id, trace_context, deadline


class RequestContextInterceptor(HandlerWrappingInterceptor):
    """Binds a :class:`RequestContext` for the duration of every RPC."""

    async def wrap_unary(self, behavior: Any, request: Any, context: Any, method: str) -> Any:
        ctx = RequestContext()
        request_id, trace_context, deadline = read_context_from_metadata(context)
        with ctx.bind(request_id=request_id, trace_context=trace_context, deadline=deadline):
            context.set_trailing_metadata((("x-request-id", request_id),))
            return await behavior(request, context)

    async def wrap_stream(
        self, behavior: Any, request: Any, context: Any, method: str
    ) -> AsyncIterator[Any]:
        ctx = RequestContext()
        request_id, trace_context, deadline = read_context_from_metadata(context)
        with ctx.bind(request_id=request_id, trace_context=trace_context, deadline=deadline):
            context.set_trailing_metadata((("x-request-id", request_id),))
            async for response in behavior(request, context):
                yield response
