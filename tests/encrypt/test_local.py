from __future__ import annotations

import pytest

from pythonforge.encrypt import KeyData
from pythonforge.encrypt.local import (
    decrypt,
    ecdh_shared_key,
    ed25519_sign,
    ed25519_verify,
    encrypt,
    generate_ec_key,
    generate_ed25519_key,
    generate_key,
    generate_rsa_key,
    hmac_sha256,
    rsa_decrypt,
    rsa_encrypt,
    rsa_sign,
    rsa_verify,
    sha256,
    verify_hmac_sha256,
)
from pythonforge.errors import CryptographyError


# --- AES-GCM -----------------------------------------------------------


def test_aes_gcm_round_trip() -> None:
    key = generate_key()
    assert decrypt(key, encrypt(key, b"secret message")) == b"secret message"


def test_aes_gcm_nonce_is_unique_per_call() -> None:
    """Nonce reuse would be catastrophic for GCM, so identical plaintexts
    must still produce different ciphertexts."""
    key = generate_key()
    assert encrypt(key, b"same") != encrypt(key, b"same")


def test_aes_gcm_with_associated_data() -> None:
    key = generate_key()
    payload = encrypt(key, b"msg", associated_data=b"context")
    assert decrypt(key, payload, associated_data=b"context") == b"msg"


def test_aes_gcm_rejects_wrong_associated_data() -> None:
    key = generate_key()
    payload = encrypt(key, b"msg", associated_data=b"context")
    with pytest.raises(CryptographyError):
        decrypt(key, payload, associated_data=b"different")


def test_aes_gcm_rejects_tampered_ciphertext() -> None:
    key = generate_key()
    payload = bytearray(encrypt(key, b"msg"))
    payload[-1] ^= 0xFF
    with pytest.raises(CryptographyError):
        decrypt(key, bytes(payload))


def test_aes_gcm_rejects_wrong_key() -> None:
    payload = encrypt(generate_key(), b"msg")
    with pytest.raises(CryptographyError):
        decrypt(generate_key(), payload)


def test_aes_gcm_rejects_truncated_payload() -> None:
    with pytest.raises(CryptographyError, match="too short"):
        decrypt(generate_key(), b"short")


def test_aes_gcm_requires_secret_material() -> None:
    with pytest.raises(CryptographyError, match="secret material"):
        encrypt(KeyData(kind="symmetric"), b"msg")


def test_invalid_aes_key_size_is_rejected() -> None:
    with pytest.raises(CryptographyError, match="key size"):
        generate_key(size=7)


# --- Hashing -----------------------------------------------------------


def test_sha256_is_stable() -> None:
    assert sha256(b"abc") == sha256(b"abc")
    assert len(sha256(b"abc")) == 32


def test_hmac_round_trip_and_rejection() -> None:
    mac = hmac_sha256(b"key", b"data")
    assert verify_hmac_sha256(b"key", b"data", mac)
    assert not verify_hmac_sha256(b"key", b"tampered", mac)
    assert not verify_hmac_sha256(b"wrong-key", b"data", mac)


def test_hmac_requires_a_key() -> None:
    with pytest.raises(CryptographyError):
        hmac_sha256(b"", b"data")


def test_blake3_digest() -> None:
    from pythonforge.encrypt.local import blake3

    assert len(blake3(b"data")) == 32
    assert blake3(b"data") == blake3(b"data")
    assert blake3(b"data") != blake3(b"other")


def test_keyed_blake3_requires_a_32_byte_key() -> None:
    from pythonforge.encrypt.local import blake3

    assert len(blake3(b"data", key=b"k" * 32)) == 32
    with pytest.raises(CryptographyError, match="32-byte"):
        blake3(b"data", key=b"too-short")


# --- RSA ---------------------------------------------------------------


def test_rsa_encrypt_decrypt_round_trip() -> None:
    key = generate_rsa_key()
    assert rsa_decrypt(key, rsa_encrypt(key, b"small secret")) == b"small secret"


def test_rsa_sign_verify_round_trip() -> None:
    key = generate_rsa_key()
    signature = rsa_sign(key, b"payload")
    assert rsa_verify(key, b"payload", signature)


def test_rsa_verify_rejects_tampered_data() -> None:
    key = generate_rsa_key()
    signature = rsa_sign(key, b"payload")
    assert not rsa_verify(key, b"tampered", signature)


def test_rsa_verify_rejects_signature_from_another_key() -> None:
    signature = rsa_sign(generate_rsa_key(), b"payload")
    assert not rsa_verify(generate_rsa_key(), b"payload", signature)


def test_rsa_public_only_key_cannot_sign() -> None:
    key = generate_rsa_key().public_only()
    with pytest.raises(CryptographyError, match="private material"):
        rsa_sign(key, b"payload")


def test_weak_rsa_key_size_is_rejected() -> None:
    with pytest.raises(CryptographyError, match="2048"):
        generate_rsa_key(key_size=1024)


# --- Ed25519 -----------------------------------------------------------


def test_ed25519_sign_verify_round_trip() -> None:
    key = generate_ed25519_key()
    assert ed25519_verify(key, b"payload", ed25519_sign(key, b"payload"))


def test_ed25519_rejects_tampered_data() -> None:
    key = generate_ed25519_key()
    assert not ed25519_verify(key, b"tampered", ed25519_sign(key, b"payload"))


# --- ECDH --------------------------------------------------------------


def test_ecdh_both_sides_derive_the_same_secret() -> None:
    alice, bob = generate_ec_key(), generate_ec_key()
    assert ecdh_shared_key(alice, bob.public_only()) == ecdh_shared_key(bob, alice.public_only())


def test_ecdh_different_peers_derive_different_secrets() -> None:
    alice, bob, eve = generate_ec_key(), generate_ec_key(), generate_ec_key()
    assert ecdh_shared_key(alice, bob.public_only()) != ecdh_shared_key(alice, eve.public_only())


def test_ecdh_info_changes_the_derived_key() -> None:
    alice, bob = generate_ec_key(), generate_ec_key()
    peer = bob.public_only()
    assert ecdh_shared_key(alice, peer, info=b"ctx-a") != ecdh_shared_key(alice, peer, info=b"ctx-b")


# --- KeyData -----------------------------------------------------------


def test_key_data_never_exposes_secret_material() -> None:
    key = generate_key()
    assert key.secret is not None
    assert str(key.secret) not in repr(key)
    assert "secret=" not in repr(key)
    assert repr(key) == str(key)


def test_public_only_drops_the_secret() -> None:
    key = generate_rsa_key()
    stripped = key.public_only()
    assert key.has_secret
    assert not stripped.has_secret
    assert stripped.public == key.public
