"""Public exception hierarchy shared by every PythonForge module.

External failures (pydantic validation, httpx errors, future grpc/KMS errors)
must be translated to one of these before crossing a public API boundary, so
callers can depend on a stable set of types instead of third-party exceptions.
The original error is preserved via exception chaining (``raise ... from
cause``) for diagnostics, but public messages must never leak secret values.
"""

from __future__ import annotations


class PythonForgeError(Exception):
    """Base class for every error raised by PythonForge's public API."""


class ConfigurationError(PythonForgeError):
    """Configuration failed to load or validate."""


class TransportError(PythonForgeError):
    """An HTTP or gRPC transport operation failed."""


class AuthenticationError(PythonForgeError):
    """A caller's identity could not be established."""


class AuthorizationError(PythonForgeError):
    """A caller was identified but is not allowed to perform the operation."""


class MissingExtraError(PythonForgeError):
    """An optional capability was invoked without its extra installed."""

    def __init__(self, extra: str, feature: str) -> None:
        self.extra = extra
        self.feature = feature
        super().__init__(
            f"{feature} requires the '{extra}' extra: install it with "
            f"pip install 'pythonforge[{extra}]'"
        )
