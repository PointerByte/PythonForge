"""Auth must behave identically over HTTP and gRPC: same token, same outcome."""

from __future__ import annotations

from pathlib import Path

import grpc
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from pythonforge.config import JWTConfig, ServerGRPCConfig, load_config
from pythonforge.context import RequestContext
from pythonforge.security import Claims, encode_token, require_auth
from pythonforge.security.http import optional_auth
from pythonforge.transport.grpc import create_channel, create_grpc_server
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2 as pb,
)
from pythonforge.transport.grpc.generated.pythonforge.example.v1 import (
    example_pb2_grpc as pbg,
)
from pythonforge.transport.grpc.interceptors.auth import JWTAuthInterceptor
from pythonforge.transport.http import create_app

SECRET = "auth-tests-signing-secret-value!!"


@pytest.fixture
def jwt_config() -> JWTConfig:
    return JWTConfig(enabled=True, algorithm="HS256", secret_key=SECRET)


@pytest.fixture
def token(jwt_config: JWTConfig) -> str:
    return encode_token(jwt_config, Claims(sub="user-1", scope="widgets:read"))


# --- HTTP --------------------------------------------------------------


@pytest.fixture
def http_client(tmp_path: Path, jwt_config: JWTConfig) -> TestClient:
    router = APIRouter()

    @router.get("/private")
    async def private(claims: Claims = Depends(require_auth(jwt_config))) -> dict[str, str | None]:
        return {"sub": claims.sub, "context_sub": (RequestContext().claims or {}).get("sub")}

    @router.get("/scoped")
    async def scoped(
        claims: Claims = Depends(require_auth(jwt_config, scopes=["widgets:write"])),
    ) -> dict[str, str | None]:
        return {"sub": claims.sub}

    @router.get("/cookie-auth")
    async def cookie_auth(
        claims: Claims = Depends(require_auth(jwt_config, cookie_name="session")),
    ) -> dict[str, str | None]:
        return {"sub": claims.sub}

    @router.get("/maybe")
    async def maybe(
        claims: Claims | None = Depends(optional_auth(jwt_config)),
    ) -> dict[str, str | None]:
        return {"sub": claims.sub if claims else None}

    config = load_config(config_dir=tmp_path, trace={"enabled": False})
    return TestClient(create_app(config, routers=[router]))


def test_http_valid_token_is_accepted(http_client: TestClient, token: str) -> None:
    response = http_client.get("/private", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["sub"] == "user-1"


def test_http_claims_are_published_to_the_shared_context(
    http_client: TestClient, token: str
) -> None:
    response = http_client.get("/private", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["context_sub"] == "user-1"


def test_http_missing_token_is_401(http_client: TestClient) -> None:
    assert http_client.get("/private").status_code == 401


def test_http_invalid_token_is_401(http_client: TestClient) -> None:
    response = http_client.get("/private", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_http_non_bearer_scheme_is_401(http_client: TestClient, token: str) -> None:
    response = http_client.get("/private", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 401


def test_http_missing_scope_is_403(http_client: TestClient, token: str) -> None:
    response = http_client.get("/scoped", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_http_cookie_token_is_accepted(http_client: TestClient, token: str) -> None:
    response = http_client.get("/cookie-auth", cookies={"session": token})
    assert response.status_code == 200
    assert response.json()["sub"] == "user-1"


def test_http_optional_auth_allows_anonymous(http_client: TestClient) -> None:
    response = http_client.get("/maybe")
    assert response.status_code == 200
    assert response.json()["sub"] is None


def test_http_optional_auth_still_rejects_a_forged_token(http_client: TestClient) -> None:
    """'Optional' means the token may be absent, never that it may be invalid."""
    response = http_client.get("/maybe", headers={"Authorization": "Bearer forged"})
    assert response.status_code == 401


# --- gRPC --------------------------------------------------------------


@pytest.fixture
async def authenticated_stub(jwt_config: JWTConfig):
    class Service(pbg.ExampleServiceServicer):
        async def Echo(self, request, context):  # noqa: N802
            claims = RequestContext().claims or {}
            return pb.EchoResponse(message=claims.get("sub", ""))

        async def EchoStream(self, request, context):  # noqa: N802
            claims = RequestContext().claims or {}
            yield pb.EchoResponse(message=claims.get("sub", ""))

    server = create_grpc_server(
        ServerGRPCConfig(host="127.0.0.1", port=0),
        auth=JWTAuthInterceptor(jwt_config, scopes=["widgets:read"]),
    )
    pbg.add_ExampleServiceServicer_to_server(Service(), server)
    await server.start()
    port = server.pythonforge_port
    try:
        async with create_channel(f"127.0.0.1:{port}", force_insecure=True) as channel:
            yield pbg.ExampleServiceStub(channel)
    finally:
        await server.stop(grace=None)


async def test_grpc_valid_token_is_accepted(authenticated_stub, token: str) -> None:
    response = await authenticated_stub.Echo(
        pb.EchoRequest(message="x"), metadata=(("authorization", f"Bearer {token}"),)
    )
    assert response.message == "user-1"


async def test_grpc_missing_token_is_unauthenticated(authenticated_stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await authenticated_stub.Echo(pb.EchoRequest(message="x"))
    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_grpc_invalid_token_is_unauthenticated(authenticated_stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await authenticated_stub.Echo(
            pb.EchoRequest(message="x"), metadata=(("authorization", "Bearer forged"),)
        )
    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_grpc_missing_scope_is_permission_denied(
    authenticated_stub, jwt_config: JWTConfig
) -> None:
    unscoped = encode_token(jwt_config, Claims(sub="user-2"))
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        await authenticated_stub.Echo(
            pb.EchoRequest(message="x"), metadata=(("authorization", f"Bearer {unscoped}"),)
        )
    assert exc_info.value.code() == grpc.StatusCode.PERMISSION_DENIED


async def test_grpc_streaming_rpc_is_also_authenticated(authenticated_stub) -> None:
    with pytest.raises(grpc.aio.AioRpcError) as exc_info:
        [item async for item in authenticated_stub.EchoStream(pb.EchoRequest(message="x"))]
    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


async def test_grpc_health_check_is_exempt_from_auth(jwt_config: JWTConfig) -> None:
    """Health probes must work without credentials, or orchestrators can't use them."""
    from grpc_health.v1 import health_pb2, health_pb2_grpc

    server = create_grpc_server(
        ServerGRPCConfig(host="127.0.0.1", port=0), auth=JWTAuthInterceptor(jwt_config)
    )
    await server.start()
    port = server.pythonforge_port
    try:
        async with create_channel(f"127.0.0.1:{port}", force_insecure=True) as channel:
            response = await health_pb2_grpc.HealthStub(channel).Check(
                health_pb2.HealthCheckRequest()
            )
            assert response.status == health_pb2.HealthCheckResponse.SERVING
    finally:
        await server.stop(grace=None)


# --- Parity ------------------------------------------------------------


async def test_the_same_token_is_accepted_by_both_transports(
    http_client: TestClient, authenticated_stub, token: str
) -> None:
    http_response = http_client.get("/private", headers={"Authorization": f"Bearer {token}"})
    rpc_response = await authenticated_stub.Echo(
        pb.EchoRequest(message="x"), metadata=(("authorization", f"Bearer {token}"),)
    )
    assert http_response.json()["sub"] == rpc_response.message == "user-1"
