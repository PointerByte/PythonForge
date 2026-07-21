"""Guarded import of grpcio, so `import pythonforge` never requires the extra.

Every module under ``pythonforge.transport.grpc`` imports grpc through here,
which turns a missing extra into an actionable :class:`MissingExtraError`
instead of a bare ``ModuleNotFoundError``.
"""

from __future__ import annotations

from typing import Any

from ...errors import MissingExtraError


def require_grpc() -> Any:
    """Return the ``grpc`` module, or raise naming the extra to install."""
    try:
        import grpc
    except ImportError as exc:
        raise MissingExtraError(extra="grpc", feature="The gRPC transport") from exc
    return grpc


def require_grpc_aio() -> Any:
    """Return the ``grpc.aio`` module, or raise naming the extra to install."""
    return require_grpc().aio


def require_grpc_health() -> tuple[Any, Any]:
    """Return ``(health servicer module, health_pb2_grpc)`` for grpc.health.v1."""
    try:
        from grpc_health.v1 import health, health_pb2_grpc
    except ImportError as exc:
        raise MissingExtraError(extra="grpc", feature="The gRPC health service") from exc
    return health, health_pb2_grpc
