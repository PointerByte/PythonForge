"""KMS adapters, exercised entirely through injected doubles.

No credentials, no network: each cloud client is replaced by a fake that
records what it was asked and returns canned responses.
"""

from __future__ import annotations

from typing import Any

import pytest

from pythonforge.encrypt.kms import InMemoryKMS, KMSProvider
from pythonforge.errors import ProviderError

KEY = b"k" * 32


# --- In-memory provider ------------------------------------------------


async def test_in_memory_kms_round_trip() -> None:
    kms = InMemoryKMS({"alias/test": KEY})
    assert await kms.decrypt("alias/test", await kms.encrypt("alias/test", b"msg")) == b"msg"


async def test_in_memory_kms_sign_verify() -> None:
    kms = InMemoryKMS({"alias/test": KEY})
    signature = await kms.sign("alias/test", b"payload")
    assert await kms.verify("alias/test", b"payload", signature)
    assert not await kms.verify("alias/test", b"tampered", signature)


async def test_in_memory_kms_unknown_reference_raises_provider_error() -> None:
    kms = InMemoryKMS()
    with pytest.raises(ProviderError, match="unknown key reference"):
        await kms.encrypt("alias/missing", b"msg")


def test_in_memory_kms_satisfies_the_protocol() -> None:
    assert isinstance(InMemoryKMS(), KMSProvider)


def test_add_key_registers_a_reference() -> None:
    kms = InMemoryKMS()
    kms.add_key("alias/new", KEY)
    assert isinstance(kms, KMSProvider)


# --- AWS ---------------------------------------------------------------


class FakeBoto3KMS:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail = fail

    def _record(self, name: str, kwargs: dict[str, Any]) -> None:
        if self._fail:
            raise RuntimeError("AWS is down")
        self.calls.append((name, kwargs))

    def encrypt(self, **kwargs: Any) -> dict[str, Any]:
        self._record("encrypt", kwargs)
        return {"CiphertextBlob": b"aws-ciphertext"}

    def decrypt(self, **kwargs: Any) -> dict[str, Any]:
        self._record("decrypt", kwargs)
        return {"Plaintext": b"aws-plaintext"}

    def sign(self, **kwargs: Any) -> dict[str, Any]:
        self._record("sign", kwargs)
        return {"Signature": b"aws-signature"}

    def verify(self, **kwargs: Any) -> dict[str, Any]:
        self._record("verify", kwargs)
        return {"SignatureValid": True}


async def test_aws_provider_uses_the_injected_client() -> None:
    from pythonforge.encrypt.kms.aws import AWSKMSProvider

    client = FakeBoto3KMS()
    provider = AWSKMSProvider(client=client)

    assert await provider.encrypt("arn:key", b"msg") == b"aws-ciphertext"
    assert await provider.decrypt("arn:key", b"blob") == b"aws-plaintext"
    assert await provider.sign("arn:key", b"data") == b"aws-signature"
    assert await provider.verify("arn:key", b"data", b"sig") is True

    assert [name for name, _ in client.calls] == ["encrypt", "decrypt", "sign", "verify"]
    assert client.calls[0][1]["KeyId"] == "arn:key"


async def test_aws_provider_translates_failures_to_provider_error() -> None:
    from pythonforge.encrypt.kms.aws import AWSKMSProvider

    provider = AWSKMSProvider(client=FakeBoto3KMS(fail=True))
    with pytest.raises(ProviderError, match="AWS KMS encrypt failed"):
        await provider.encrypt("arn:key", b"msg")


def test_aws_provider_satisfies_the_protocol() -> None:
    from pythonforge.encrypt.kms.aws import AWSKMSProvider

    assert isinstance(AWSKMSProvider(client=FakeBoto3KMS()), KMSProvider)


# --- Azure -------------------------------------------------------------


class FakeAzureResult:
    def __init__(self, **attributes: Any) -> None:
        self.__dict__.update(attributes)


class FakeAzureCryptoClient:
    def __init__(self, reference: str, *, fail: bool = False) -> None:
        self.reference = reference
        self._fail = fail

    def _guard(self) -> None:
        if self._fail:
            raise RuntimeError("Azure is down")

    async def encrypt(self, algorithm: str, plaintext: bytes) -> FakeAzureResult:
        self._guard()
        return FakeAzureResult(ciphertext=b"azure-ciphertext")

    async def decrypt(self, algorithm: str, ciphertext: bytes) -> FakeAzureResult:
        self._guard()
        return FakeAzureResult(plaintext=b"azure-plaintext")

    async def sign(self, algorithm: str, data: bytes) -> FakeAzureResult:
        self._guard()
        return FakeAzureResult(signature=b"azure-signature")

    async def verify(self, algorithm: str, data: bytes, signature: bytes) -> FakeAzureResult:
        self._guard()
        return FakeAzureResult(is_valid=True)


async def test_azure_provider_uses_the_injected_factory() -> None:
    from pythonforge.encrypt.kms.azure import AzureKeyVaultProvider

    provider = AzureKeyVaultProvider(client_factory=FakeAzureCryptoClient)

    assert await provider.encrypt("https://vault/keys/k", b"msg") == b"azure-ciphertext"
    assert await provider.decrypt("https://vault/keys/k", b"blob") == b"azure-plaintext"
    assert await provider.sign("https://vault/keys/k", b"data") == b"azure-signature"
    assert await provider.verify("https://vault/keys/k", b"data", b"sig") is True


async def test_azure_provider_translates_failures_to_provider_error() -> None:
    from pythonforge.encrypt.kms.azure import AzureKeyVaultProvider

    provider = AzureKeyVaultProvider(
        client_factory=lambda reference: FakeAzureCryptoClient(reference, fail=True)
    )
    with pytest.raises(ProviderError, match="Azure Key Vault encrypt failed"):
        await provider.encrypt("https://vault/keys/k", b"msg")


# --- GCP ---------------------------------------------------------------


class FakeGCPResponse:
    def __init__(self, **attributes: Any) -> None:
        self.__dict__.update(attributes)


class FakeGCPClient:
    def __init__(self, *, fail: bool = False, public_pem: bytes = b"") -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self._fail = fail
        self._public_pem = public_pem

    def _guard(self, name: str, request: dict[str, Any]) -> None:
        if self._fail:
            raise RuntimeError("GCP is down")
        self.requests.append((name, request))

    def encrypt(self, request: dict[str, Any]) -> FakeGCPResponse:
        self._guard("encrypt", request)
        return FakeGCPResponse(ciphertext=b"gcp-ciphertext")

    def decrypt(self, request: dict[str, Any]) -> FakeGCPResponse:
        self._guard("decrypt", request)
        return FakeGCPResponse(plaintext=b"gcp-plaintext")

    def asymmetric_sign(self, request: dict[str, Any]) -> FakeGCPResponse:
        self._guard("asymmetric_sign", request)
        return FakeGCPResponse(signature=b"gcp-signature")

    def get_public_key(self, request: dict[str, Any]) -> FakeGCPResponse:
        self._guard("get_public_key", request)
        return FakeGCPResponse(pem=self._public_pem.decode())


async def test_gcp_provider_uses_the_injected_client() -> None:
    from pythonforge.encrypt.kms.gcp import GCPKMSProvider

    client = FakeGCPClient()
    provider = GCPKMSProvider(client=client)

    assert await provider.encrypt("projects/k", b"msg") == b"gcp-ciphertext"
    assert await provider.decrypt("projects/k", b"blob") == b"gcp-plaintext"
    assert await provider.sign("projects/k", b"data") == b"gcp-signature"

    # The signing request must carry a SHA-256 digest, not the raw payload.
    sign_request = dict(client.requests)["asymmetric_sign"]
    assert len(sign_request["digest"]["sha256"]) == 32


async def test_gcp_verify_checks_the_signature_against_the_public_key() -> None:
    from pythonforge.encrypt.kms.gcp import GCPKMSProvider
    from pythonforge.encrypt.local import generate_rsa_key, rsa_sign

    key = generate_rsa_key()
    assert key.public
    signature = rsa_sign(key, b"data")

    provider = GCPKMSProvider(client=FakeGCPClient(public_pem=key.public))
    assert await provider.verify("projects/k", b"data", signature) is True
    assert await provider.verify("projects/k", b"tampered", signature) is False


async def test_gcp_provider_translates_failures_to_provider_error() -> None:
    from pythonforge.encrypt.kms.gcp import GCPKMSProvider

    provider = GCPKMSProvider(client=FakeGCPClient(fail=True))
    with pytest.raises(ProviderError, match="Google Cloud KMS encrypt failed"):
        await provider.encrypt("projects/k", b"msg")
