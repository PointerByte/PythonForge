from __future__ import annotations

import asyncio
import contextvars
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from pythonforge import context as context_module
from pythonforge.config import LoggerConfig, ServerGRPCConfig
from pythonforge.context import RequestContext
from pythonforge.errors import AuthenticationError, AuthorizationError
from pythonforge.logger import configure_logging
from pythonforge.transport.grpc import create_channel, create_grpc_server
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2 as pb,
)
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2_grpc as pbg,
)


@pytest.fixture(autouse=True)
def _isolated_request_context() -> Iterator[None]:
    """Reset every request-scoped contextvar before/after each test.

    Without this, a test that sets context state directly (rather than
    through the auto-resetting ``RequestContext.bind``) would leak into
    whichever test happens to run next in the same process.
    """
    tokens: list[tuple[contextvars.ContextVar[Any], contextvars.Token[Any]]] = [
        (context_module._request_id, context_module._request_id.set(None)),
        (context_module._trace_context, context_module._trace_context.set(None)),
        (context_module._claims, context_module._claims.set(None)),
        (context_module._deadline, context_module._deadline.set(None)),
        (context_module._attributes, context_module._attributes.set(None)),
        (context_module._downstream_processes, context_module._downstream_processes.set(())),
    ]
    yield
    for var, token in reversed(tokens):
        var.reset(token)


class ExampleService(pbg.ExampleServiceServicer):
    """Covers all four RPC patterns plus the error-mapping paths."""

    async def Echo(self, request, context):  # noqa: N802 - gRPC naming
        ctx = RequestContext()
        if request.message == "boom":
            raise ValueError("internal detail that must not leak")
        if request.message == "unauthenticated":
            raise AuthenticationError("missing bearer token")
        if request.message == "forbidden":
            raise AuthorizationError("insufficient scope")
        if request.message == "slow":
            await asyncio.sleep(5)
        return pb.EchoResponse(
            message=request.message,
            request_id=ctx.request_id or "",
            trace_id=ctx.trace_context.trace_id if ctx.trace_context else "",
        )

    async def EchoStream(self, request, context):  # noqa: N802
        ctx = RequestContext()
        if request.message == "boom":
            raise ValueError("internal detail that must not leak")
        for index in range(3):
            yield pb.EchoResponse(
                message=f"{request.message}-{index}",
                request_id=ctx.request_id or "",
            )

    async def SumStream(self, request_iterator, context):  # noqa: N802
        total = 0
        async for request in request_iterator:
            total += request.value
        return pb.SumResponse(total=total)

    async def EchoBidi(self, request_iterator, context):  # noqa: N802
        async for request in request_iterator:
            yield pb.EchoResponse(message=f"bidi:{request.message}")


@pytest.fixture
async def grpc_server() -> AsyncIterator[int]:
    """A running server on an ephemeral port; yields the bound port."""
    configure_logging(LoggerConfig(format="json"))
    server = create_grpc_server(ServerGRPCConfig(host="127.0.0.1", port=0))
    pbg.add_ExampleServiceServicer_to_server(ExampleService(), server)
    await server.start()
    try:
        yield server.pythonforge_port
    finally:
        await server.stop(grace=None)


@pytest.fixture
async def stub(grpc_server: int) -> AsyncIterator[pbg.ExampleServiceStub]:
    async with create_channel(f"127.0.0.1:{grpc_server}", force_insecure=True) as channel:
        yield pbg.ExampleServiceStub(channel)
