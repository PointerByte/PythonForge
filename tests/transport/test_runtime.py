from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pythonforge.config import ServerGRPCConfig, load_config
from pythonforge.errors import LifecycleError
from pythonforge.transport import ServiceRuntime
from pythonforge.transport.grpc import create_channel, create_grpc_server
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2 as pb,
)
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2_grpc as pbg,
)


def _runtime(tmp_path: Path) -> ServiceRuntime:
    return ServiceRuntime(load_config(config_dir=tmp_path), shutdown_timeout=2.0)


async def test_components_start_and_stop_in_order(tmp_path: Path) -> None:
    events: list[str] = []
    runtime = _runtime(tmp_path)

    def component(name: str) -> tuple:
        async def start() -> None:
            events.append(f"start:{name}")

        async def stop() -> None:
            events.append(f"stop:{name}")

        return start, stop

    for label in ("a", "b"):
        runtime.add_component(label, *component(label))

    await runtime.start()
    await runtime.stop()

    # Started in registration order, stopped in reverse.
    assert events == ["start:a", "start:b", "stop:b", "stop:a"]


async def test_failed_start_rolls_back_already_started_components(tmp_path: Path) -> None:
    events: list[str] = []
    runtime = _runtime(tmp_path)

    async def ok_start() -> None:
        events.append("start:ok")

    async def ok_stop() -> None:
        events.append("stop:ok")

    async def bad_start() -> None:
        raise OSError("port already in use")

    async def bad_stop() -> None:  # pragma: no cover - never started
        events.append("stop:bad")

    runtime.add_component("ok", ok_start, ok_stop)
    runtime.add_component("bad", bad_start, bad_stop)

    with pytest.raises(LifecycleError, match="bad"):
        await runtime.start()

    # The healthy transport must be torn down; the failed one never started.
    assert events == ["start:ok", "stop:ok"]


async def test_slow_component_does_not_block_the_rest_of_shutdown(tmp_path: Path) -> None:
    events: list[str] = []
    runtime = ServiceRuntime(load_config(config_dir=tmp_path), shutdown_timeout=0.1)

    async def noop() -> None:
        return None

    async def slow_stop() -> None:
        await asyncio.sleep(10)

    async def fast_stop() -> None:
        events.append("stop:fast")

    runtime.add_component("fast", noop, fast_stop)
    runtime.add_component("slow", noop, slow_stop)

    await runtime.start()
    await runtime.stop()

    assert events == ["stop:fast"]


async def test_stop_error_does_not_prevent_other_components_stopping(tmp_path: Path) -> None:
    events: list[str] = []
    runtime = _runtime(tmp_path)

    async def noop() -> None:
        return None

    async def failing_stop() -> None:
        raise RuntimeError("teardown blew up")

    async def good_stop() -> None:
        events.append("stop:good")

    runtime.add_component("good", noop, good_stop)
    runtime.add_component("failing", noop, failing_stop)

    await runtime.start()
    await runtime.stop()

    assert events == ["stop:good"]


async def test_async_context_manager_starts_and_stops(tmp_path: Path) -> None:
    events: list[str] = []
    runtime = _runtime(tmp_path)

    async def start() -> None:
        events.append("start")

    async def stop() -> None:
        events.append("stop")

    runtime.add_component("c", start, stop)
    async with runtime:
        assert events == ["start"]
    assert events == ["start", "stop"]


async def test_grpc_server_runs_under_the_runtime(tmp_path: Path) -> None:
    """End-to-end: a real gRPC server, started and drained by ServiceRuntime."""

    class Service(pbg.ExampleServiceServicer):
        async def Echo(self, request, context):  # noqa: N802
            return pb.EchoResponse(message=request.message)

    server = create_grpc_server(ServerGRPCConfig(host="127.0.0.1", port=0))
    pbg.add_ExampleServiceServicer_to_server(Service(), server)
    port = server.pythonforge_port

    runtime = _runtime(tmp_path)
    runtime.add_grpc_server(server)

    async with runtime:
        async with create_channel(f"127.0.0.1:{port}", force_insecure=True) as channel:
            response = await pbg.ExampleServiceStub(channel).Echo(pb.EchoRequest(message="up"))
            assert response.message == "up"


async def test_serve_forever_returns_after_stop(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    stopped: list[str] = []

    async def noop() -> None:
        return None

    async def stop() -> None:
        stopped.append("stopped")

    runtime.add_component("c", noop, stop)

    task = asyncio.create_task(runtime.serve_forever(handle_signals=False))
    await asyncio.sleep(0.05)
    await runtime.stop()
    await asyncio.wait_for(task, timeout=2)

    assert stopped
