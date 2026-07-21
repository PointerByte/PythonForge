from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from ...config import ClientConfig
from ...context import DownstreamCall, RequestContext
from ...errors import TransportError

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})


class ForgeClient:
    """Async HTTPX client with context propagation, TLS/mTLS, deadlines and retries.

    Returns the raw :class:`httpx.Response` rather than pre-parsed JSON, so it
    stays a thin wrapper over the normal HTTPX API instead of hiding it.
    """

    def __init__(
        self,
        base_url: str,
        config: ClientConfig | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """``transport`` is an injection point for tests (e.g. ``httpx.MockTransport``
        or ``httpx.ASGITransport``); production callers should leave it unset."""
        self._config = config or ClientConfig()
        cfg = self._config

        cert: str | tuple[str, str] | None = None
        if cfg.cert_file and cfg.key_file:
            cert = (cfg.cert_file, cfg.key_file)
        elif cfg.cert_file:
            cert = cfg.cert_file

        verify: bool | str = cfg.ca_file if cfg.ca_file else cfg.verify

        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(cfg.timeout, connect=cfg.connect_timeout),
            verify=verify,
            cert=cert,
            transport=transport,
        )

    async def __aenter__(self) -> ForgeClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        ctx = RequestContext()
        headers: dict[str, str] = dict(kwargs.pop("headers", None) or {})

        if ctx.request_id:
            headers["X-Request-Id"] = ctx.request_id
        if ctx.trace_context:
            headers["traceparent"] = ctx.trace_context.to_traceparent()
            if ctx.trace_context.tracestate:
                headers["tracestate"] = ctx.trace_context.to_tracestate()

        timeout = kwargs.pop("timeout", None)
        if ctx.deadline is not None:
            remaining = ctx.deadline - time.time()
            if remaining <= 0:
                raise TransportError(f"deadline exceeded before calling {method} {path}")
            headers["X-Deadline"] = str(ctx.deadline)
            configured = timeout if timeout is not None else self._config.timeout
            timeout = (
                min(configured, remaining) if isinstance(configured, int | float) else remaining
            )

        if timeout is not None:
            kwargs["timeout"] = timeout

        retryable = method.upper() in _IDEMPOTENT_METHODS
        attempts = self._config.retries + 1 if retryable else 1

        last_exc: Exception | None = None
        for attempt in range(attempts):
            start = time.perf_counter()
            try:
                response = await self._client.request(method, path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                self._record_downstream(method, path, "error", start)
                if attempt == attempts - 1:
                    raise TransportError(f"{method} {path} failed: {exc}") from exc
                await self._sleep_backoff(attempt)
                continue

            self._record_downstream(method, path, str(response.status_code), start)
            if response.status_code >= 500 and attempt < attempts - 1:
                await self._sleep_backoff(attempt)
                continue
            return response

        raise TransportError(f"{method} {path} failed") from last_exc

    async def _sleep_backoff(self, attempt: int) -> None:
        await asyncio.sleep(self._config.retry_backoff_seconds * (2**attempt))

    def _record_downstream(self, method: str, path: str, status: str, start: float) -> None:
        latency_ms = (time.perf_counter() - start) * 1000
        RequestContext().add_downstream_call(
            DownstreamCall(
                system="http",
                process="pythonforge.http.client",
                method=method,
                destination=path,
                status=status,
                latency_ms=latency_ms,
            )
        )

    async def close(self) -> None:
        await self._client.aclose()
