from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from ...context import RequestContext, TraceContext
from ...logger import get_logger, log_event

logger = get_logger("pythonforge.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populates :class:`RequestContext` from headers and logs request completion.

    Binds request id, W3C trace context and deadline for the duration of the
    request via :meth:`RequestContext.bind`, so nested calls (e.g. through
    ``ForgeClient``) observe them, and resets them on the way out.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        ctx = RequestContext()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        trace_context = None
        if traceparent := request.headers.get("traceparent"):
            trace_context = TraceContext.from_traceparent(traceparent)
            if trace_context and (tracestate := request.headers.get("tracestate")):
                trace_context = TraceContext(
                    trace_id=trace_context.trace_id,
                    parent_id=trace_context.parent_id,
                    trace_flags=trace_context.trace_flags,
                    tracestate=TraceContext.parse_tracestate(tracestate),
                )
        if trace_context is None:
            trace_context = TraceContext.new()

        deadline = None
        if deadline_header := request.headers.get("x-deadline"):
            try:
                deadline = float(deadline_header)
            except ValueError:
                deadline = None

        start = time.perf_counter()
        with ctx.bind(request_id=request_id, trace_context=trace_context, deadline=deadline):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled exception escaped route handlers")
                response = JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "code": 500,
                            "message": "internal server error",
                            "request_id": request_id,
                        }
                    },
                )
            latency_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-Id"] = request_id
            log_event(
                logger,
                logging.INFO,
                "request finished",
                process="http",
                method=request.method,
                latency_ms=latency_ms,
                details={"path": request.url.path, "status_code": response.status_code},
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Single-process, in-memory fixed-window rate limiter, keyed by client IP.

    Meant as a basic default, not a distributed rate limiter -- state is not
    shared across workers/processes and resets on restart.
    """

    def __init__(
        self,
        app: object,
        *,
        max_requests: int,
        window_seconds: float,
        exempt_paths: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._exempt_paths = exempt_paths
        self._hits: dict[str, deque[float]] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits.setdefault(client_ip, deque())
        while window and now - window[0] > self._window_seconds:
            window.popleft()

        if len(window) >= self._max_requests:
            retry_after = max(0.0, self._window_seconds - (now - window[0]))
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": HTTP_429_TOO_MANY_REQUESTS,
                        "message": "rate limit exceeded",
                        "request_id": RequestContext().request_id,
                    }
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        window.append(now)
        return await call_next(request)
