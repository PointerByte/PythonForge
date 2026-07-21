"""Contracts both transports must satisfy identically.

The specs require that a capability added to one transport exists in the
other with the same observable semantics. These tests exercise HTTP and gRPC
side by side and compare the results, so drift fails the build rather than
being discovered in production.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from pythonforge.config import LoggerConfig, load_config
from pythonforge.context import RequestContext
from pythonforge.logger import configure_logging
from pythonforge.logger.schema import SCHEMA_FIELDS
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import example_pb2 as pb
from pythonforge.transport.http import create_app

TRACEPARENT = f"00-{'a' * 32}-{'b' * 16}-01"


def _log_lines(captured: str) -> list[dict]:
    return [json.loads(line) for line in captured.strip().splitlines() if line.startswith("{")]


@pytest.fixture
def http_client(tmp_path: Path) -> TestClient:
    router = APIRouter()

    @router.get("/echo")
    async def echo() -> dict[str, str | None]:
        ctx = RequestContext()
        return {
            "request_id": ctx.request_id,
            "trace_id": ctx.trace_context.trace_id if ctx.trace_context else None,
        }

    config = load_config(config_dir=tmp_path, trace={"enabled": False}, logger={"format": "json"})
    return TestClient(create_app(config, routers=[router]))


async def test_request_id_metadata_and_header_are_equivalent(http_client, stub) -> None:
    """The same identity travels as an HTTP header or as gRPC metadata."""
    http_body = http_client.get("/echo", headers={"X-Request-Id": "shared-id"}).json()
    rpc = await stub.Echo(pb.EchoRequest(message="x"), metadata=(("x-request-id", "shared-id"),))

    assert http_body["request_id"] == "shared-id"
    assert rpc.request_id == "shared-id"


async def test_traceparent_is_honoured_by_both_transports(http_client, stub) -> None:
    http_body = http_client.get("/echo", headers={"traceparent": TRACEPARENT}).json()
    rpc = await stub.Echo(pb.EchoRequest(message="x"), metadata=(("traceparent", TRACEPARENT),))

    assert http_body["trace_id"] == "a" * 32
    assert rpc.trace_id == "a" * 32
    assert http_body["trace_id"] == rpc.trace_id


async def test_both_transports_generate_a_request_id_when_absent(http_client, stub) -> None:
    http_body = http_client.get("/echo").json()
    rpc = await stub.Echo(pb.EchoRequest(message="x"))

    assert http_body["request_id"]
    assert rpc.request_id


async def test_log_schema_is_identical_across_transports(
    http_client, stub, capsys: pytest.CaptureFixture[str]
) -> None:
    """Field-for-field parity of the completion log entry."""
    configure_logging(LoggerConfig(format="json"))
    logging.getLogger("pythonforge.grpc").handlers = logging.getLogger("pythonforge").handlers
    logging.getLogger("pythonforge.http").handlers = logging.getLogger("pythonforge").handlers

    capsys.readouterr()
    http_client.get("/echo")
    http_entries = [e for e in _log_lines(capsys.readouterr().err) if e["process"] == "http"]

    await stub.Echo(pb.EchoRequest(message="x"))
    grpc_entries = [e for e in _log_lines(capsys.readouterr().err) if e["process"] == "grpc"]

    assert http_entries, "the HTTP transport logged no completion entry"
    assert grpc_entries, "the gRPC transport logged no completion entry"

    http_entry, grpc_entry = http_entries[-1], grpc_entries[-1]
    assert set(http_entry) == set(grpc_entry)
    assert set(SCHEMA_FIELDS) <= set(http_entry)

    for entry in (http_entry, grpc_entry):
        assert entry["trace_id"]
        assert entry["method"]
        assert isinstance(entry["latency_ms"], float)


async def test_neither_transport_logs_payloads(
    http_client, stub, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bodies and message payloads stay out of logs unless explicitly enabled."""
    configure_logging(LoggerConfig(format="json"))
    logging.getLogger("pythonforge.grpc").handlers = logging.getLogger("pythonforge").handlers
    logging.getLogger("pythonforge.http").handlers = logging.getLogger("pythonforge").handlers

    capsys.readouterr()
    http_client.get("/echo", headers={"Authorization": "Bearer super-secret"})
    await stub.Echo(
        pb.EchoRequest(message="top-secret-payload"),
        metadata=(("authorization", "Bearer super-secret"),),
    )
    captured = capsys.readouterr().err

    assert "super-secret" not in captured
    assert "top-secret-payload" not in captured
