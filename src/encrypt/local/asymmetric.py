"""RSA-OAEP encryption, RSA/Ed25519 signatures, and ECDH key agreement."""

from __future__ import annotations

from typing import Any

from ...errors import CryptographyError
from ...security._optional import require_cryptography
from ..keys import KeyData


def _primitives() -> Any:
    require_cryptography()
    from cryptography.hazmat.primitives import hashes, serialization

    return hashes, serialization


# --- RSA ---------------------------------------------------------------


def generate_rsa_key(key_size: int = 2048) -> KeyData:
    require_cryptography()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    if key_size < 2048:
        raise CryptographyError("RSA keys below 2048 bits are not allowed")

    private = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    return KeyData(
        kind="rsa",
        provider="local",
        secret=private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        public=private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def _load_private(key: KeyData) -> Any:
    if not key.secret:
        raise CryptographyError("operation requires a key with private material")
    _, serialization = _primitives()
    try:
        return serialization.load_pem_private_key(key.secret, password=None)
    except Exception as exc:
        raise CryptographyError("could not load private key") from exc


def _load_public(key: KeyData) -> Any:
    if not key.public:
        raise CryptographyError("operation requires a key with public material")
    _, serialization = _primitives()
    try:
        return serialization.load_pem_public_key(key.public)
    except Exception as exc:
        raise CryptographyError("could not load public key") from exc


def rsa_encrypt(key: KeyData, plaintext: bytes) -> bytes:
    """RSA-OAEP with SHA-256. Only for small payloads (keys, not documents)."""
    hashes, _ = _primitives()
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        return bytes(
            _load_public(key).encrypt(
                plaintext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        )
    except CryptographyError:
        raise
    except Exception as exc:
        raise CryptographyError("RSA-OAEP encryption failed") from exc


def rsa_decrypt(key: KeyData, ciphertext: bytes) -> bytes:
    hashes, _ = _primitives()
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        return bytes(
            _load_private(key).decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        )
    except CryptographyError:
        raise
    except Exception as exc:
        raise CryptographyError("RSA-OAEP decryption failed") from exc


def rsa_sign(key: KeyData, data: bytes) -> bytes:
    """RSA-PSS with SHA-256."""
    hashes, _ = _primitives()
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        return bytes(
            _load_private(key).sign(
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
        )
    except CryptographyError:
        raise
    except Exception as exc:
        raise CryptographyError("RSA signing failed") from exc


def rsa_verify(key: KeyData, data: bytes, signature: bytes) -> bool:
    """Return ``False`` on a bad signature rather than raising."""
    hashes, _ = _primitives()
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        _load_public(key).verify(
            signature,
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except CryptographyError:
        raise
    except Exception:
        return False
    return True


# --- Ed25519 -----------------------------------------------------------


def generate_ed25519_key() -> KeyData:
    require_cryptography()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    private = ed25519.Ed25519PrivateKey.generate()
    return KeyData(
        kind="ed25519",
        provider="local",
        secret=private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        public=private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def ed25519_sign(key: KeyData, data: bytes) -> bytes:
    try:
        return bytes(_load_private(key).sign(data))
    except CryptographyError:
        raise
    except Exception as exc:
        raise CryptographyError("Ed25519 signing failed") from exc


def ed25519_verify(key: KeyData, data: bytes, signature: bytes) -> bool:
    try:
        _load_public(key).verify(signature, data)
    except CryptographyError:
        raise
    except Exception:
        return False
    return True


# --- ECDH --------------------------------------------------------------


def generate_ec_key() -> KeyData:
    """A P-256 key pair for ECDH key agreement."""
    require_cryptography()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    return KeyData(
        kind="ec",
        provider="local",
        secret=private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        public=private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def ecdh_shared_key(
    private_key: KeyData, peer_key: KeyData, *, length: int = 32, info: bytes = b""
) -> bytes:
    """Derive a shared secret via ECDH, run through HKDF-SHA256.

    The raw ECDH output is not uniformly random and must never be used as a
    key directly, hence the mandatory KDF step.
    """
    hashes, _ = _primitives()
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    try:
        shared = _load_private(private_key).exchange(ec.ECDH(), _load_public(peer_key))
        return bytes(
            HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=info).derive(shared)
        )
    except CryptographyError:
        raise
    except Exception as exc:
        raise CryptographyError("ECDH key agreement failed") from exc
