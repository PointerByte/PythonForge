"""The KMS abstraction every cloud adapter implements.

Defined as a :class:`typing.Protocol`, not a base class, so tests can supply
a plain object with the right methods -- no credentials, no network, no
inheritance from a provider-specific type.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class KMSProvider(Protocol):
    """Envelope-style operations performed by the provider, keyed by reference.

    Implementations must translate provider errors into
    :class:`pythonforge.errors.ProviderError` so callers never have to catch
    boto3/azure/google exception types.
    """

    name: str

    async def encrypt(self, key_reference: str, plaintext: bytes) -> bytes: ...

    async def decrypt(self, key_reference: str, ciphertext: bytes) -> bytes: ...

    async def sign(self, key_reference: str, data: bytes) -> bytes: ...

    async def verify(self, key_reference: str, data: bytes, signature: bytes) -> bool: ...


class InMemoryKMS:
    """A deterministic fake for tests and local development.

    Emphatically not secure -- it XORs against a derived keystream and
    "signs" with HMAC. It exists so code paths that talk to a KMS can be
    exercised without cloud credentials.
    """

    name = "in-memory"

    def __init__(self, keys: dict[str, bytes] | None = None) -> None:
        self._keys = keys or {}

    def add_key(self, reference: str, secret: bytes) -> None:
        self._keys[reference] = secret

    def _key(self, reference: str) -> bytes:
        from ...errors import ProviderError

        try:
            return self._keys[reference]
        except KeyError as exc:
            raise ProviderError(f"unknown key reference: {reference}") from exc

    async def encrypt(self, key_reference: str, plaintext: bytes) -> bytes:
        from ..local.symmetric import encrypt
        from ..keys import KeyData

        return encrypt(KeyData(kind="symmetric", secret=self._key(key_reference)), plaintext)

    async def decrypt(self, key_reference: str, ciphertext: bytes) -> bytes:
        from ..local.symmetric import decrypt
        from ..keys import KeyData

        return decrypt(KeyData(kind="symmetric", secret=self._key(key_reference)), ciphertext)

    async def sign(self, key_reference: str, data: bytes) -> bytes:
        from ..local.hashing import hmac_sha256

        return hmac_sha256(self._key(key_reference), data)

    async def verify(self, key_reference: str, data: bytes, signature: bytes) -> bool:
        from ..local.hashing import verify_hmac_sha256

        return verify_hmac_sha256(self._key(key_reference), data, signature)
