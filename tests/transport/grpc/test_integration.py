from __future__ import annotations

import asyncio

import grpc
import pytest

from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2 as pb,
)

TRACEPARENT = f"00-{'a' * 32}-{'b' * 16}-01"


async def test_unary(stub) -> None:
    response = await stub.Echo(pb.EchoRequest(message="hello"))
    assert response.message == "hello"


async def test_server_streaming(stub) -> None:
    messages = [item.message async for item in stub.EchoStream(pb.EchoRequest(message="s"))]
    assert messages == ["s-0", "s-1", "s-2"]


async def test_client_streaming(stub) -> None:
    async def requests():
        for value in (1, 2, 3, 4):
            yield pb.SumRequest(value=value)

    response = await stub.SumStream(requests())
    assert response.total == 10


async def test_bidirectional_streaming(stub) -> None:
    async def requests():
        for message in ("a", "b", "c"):
            yield pb.EchoRequest(message=message)

    messages = [item.message async for item in stub.EchoBidi(requests())]
    assert messages == ["bidi:a", "bidi:b", "bidi:c"]


async def test_metadata_populates_shared_context(stub) -> None:
    """The gRPC adapter must fill the same RequestContext the HTTP one does."""
    response = await stub.Echo(
        pb.EchoRequest(message="hi"),
        metadata=(("x-request-id", "req-42"), ("traceparent", TRACEPARENT)),
    )
    assert response.request_id == "req-42"
    assert response.trace_id == "a" * 32


async def test_request_id_is_generated_when_absent(stub) -> None:
    response = await stub.Echo(pb.EchoRequest(message="hi"))
    assert response.request_id


async def test_malformed_traceparent_starts_a_fresh_trace(stub) -> None:
    response = await stub.Echo(
        pb.EchoRequest(message="hi"), metadata=(("traceparent", "not-a-traceparent"),)
    )
    assert response.trace_id
    assert response.trace_id != "not-a-traceparent"


async def test_context_is_isolated_across_concurrent_rpcs(stub) -> None:
    responses = await asyncio.gather(
        *(
            stub.Echo(pb.EchoRequest(message=f"m{i}"), metadata=(("x-request-id", f"req-{i}"),))
            for i in range(8)
        )
    )
    assert [r.request_id for r in responses] == [f"req-{i}" for i in range(8)]


async def test_streaming_rpc_also_populates_context(stub) -> None:
    items = [
        item
        async for item in stub.EchoStream(
            pb.EchoRequest(message="s"), metadata=(("x-request-id", "stream-req"),)
        )
    ]
    assert all(item.request_id == "stream-req" for item in items)


async def test_internal_exception_maps_to_internal_without_leaking(stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await stub.Echo(pb.EchoRequest(message="boom"))
    assert exc_info.value.code() == grpc.StatusCode.INTERNAL
    assert "internal detail" not in exc_info.value.details()


async def test_authentication_error_maps_to_unauthenticated(stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await stub.Echo(pb.EchoRequest(message="unauthenticated"))
    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_authorization_error_maps_to_permission_denied(stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await stub.Echo(pb.EchoRequest(message="forbidden"))
    assert exc_info.value.code() == grpc.StatusCode.PERMISSION_DENIED


async def test_streaming_error_maps_to_status_code(stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        [item async for item in stub.EchoStream(pb.EchoRequest(message="boom"))]
    assert exc_info.value.code() == grpc.StatusCode.INTERNAL


async def test_deadline_exceeded(stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await stub.Echo(pb.EchoRequest(message="slow"), timeout=0.1)
    assert exc_info.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED


async def test_cancellation(stub) -> None:
    call = stub.Echo(pb.EchoRequest(message="slow"))
    await asyncio.sleep(0.05)
    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call
    assert call.cancelled()


async def test_health_service_is_registered(grpc_server: int) -> None:
    from grpc_health.v1 import health_pb2, health_pb2_grpc

    from pythonforge.transport.grpc import create_channel

    async with create_channel(f"127.0.0.1:{grpc_server}", force_insecure=True) as channel:
        stub = health_pb2_grpc.HealthStub(channel)
        response = await stub.Check(health_pb2.HealthCheckRequest())
        assert response.status == health_pb2.HealthCheckResponse.SERVING
