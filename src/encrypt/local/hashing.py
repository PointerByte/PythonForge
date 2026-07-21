"""Hashes and MACs: SHA-256, HMAC-SHA256 and BLAKE3."""

from __future__ import annotations

import hashlib
import hmac

from ...errors import CryptographyError, MissingExtraError


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    if not key:
        raise CryptographyError("HMAC requires a non-empty key")
    return hmac.new(key, data, hashlib.sha256).digest()


def verify_hmac_sha256(key: bytes, data: bytes, expected: bytes) -> bool:
    """Constant-time comparison -- a plain ``==`` here leaks the MAC by timing."""
    return hmac.compare_digest(hmac_sha256(key, data), expected)


def blake3(data: bytes, *, key: bytes | None = None, length: int = 32) -> bytes:
    """BLAKE3 digest, optionally keyed.

    Ships with the ``security`` extra; the import is deferred so the rest of
    this module works even when it is unavailable.
    """
    try:
        import blake3 as _blake3
    except ImportError as exc:
        raise MissingExtraError(extra="security", feature="BLAKE3 hashing") from exc

    if key is not None:
        if len(key) != 32:
            raise CryptographyError("keyed BLAKE3 requires a 32-byte key")
        return bytes(_blake3.blake3(data, key=key).digest(length=length))
    return bytes(_blake3.blake3(data).digest(length=length))
