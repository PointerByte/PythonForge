from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ...config import ClientConfig
from ...context import RequestContext
from ...errors import ConfigurationError, TransportError
from ._optional import require_grpc, require_grpc_aio


def _read(path: str | None) -> bytes | None:
    if path is None:
        return None
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ConfigurationError(f"client: cannot read TLS material at {path}") from exc


def build_channel_credentials(config: ClientConfig) -> Any:
    """Build ``grpc.ChannelCredentials``, or ``None`` for an insecure channel."""
    if not config.verify and not config.ca_file and not config.cert_file:
        return None
    grpc = require_grpc()
    return grpc.ssl_channel_credentials(
        root_certificates=_read(config.ca_file),
        private_key=_read(config.key_file),
        certificate_chain=_read(config.cert_file),
    )


def create_channel(
    target: str,
    config: ClientConfig | None = None,
    *,
    options: Sequence[tuple[str, Any]] | None = None,
    force_insecure: bool = False,
) -> Any:
    """Create a ``grpc.aio.Channel`` honouring the TLS/mTLS settings in ``config``.

    ``force_insecure`` is for local development and tests against a
    plaintext server; production callers should leave it alone.
    """
    aio = require_grpc_aio()
    config = config or ClientConfig()
    credentials = None if force_insecure else build_channel_credentials(config)
    if credentials is None:
        return aio.insecure_channel(target, options=list(options or []))
    return aio.secure_channel(target, credentials, options=list(options or []))


def context_metadata() -> list[tuple[str, str]]:
    """Metadata carrying the current :class:`RequestContext` to a downstream RPC.

    The same keys the HTTP client sends as headers, so a request keeps one
    identity as it crosses transports.
    """
    ctx = RequestContext()
    metadata: list[tuple[str, str]] = []
    if ctx.request_id:
        metadata.append(("x-request-id", ctx.request_id))
    if ctx.trace_context:
        metadata.append(("traceparent", ctx.trace_context.to_traceparent()))
        if ctx.trace_context.tracestate:
            metadata.append(("tracestate", ctx.trace_context.to_tracestate()))
    return metadata


def context_timeout(configured_timeout: float | None = None) -> float | None:
    """Clamp a call timeout to the current context deadline, if any.

    Raises :class:`TransportError` when the deadline has already passed, so
    an expired request never opens a new downstream call.
    """
    ctx = RequestContext()
    if ctx.deadline is None:
        return configured_timeout
    remaining = ctx.deadline - time.time()
    if remaining <= 0:
        raise TransportError("deadline exceeded before starting the RPC")
    if configured_timeout is None:
        return remaining
    return min(configured_timeout, remaining)
