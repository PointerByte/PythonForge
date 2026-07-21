"""AWS KMS adapter (requires the ``aws`` extra).

boto3 is synchronous, so every call is pushed to a worker thread rather
than blocking the event loop. The client is injectable, which is what makes
this testable without credentials or network.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ...errors import MissingExtraError, ProviderError


def _require_boto3() -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise MissingExtraError(extra="aws", feature="The AWS KMS provider") from exc
    return boto3


class AWSKMSProvider:
    name = "aws"

    def __init__(self, client: Any | None = None, *, region_name: str | None = None) -> None:
        """``client`` accepts a preconfigured (or fake) boto3 KMS client."""
        self._client = (
            client
            if client is not None
            else _require_boto3().client("kms", region_name=region_name)
        )

    async def _call(self, operation: str, **kwargs: Any) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(getattr(self._client, operation), **kwargs)
        except Exception as exc:
            raise ProviderError(f"AWS KMS {operation} failed") from exc

    async def encrypt(self, key_reference: str, plaintext: bytes) -> bytes:
        response = await self._call("encrypt", KeyId=key_reference, Plaintext=plaintext)
        return bytes(response["CiphertextBlob"])

    async def decrypt(self, key_reference: str, ciphertext: bytes) -> bytes:
        response = await self._call("decrypt", KeyId=key_reference, CiphertextBlob=ciphertext)
        return bytes(response["Plaintext"])

    async def sign(
        self, key_reference: str, data: bytes, *, algorithm: str = "RSASSA_PSS_SHA_256"
    ) -> bytes:
        response = await self._call(
            "sign", KeyId=key_reference, Message=data, SigningAlgorithm=algorithm
        )
        return bytes(response["Signature"])

    async def verify(
        self,
        key_reference: str,
        data: bytes,
        signature: bytes,
        *,
        algorithm: str = "RSASSA_PSS_SHA_256",
    ) -> bool:
        response = await self._call(
            "verify",
            KeyId=key_reference,
            Message=data,
            Signature=signature,
            SigningAlgorithm=algorithm,
        )
        return bool(response.get("SignatureValid", False))
