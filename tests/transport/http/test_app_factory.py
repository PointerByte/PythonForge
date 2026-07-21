from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from pythonforge.config import FullConfig, load_config
from pythonforge.errors import AuthenticationError, AuthorizationError, PythonForgeError
from pythonforge.transport.http import create_app


def _build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/hello")
    async def hello() -> dict[str, str]:
        return {"message": "hi"}

    @router.get("/boom")
    async def boom() -> None:
        raise ValueError("kaboom")

    @router.get("/unauthenticated")
    async def unauthenticated() -> None:
        raise AuthenticationError("missing credentials")

    @router.get("/forbidden")
    async def forbidden() -> None:
        raise AuthorizationError("not allowed")

    @router.get("/bad-request")
    async def bad_request() -> None:
        raise PythonForgeError("something is off")

    return router


def _config(tmp_path: Path, **overrides: object) -> FullConfig:
    return load_config(config_dir=tmp_path, trace={"enabled": False}, **overrides)  # type: ignore[arg-type]


def _app(tmp_path: Path, **overrides: object) -> FastAPI:
    return create_app(_config(tmp_path, **overrides), routers=[_build_router()])


def test_liveness_ok(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_readiness_reflects_startup(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_readiness_reflects_failing_check(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path), readiness_checks=[lambda: False])
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


async def test_readiness_supports_async_checks(tmp_path: Path) -> None:
    async def check() -> bool:
        return True

    app = create_app(_config(tmp_path), readiness_checks=[check])
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_custom_health_and_ready_paths(tmp_path: Path) -> None:
    app = create_app(
        _config(tmp_path, server={"http": {"health_path": "/live", "ready_path": "/ready"}})
    )
    with TestClient(app) as client:
        assert client.get("/live").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/health").status_code == 404


def test_request_id_header_is_echoed(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/v1/hello", headers={"X-Request-Id": "my-id"})
        assert response.headers["X-Request-Id"] == "my-id"


def test_request_id_is_generated_when_absent(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/v1/hello")
        assert response.headers["X-Request-Id"]


def test_traceparent_and_tracestate_headers_are_honored(tmp_path: Path) -> None:
    router = APIRouter()

    @router.get("/echo-trace")
    async def echo_trace() -> dict[str, str | None]:
        from pythonforge.context import RequestContext

        ctx = RequestContext()
        trace = ctx.trace_context
        return {
            "trace_id": trace.trace_id if trace else None,
            "tracestate": trace.to_tracestate() if trace else None,
        }

    app = create_app(_config(tmp_path), routers=[router])
    with TestClient(app) as client:
        response = client.get(
            "/echo-trace",
            headers={
                "traceparent": f"00-{'a' * 32}-{'b' * 16}-01",
                "tracestate": "vendor=1",
            },
        )
        assert response.json() == {"trace_id": "a" * 32, "tracestate": "vendor=1"}


def test_invalid_deadline_header_is_ignored(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/v1/hello", headers={"X-Deadline": "not-a-number"})
        assert response.status_code == 200


def test_security_headers_present(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/v1/hello")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


def test_unhandled_exception_returns_stable_envelope_without_leaking_details(
    tmp_path: Path,
) -> None:
    with TestClient(_app(tmp_path), raise_server_exceptions=False) as client:
        response = client.get("/boom")
        assert response.status_code == 500
        body = response.json()
        assert body == {
            "error": {
                "code": 500,
                "message": "internal server error",
                "request_id": response.headers["X-Request-Id"],
            }
        }
        assert "kaboom" not in response.text


def test_404_uses_stable_envelope(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        assert "error" in response.json()


def test_validation_error_returns_422_envelope(tmp_path: Path) -> None:
    router = APIRouter()

    @router.post("/items")
    async def create_item(name: str) -> dict[str, str]:
        return {"name": name}

    app = create_app(_config(tmp_path), routers=[router])
    with TestClient(app) as client:
        response = client.post("/items", json={})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == 422


def test_cors_disabled_by_default(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/api/v1/hello", headers={"Origin": "https://example.com"})
        assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origin(tmp_path: Path) -> None:
    app = _app(tmp_path, server={"http": {"cors_origins": ["https://example.com"]}})
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})
        assert response.headers["access-control-allow-origin"] == "https://example.com"


def test_rate_limit_exempts_health_endpoints(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        server={
            "http": {
                "rate_limit_enabled": True,
                "rate_limit_requests": 1,
                "rate_limit_window_seconds": 60,
            }
        },
    )
    with TestClient(app) as client:
        for _ in range(5):
            assert client.get("/health").status_code == 200
            assert client.get("/health/ready").status_code == 200


def test_rate_limit_returns_429_with_retry_after(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        server={
            "http": {
                "rate_limit_enabled": True,
                "rate_limit_requests": 2,
                "rate_limit_window_seconds": 60,
            }
        },
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/hello").status_code == 200
        assert client.get("/api/v1/hello").status_code == 200
        third = client.get("/api/v1/hello")
        assert third.status_code == 429
        assert "Retry-After" in third.headers
        assert third.json()["error"]["code"] == 429


def test_rate_limit_window_expires_and_allows_more_requests(tmp_path: Path) -> None:
    import time

    app = _app(
        tmp_path,
        server={
            "http": {
                "rate_limit_enabled": True,
                "rate_limit_requests": 1,
                "rate_limit_window_seconds": 0.05,
            }
        },
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/hello").status_code == 200
        assert client.get("/api/v1/hello").status_code == 429
        time.sleep(0.1)
        assert client.get("/api/v1/hello").status_code == 200


def test_two_apps_from_different_configs_do_not_share_state(tmp_path: Path) -> None:
    app_a = _app(tmp_path / "a")
    app_b = _app(tmp_path / "b", server={"http": {"cors_origins": ["https://b.example.com"]}})
    assert app_a.state.config.server.http.cors_origins == []
    assert app_b.state.config.server.http.cors_origins == ["https://b.example.com"]


def test_authentication_error_returns_401(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/unauthenticated")
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "missing credentials"


def test_authorization_error_returns_403(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/forbidden")
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "not allowed"


def test_generic_pythonforge_error_returns_400(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        response = client.get("/bad-request")
        assert response.status_code == 400
        assert response.json()["error"]["message"] == "something is off"


def test_startup_and_shutdown_hooks_run(tmp_path: Path) -> None:
    events: list[str] = []

    def sync_startup(app: FastAPI) -> None:
        events.append("sync_startup")

    async def async_startup(app: FastAPI) -> None:
        events.append("async_startup")

    def sync_shutdown(app: FastAPI) -> None:
        events.append("sync_shutdown")

    async def async_shutdown(app: FastAPI) -> None:
        events.append("async_shutdown")

    app = create_app(
        _config(tmp_path),
        on_startup=[sync_startup, async_startup],
        on_shutdown=[sync_shutdown, async_shutdown],
    )
    with TestClient(app):
        assert events == ["sync_startup", "async_startup"]
    assert events == ["sync_startup", "async_startup", "sync_shutdown", "async_shutdown"]
