"""AES-GCM authenticated encryption."""

from __future__ import annotations

import os

from ...errors import CryptographyError
from ..keys import KeyData

NONCE_SIZE = 12  # 96 bits, the size AES-GCM is specified for.
KEY_SIZES = (16, 24, 32)


def _aesgcm():  # type: ignore[no-untyped-def]
    from ...security._optional import require_cryptography

    require_cryptography()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM


def generate_key(size: int = 32) -> KeyData:
    if size not in KEY_SIZES:
        raise CryptographyError(f"AES key size must be one of {KEY_SIZES} bytes")
    return KeyData(kind="symmetric", provider="local", secret=os.urandom(size))


def encrypt(key: KeyData, plaintext: bytes, *, associated_data: bytes | None = None) -> bytes:
    """Encrypt with AES-GCM, returning ``nonce || ciphertext || tag``.

    A fresh random nonce per call is essential: reusing a nonce with the
    same key breaks GCM catastrophically, so it is generated here rather
    than being a caller-supplied parameter.
    """
    if not key.secret:
        raise CryptographyError("encryption requires a key with secret material")
    nonce = os.urandom(NONCE_SIZE)
    try:
        ciphertext = _aesgcm()(key.secret).encrypt(nonce, plaintext, associated_data)
    except Exception as exc:
        raise CryptographyError("AES-GCM encryption failed") from exc
    return nonce + ciphertext


def decrypt(key: KeyData, payload: bytes, *, associated_data: bytes | None = None) -> bytes:
    """Decrypt a ``nonce || ciphertext || tag`` payload produced by :func:`encrypt`."""
    if not key.secret:
        raise CryptographyError("decryption requires a key with secret material")
    if len(payload) <= NONCE_SIZE:
        raise CryptographyError("ciphertext is too short to be valid")
    nonce, ciphertext = payload[:NONCE_SIZE], payload[NONCE_SIZE:]
    try:
        return bytes(_aesgcm()(key.secret).decrypt(nonce, ciphertext, associated_data))
    except Exception as exc:
        # Never distinguish "bad tag" from "bad key" from "corrupt data".
        raise CryptographyError("AES-GCM decryption failed") from exc
