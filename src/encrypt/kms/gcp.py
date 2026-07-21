"""Google Cloud KMS adapter (requires the ``gcp`` extra)."""

from __future__ import annotations

import asyncio
from typing import Any

from ...errors import MissingExtraError, ProviderError


def _require_gcp() -> Any:
    try:
        from google.cloud import kms
    except ImportError as exc:
        raise MissingExtraError(extra="gcp", feature="The Google Cloud KMS provider") from exc
    return kms


class GCPKMSProvider:
    """``key_reference`` is the fully-qualified crypto key (version) name."""

    name = "gcp"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client if client is not None else _require_gcp().KeyManagementServiceClient()

    async def _call(self, operation: str, request: dict[str, Any]) -> Any:
        try:
            return await asyncio.to_thread(getattr(self._client, operation), request=request)
        except Exception as exc:
            raise ProviderError(f"Google Cloud KMS {operation} failed") from exc

    async def encrypt(self, key_reference: str, plaintext: bytes) -> bytes:
        response = await self._call("encrypt", {"name": key_reference, "plaintext": plaintext})
        return bytes(response.ciphertext)

    async def decrypt(self, key_reference: str, ciphertext: bytes) -> bytes:
        response = await self._call("decrypt", {"name": key_reference, "ciphertext": ciphertext})
        return bytes(response.plaintext)

    async def sign(self, key_reference: str, data: bytes) -> bytes:
        from ..local.hashing import sha256

        response = await self._call(
            "asymmetric_sign", {"name": key_reference, "digest": {"sha256": sha256(data)}}
        )
        return bytes(response.signature)

    async def verify(self, key_reference: str, data: bytes, signature: bytes) -> bool:
        """Cloud KMS has no verify RPC -- verification happens locally against
        the public key it hands out."""
        from ..keys import KeyData
        from ..local.asymmetric import rsa_verify

        response = await self._call("get_public_key", {"name": key_reference})
        public_pem = response.pem.encode() if isinstance(response.pem, str) else response.pem
        return rsa_verify(KeyData(kind="rsa", provider="gcp", public=public_pem), data, signature)
