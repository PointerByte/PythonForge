"""Recursive, case-insensitive redaction applied before anything reaches a sink.

``Authorization`` and ``Cookie`` are always redacted regardless of config, per
the observability spec; ``LoggerConfig.sensitive_keys`` extends the set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "***REDACTED***"

ALWAYS_SENSITIVE = frozenset({"authorization", "cookie"})
DEFAULT_SENSITIVE_KEYS = ALWAYS_SENSITIVE | frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "set-cookie",
    }
)


def redact(data: Any, extra_sensitive_keys: Sequence[str] = ()) -> Any:
    """Return a copy of ``data`` with sensitive values replaced by :data:`REDACTED`.

    Traverses dicts, lists and tuples at any depth; other types pass through
    unchanged. Keys are matched case-insensitively.
    """
    sensitive = DEFAULT_SENSITIVE_KEYS | {key.lower() for key in extra_sensitive_keys}
    return _redact(data, sensitive)


def _redact(data: Any, sensitive: frozenset[str]) -> Any:
    if isinstance(data, Mapping):
        return {
            key: REDACTED if str(key).lower() in sensitive else _redact(value, sensitive)
            for key, value in data.items()
        }
    if isinstance(data, list | tuple):
        redacted = [_redact(item, sensitive) for item in data]
        return type(data)(redacted) if isinstance(data, tuple) else redacted
    return data
