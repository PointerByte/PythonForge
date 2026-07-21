from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ...config import ServerGRPCConfig
from ...errors import ConfigurationError
from ._optional import require_grpc, require_grpc_aio, require_grpc_health
from .interceptors.context import RequestContextInterceptor
from .interceptors.errors import ErrorInterceptor
from .interceptors.logging import LoggingInterceptor


def _read(path: str | None, label: str) -> bytes:
    if path is None:
        raise ConfigurationError(f"server.grpc: {label} is required when TLS is enabled")
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ConfigurationError(f"server.grpc: cannot read {label} at {path}") from exc


def build_server_credentials(config: ServerGRPCConfig) -> Any:
    """Build ``grpc.ServerCredentials`` from a config, or ``None`` for plaintext."""
    if not config.tls_enabled:
        return None
    grpc = require_grpc()
    certificate = _read(config.cert_file, "cert_file")
    key = _read(config.key_file, "key_file")
    root_certificates = _read(config.ca_file, "ca_file") if config.mtls_required else None
    return grpc.ssl_server_credentials(
        [(key, certificate)],
        root_certificates=root_certificates,
        require_client_auth=config.mtls_required,
    )


def default_interceptors(auth: Any | None = None) -> list[Any]:
    """The standard chain, listed outermost first.

    Order is load-bearing. ``interceptors[0]`` wraps everything after it, so:

    1. **context** binds the RequestContext, making request/trace ids
       available to every layer below (including the log entry).
    2. **logging** observes the final status of the call, whatever produced it.
    3. **errors** converts exceptions into gRPC status codes -- it must sit
       *outside* auth, otherwise an authentication failure bypasses it and
       surfaces as an unhandled crash instead of UNAUTHENTICATED.
    4. **auth** (optional) rejects the call before the handler runs.
    """
    chain = [RequestContextInterceptor(), LoggingInterceptor(), ErrorInterceptor()]
    if auth is not None:
        chain.append(auth)
    return chain


def create_grpc_server(
    config: ServerGRPCConfig,
    *,
    auth: Any | None = None,
    interceptors: Sequence[Any] | None = None,
    enable_health: bool = True,
    options: Sequence[tuple[str, Any]] | None = None,
) -> Any:
    """Create a configured (but not started) ``grpc.aio.Server``.

    The caller registers its own servicers on the returned server and then
    awaits ``server.start()``; ``pythonforge.transport.ServiceRuntime``
    handles the lifecycle.

    Pass ``auth`` (a ``JWTAuthInterceptor``) to add authentication at the
    correct position in the default chain; pass ``interceptors`` to replace
    the chain outright, in which case ordering is your responsibility -- see
    :func:`default_interceptors`.
    """
    aio = require_grpc_aio()

    channel_options: list[tuple[str, Any]] = [
        ("grpc.max_send_message_length", config.max_message_length),
        ("grpc.max_receive_message_length", config.max_message_length),
        *(options or []),
    ]

    server = aio.server(
        interceptors=list(default_interceptors(auth) if interceptors is None else interceptors),
        options=channel_options,
    )

    if enable_health:
        health, health_pb2_grpc = require_grpc_health()
        health_servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
        # Exposed so readiness can flip services to NOT_SERVING while draining.
        server.pythonforge_health = health_servicer

    credentials = build_server_credentials(config)
    address = f"{config.host}:{config.port}"
    if credentials is None:
        bound_port = server.add_insecure_port(address)
    else:
        bound_port = server.add_secure_port(address, credentials)

    if bound_port == 0:
        raise ConfigurationError(f"server.grpc: could not bind {address}")
    # With port 0 the OS picks an ephemeral port; expose the real one so
    # integration tests (and callers) know where the server actually listens.
    server.pythonforge_port = bound_port

    return server
