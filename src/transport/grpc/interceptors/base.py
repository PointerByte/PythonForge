"""Shared machinery for server interceptors that must wrap every RPC pattern.

``grpc.aio`` gives interceptors a single hook (``intercept_service``) that
returns an ``RpcMethodHandler``. Wrapping behaviour uniformly across unary,
client-streaming, server-streaming and bidi RPCs is fiddly enough that every
PythonForge interceptor builds on :class:`HandlerWrappingInterceptor` rather
than reimplementing the dispatch.
"""

from __future__ import annotations

import inspect
from abc import abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .._optional import require_grpc, require_grpc_aio

UnaryBehavior = Callable[[Any, Any], Awaitable[Any]]
StreamBehavior = Callable[[Any, Any], AsyncIterator[Any]]


def _as_coroutine(behavior: Any) -> Any:
    """Adapt a possibly-synchronous unary handler to an awaitable one.

    Not every servicer registered on an aio server is async: grpc's own
    ``grpc.health.v1`` servicer, for instance, implements plain ``def``
    methods that work with both server flavours. Interceptors must not
    assume otherwise.
    """

    async def call(request: Any, context: Any) -> Any:
        result = behavior(request, context)
        if inspect.isawaitable(result):
            return await result
        return result

    return call


def _as_async_iterator(behavior: Any) -> Any:
    """Adapt a possibly-synchronous streaming handler to an async iterator."""

    async def call(request: Any, context: Any) -> AsyncIterator[Any]:
        result = behavior(request, context)
        if hasattr(result, "__aiter__"):
            async for item in result:
                yield item
        elif inspect.isawaitable(result):
            for item in await result:
                yield item
        else:
            for item in result:
                yield item

    return call


def _rebuild_handler(handler: Any, behavior: Any) -> Any:
    """Return a copy of ``handler`` with its behaviour replaced."""
    grpc = require_grpc()
    if handler.request_streaming and handler.response_streaming:
        factory = grpc.stream_stream_rpc_method_handler
    elif handler.request_streaming:
        factory = grpc.stream_unary_rpc_method_handler
    elif handler.response_streaming:
        factory = grpc.unary_stream_rpc_method_handler
    else:
        factory = grpc.unary_unary_rpc_method_handler
    return factory(
        behavior,
        request_deserializer=handler.request_deserializer,
        response_serializer=handler.response_serializer,
    )


class HandlerWrappingInterceptor(require_grpc_aio().ServerInterceptor):  # type: ignore[misc]
    """Base class that applies :meth:`wrap_call` around every RPC pattern.

    Subclasses implement :meth:`wrap_call` once; this class takes care of
    awaiting unary responses versus iterating streaming ones.
    """

    async def intercept_service(
        self,
        continuation: Callable[[Any], Awaitable[Any]],
        handler_call_details: Any,
    ) -> Any:
        handler = await continuation(handler_call_details)
        if handler is None:
            return None
        method: str = handler_call_details.method
        raw = self._extract_behavior(handler)
        # Subclasses always receive an async behaviour, whatever the servicer
        # actually registered.
        inner = _as_async_iterator(raw) if handler.response_streaming else _as_coroutine(raw)

        if handler.response_streaming:

            async def stream_behavior(request: Any, context: Any) -> AsyncIterator[Any]:
                async for response in self.wrap_stream(inner, request, context, method):
                    yield response

            return _rebuild_handler(handler, stream_behavior)

        async def unary_behavior(request: Any, context: Any) -> Any:
            return await self.wrap_unary(inner, request, context, method)

        return _rebuild_handler(handler, unary_behavior)

    @staticmethod
    def _extract_behavior(handler: Any) -> Any:
        for attribute in ("unary_unary", "unary_stream", "stream_unary", "stream_stream"):
            behavior = getattr(handler, attribute, None)
            if behavior is not None:
                return behavior
        raise RuntimeError("RPC handler exposes no behaviour")  # pragma: no cover

    @abstractmethod
    async def wrap_unary(
        self, behavior: Any, request: Any, context: Any, method: str
    ) -> Any:  # pragma: no cover - abstract
        ...

    @abstractmethod
    def wrap_stream(
        self, behavior: Any, request: Any, context: Any, method: str
    ) -> AsyncIterator[Any]:  # pragma: no cover - abstract
        ...
