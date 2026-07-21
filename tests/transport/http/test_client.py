from __future__ import annotations

import time

import httpx
import pytest

from pythonforge.config import ClientConfig
from pythonforge.context import RequestContext, TraceContext
from pythonforge.errors import TransportError
from pythonforge.transport.http.client import ForgeClient


def _client(handler, **config_overrides: object) -> ForgeClient:
    config = ClientConfig(retry_backoff_seconds=0, **config_overrides)
    return ForgeClient("http://test", config, transport=httpx.MockTransport(handler))


async def test_returns_raw_httpx_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    response = await client.get("/x")
    assert isinstance(response, httpx.Response)
    assert response.json() == {"ok": True}
    await client.close()


async def test_propagates_request_id_and_traceparent() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        return httpx.Response(200)

    client = _client(handler)
    ctx = RequestContext()
    trace = TraceContext(trace_id="a" * 32)
    with ctx.bind(request_id="req-1", trace_context=trace):
        await client.get("/x")
    assert seen["headers"]["x-request-id"] == "req-1"
    assert seen["headers"]["traceparent"] == trace.to_traceparent()
    await client.close()


async def test_convenience_verb_methods_use_the_right_http_method() -> None:
    seen_methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_methods.append(request.method)
        return httpx.Response(200)

    client = _client(handler)
    await client.put("/x")
    await client.patch("/x")
    await client.delete("/x")
    assert seen_methods == ["PUT", "PATCH", "DELETE"]
    await client.close()


async def test_no_context_headers_when_context_empty() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        return httpx.Response(200)

    client = _client(handler)
    await client.get("/x")
    assert "x-request-id" not in seen["headers"]
    assert "traceparent" not in seen["headers"]
    await client.close()


async def test_retries_idempotent_method_on_5xx_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200)

    client = _client(handler, retries=3)
    response = await client.get("/x")
    assert response.status_code == 200
    assert attempts["n"] == 3
    await client.close()


async def test_does_not_retry_non_idempotent_method_on_5xx() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503)

    client = _client(handler, retries=3)
    response = await client.post("/x")
    assert response.status_code == 503
    assert attempts["n"] == 1
    await client.close()


async def test_does_not_retry_4xx() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(404)

    client = _client(handler, retries=3)
    response = await client.get("/x")
    assert response.status_code == 404
    assert attempts["n"] == 1
    await client.close()


async def test_retries_transport_error_then_raises_after_exhausting_budget() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = _client(handler, retries=2)
    with pytest.raises(TransportError):
        await client.get("/x")
    await client.close()


async def test_deadline_already_passed_raises_without_calling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200)

    client = _client(handler)
    ctx = RequestContext()
    with ctx.bind(deadline=time.time() - 1):
        with pytest.raises(TransportError, match="deadline exceeded"):
            await client.get("/x")
    assert called["n"] == 0
    await client.close()


async def test_records_downstream_call_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201)

    client = _client(handler)
    ctx = RequestContext()
    await client.post("/widgets")
    assert len(ctx.downstream_processes) == 1
    call = ctx.downstream_processes[0]
    assert call.system == "http"
    assert call.method == "POST"
    assert call.destination == "/widgets"
    assert call.status == "201"
    await client.close()


async def test_records_downstream_call_on_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = _client(handler, retries=0)
    ctx = RequestContext()
    with pytest.raises(TransportError):
        await client.get("/x")
    assert ctx.downstream_processes[-1].status == "error"
    await client.close()


async def test_async_context_manager_closes_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    async with ForgeClient("http://test", transport=httpx.MockTransport(handler)) as client:
        response = await client.get("/x")
        assert response.status_code == 200


async def test_constructs_with_insecure_verify_disabled() -> None:
    client = ForgeClient("https://example.com", ClientConfig(verify=False))
    await client.close()
