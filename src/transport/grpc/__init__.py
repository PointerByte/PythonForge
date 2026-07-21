"""gRPC transport (requires the ``grpc`` extra).

Importing this package without ``pythonforge[grpc]`` installed raises
:class:`pythonforge.errors.MissingExtraError` naming the extra, rather than
a bare ``ModuleNotFoundError``.
"""

from .client import context_metadata, context_timeout, create_channel
from .interceptors import (
    ErrorInterceptor,
    HandlerWrappingInterceptor,
    LoggingInterceptor,
    RequestContextInterceptor,
)
from .server import create_grpc_server, default_interceptors

__all__ = [
    "ErrorInterceptor",
    "HandlerWrappingInterceptor",
    "LoggingInterceptor",
    "RequestContextInterceptor",
    "context_metadata",
    "context_timeout",
    "create_channel",
    "create_grpc_server",
    "default_interceptors",
]
