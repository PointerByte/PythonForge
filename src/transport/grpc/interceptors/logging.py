"""Emits one log entry per RPC using the exact schema the HTTP transport uses.

Field-for-field parity with
``pythonforge.transport.http.middleware.RequestContextMiddleware`` is a
requirement, not a coincidence -- ``tests/contracts/`` asserts it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from ....logger import get_logger, log_event
from .base import HandlerWrappingInterceptor

logger = get_logger("pythonforge.grpc")


class LoggingInterceptor(HandlerWrappingInterceptor):
    async def wrap_unary(self, behavior: Any, request: Any, context: Any, method: str) -> Any:
        start = time.perf_counter()
        status = "OK"
        try:
            return await behavior(request, context)
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._emit(method, status, start)

    async def wrap_stream(
        self, behavior: Any, request: Any, context: Any, method: str
    ) -> AsyncIterator[Any]:
        start = time.perf_counter()
        status = "OK"
        try:
            async for response in behavior(request, context):
                yield response
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._emit(method, status, start)

    @staticmethod
    def _emit(method: str, status: str, start: float) -> None:
        log_event(
            logger,
            logging.INFO,
            "rpc finished",
            process="grpc",
            method=method,
            latency_ms=(time.perf_counter() - start) * 1000,
            # Message payloads are deliberately absent: bodies are never
            # captured by default, in gRPC just as in HTTP.
            details={"status": status},
        )
