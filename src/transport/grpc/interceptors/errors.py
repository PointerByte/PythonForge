"""Maps PythonForge exceptions to gRPC status codes.

Mirrors the HTTP exception handlers in
``pythonforge.transport.http.app_factory``: the same exception produces
HTTP 401 / gRPC UNAUTHENTICATED, HTTP 403 / gRPC PERMISSION_DENIED, and so
on. Internal exception detail never reaches the caller -- it is logged and
replaced by a generic message.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ....errors import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    PythonForgeError,
    TransportError,
)
from ....logger import get_logger
from .._optional import require_grpc
from .base import HandlerWrappingInterceptor

logger = get_logger("pythonforge.grpc")


def status_code_for(exc: BaseException) -> Any:
    """Return the ``grpc.StatusCode`` that a given exception maps to."""
    grpc = require_grpc()
    if isinstance(exc, AuthenticationError):
        return grpc.StatusCode.UNAUTHENTICATED
    if isinstance(exc, AuthorizationError):
        return grpc.StatusCode.PERMISSION_DENIED
    if isinstance(exc, ConfigurationError):
        return grpc.StatusCode.FAILED_PRECONDITION
    if isinstance(exc, TransportError):
        return grpc.StatusCode.UNAVAILABLE
    if isinstance(exc, PythonForgeError):
        return grpc.StatusCode.INVALID_ARGUMENT
    return grpc.StatusCode.INTERNAL


class ErrorInterceptor(HandlerWrappingInterceptor):
    async def wrap_unary(self, behavior: Any, request: Any, context: Any, method: str) -> Any:
        try:
            return await behavior(request, context)
        except Exception as exc:
            await self._abort(context, exc, method)

    async def wrap_stream(
        self, behavior: Any, request: Any, context: Any, method: str
    ) -> AsyncIterator[Any]:
        try:
            async for response in behavior(request, context):
                yield response
        except Exception as exc:
            await self._abort(context, exc, method)

    @staticmethod
    async def _abort(context: Any, exc: Exception, method: str) -> Any:
        grpc = require_grpc()
        # A handler that aborted deliberately already carries its own status.
        if isinstance(exc, grpc.aio.AbortError | grpc.RpcError):
            raise exc
        if isinstance(exc, PythonForgeError):
            message = str(exc)
        else:
            logger.exception("unhandled exception in RPC %s", method)
            message = "internal server error"
        await context.abort(status_code_for(exc), message)
