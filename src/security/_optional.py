"""Guarded imports for the ``security`` extra (PyJWT + cryptography)."""

from __future__ import annotations

from typing import Any

from ..errors import MissingExtraError


def require_jwt() -> Any:
    try:
        import jwt
    except ImportError as exc:
        raise MissingExtraError(extra="security", feature="JWT support") from exc
    return jwt


def require_cryptography() -> Any:
    try:
        import cryptography
    except ImportError as exc:
        raise MissingExtraError(extra="security", feature="Cryptography support") from exc
    return cryptography
