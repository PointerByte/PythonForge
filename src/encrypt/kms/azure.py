"""Azure Key Vault adapter (requires the ``azure`` extra)."""

from __future__ import annotations

from typing import Any

from ...errors import MissingExtraError, ProviderError


def _require_azure() -> tuple[Any, Any]:
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.keyvault.keys.crypto.aio import CryptographyClient
    except ImportError as exc:
        raise MissingExtraError(extra="azure", feature="The Azure Key Vault provider") from exc
    return CryptographyClient, DefaultAzureCredential


class AzureKeyVaultProvider:
    """``key_reference`` is the full key identifier URL.

    ``client_factory`` exists so tests can inject a fake without touching
    Azure identity resolution.
    """

    name = "azure"

    def __init__(
        self,
        client_factory: Any | None = None,
        *,
        credential: Any | None = None,
        encryption_algorithm: str = "RSA-OAEP-256",
        signing_algorithm: str = "PS256",
    ) -> None:
        self._encryption_algorithm = encryption_algorithm
        self._signing_algorithm = signing_algorithm
        if client_factory is not None:
            self._client_factory = client_factory
        else:
            CryptographyClient, DefaultAzureCredential = _require_azure()
            resolved = credential or DefaultAzureCredential()
            self._client_factory = lambda reference: CryptographyClient(reference, resolved)

    async def _client(self, key_reference: str) -> Any:
        return self._client_factory(key_reference)

    async def encrypt(self, key_reference: str, plaintext: bytes) -> bytes:
        try:
            client = await self._client(key_reference)
            result = await client.encrypt(self._encryption_algorithm, plaintext)
            return bytes(result.ciphertext)
        except Exception as exc:
            raise ProviderError("Azure Key Vault encrypt failed") from exc

    async def decrypt(self, key_reference: str, ciphertext: bytes) -> bytes:
        try:
            client = await self._client(key_reference)
            result = await client.decrypt(self._encryption_algorithm, ciphertext)
            return bytes(result.plaintext)
        except Exception as exc:
            raise ProviderError("Azure Key Vault decrypt failed") from exc

    async def sign(self, key_reference: str, data: bytes) -> bytes:
        try:
            client = await self._client(key_reference)
            result = await client.sign(self._signing_algorithm, data)
            return bytes(result.signature)
        except Exception as exc:
            raise ProviderError("Azure Key Vault sign failed") from exc

    async def verify(self, key_reference: str, data: bytes, signature: bytes) -> bool:
        try:
            client = await self._client(key_reference)
            result = await client.verify(self._signing_algorithm, data, signature)
            return bool(result.is_valid)
        except Exception as exc:
            raise ProviderError("Azure Key Vault verify failed") from exc
