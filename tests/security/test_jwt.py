from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pythonforge.config import JWTConfig
from pythonforge.encrypt.local import generate_ed25519_key, generate_rsa_key
from pythonforge.errors import AuthenticationError, ConfigurationError
from pythonforge.security.jwt import Claims, decode_token, encode_token

# 32+ bytes: shorter HMAC secrets are legal but PyJWT warns, per RFC 7518 3.2.
SECRET = "a-test-signing-secret-value-32b!"


def hs256_config(**overrides) -> JWTConfig:
    return JWTConfig(enabled=True, algorithm="HS256", secret_key=SECRET, **overrides)


def asymmetric_config(algorithm: str) -> JWTConfig:
    key = generate_ed25519_key() if algorithm == "EdDSA" else generate_rsa_key()
    assert key.secret and key.public
    return JWTConfig(
        enabled=True,
        algorithm=algorithm,
        private_key=key.secret.decode(),
        public_key=key.public.decode(),
    )


@pytest.mark.parametrize("algorithm", ["HS256", "RS256", "PS256", "EdDSA"])
def test_round_trip_for_every_supported_algorithm(algorithm: str) -> None:
    config = hs256_config() if algorithm == "HS256" else asymmetric_config(algorithm)
    token = encode_token(config, Claims(sub="user-1"))
    assert decode_token(config, token).sub == "user-1"


def test_extra_claims_survive_the_round_trip() -> None:
    config = hs256_config()
    token = encode_token(config, Claims(sub="u", extra={"tenant": "acme", "roles": ["admin"]}))
    claims = decode_token(config, token)
    assert claims.extra["tenant"] == "acme"
    assert claims.extra["roles"] == ["admin"]


def test_scopes_are_split_from_the_scope_claim() -> None:
    claims = Claims(sub="u", scope="read:widgets write:widgets")
    assert claims.scopes == ["read:widgets", "write:widgets"]
    assert claims.has_scope("read:widgets")
    assert not claims.has_scope("delete:widgets")


def test_expiry_is_added_automatically() -> None:
    config = hs256_config(access_token_expire_minutes=5)
    claims = decode_token(config, encode_token(config, Claims(sub="u")))
    assert claims.exp is not None
    assert claims.exp > datetime.now(tz=UTC)


def test_expired_token_is_rejected() -> None:
    config = hs256_config()
    expired = Claims(sub="u", exp=datetime.now(tz=UTC) - timedelta(minutes=1))
    token = encode_token(config, expired)
    with pytest.raises(AuthenticationError):
        decode_token(config, token)


def test_tampered_signature_is_rejected() -> None:
    config = hs256_config()
    token = encode_token(config, Claims(sub="u"))
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"
    with pytest.raises(AuthenticationError):
        decode_token(config, tampered)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = encode_token(hs256_config(), Claims(sub="u"))
    other = JWTConfig(
        enabled=True, algorithm="HS256", secret_key="a-completely-different-secret!!!"
    )
    with pytest.raises(AuthenticationError):
        decode_token(other, token)


def test_algorithm_confusion_is_rejected() -> None:
    """An HS256-signed token must never validate against an RS256 verifier.

    decode_token pins ``algorithms=[configured]``, so the verifier refuses to
    switch algorithms no matter what the token's header claims.
    """
    rs256 = asymmetric_config("RS256")
    forged = encode_token(hs256_config(), Claims(sub="attacker"))
    with pytest.raises(AuthenticationError):
        decode_token(rs256, forged)


def test_wrong_issuer_is_rejected() -> None:
    signer = hs256_config(issuer="issuer-a")
    verifier = hs256_config(issuer="issuer-b")
    with pytest.raises(AuthenticationError):
        decode_token(verifier, encode_token(signer, Claims(sub="u")))


def test_wrong_audience_is_rejected() -> None:
    signer = hs256_config(audience="api-a")
    verifier = hs256_config(audience="api-b")
    with pytest.raises(AuthenticationError):
        decode_token(verifier, encode_token(signer, Claims(sub="u")))


def test_matching_issuer_and_audience_are_accepted() -> None:
    config = hs256_config(issuer="pythonforge", audience="api")
    claims = decode_token(config, encode_token(config, Claims(sub="u")))
    assert claims.iss == "pythonforge"
    assert claims.aud == "api"


def test_error_message_does_not_reveal_the_failure_reason() -> None:
    config = hs256_config()
    with pytest.raises(AuthenticationError) as exc_info:
        decode_token(config, "not-even-a-token")
    assert str(exc_info.value) == "invalid or expired token"


def test_missing_key_material_raises_configuration_error() -> None:
    config = JWTConfig(enabled=False, algorithm="HS256")
    with pytest.raises(ConfigurationError):
        encode_token(config, Claims(sub="u"))


def test_enabled_config_without_secret_is_rejected_at_load() -> None:
    with pytest.raises(ValueError, match="requires secret_key"):
        JWTConfig(enabled=True, algorithm="HS256")


def test_enabled_asymmetric_config_without_public_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires public_key"):
        JWTConfig(enabled=True, algorithm="RS256")


def test_secret_never_appears_in_repr() -> None:
    config = hs256_config()
    assert SECRET not in repr(config)
