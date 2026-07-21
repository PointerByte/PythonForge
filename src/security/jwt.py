"""JWT encoding/decoding for HS256, RS256, PS256 and EdDSA.

Verification is fail-closed by design: signature, expiry, issuer and
audience are all checked, and every failure surfaces as
:class:`AuthenticationError` with a deliberately vague message -- telling a
caller *why* their token was rejected is an oracle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from ..config import JWTConfig
from ..errors import AuthenticationError, ConfigurationError
from ._optional import require_jwt


class Claims(BaseModel):
    """Registered JWT claims, plus whatever else the token carried.

    Unknown claims are preserved in ``extra`` instead of being dropped, so
    application-specific claims (roles, tenant, ...) survive a round trip.
    """

    sub: str | None = None
    iss: str | None = None
    aud: str | list[str] | None = None
    exp: datetime | None = None
    nbf: datetime | None = None
    iat: datetime | None = None
    jti: str | None = None
    scope: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def scopes(self) -> list[str]:
        """The space-delimited ``scope`` claim, split into a list."""
        return self.scope.split() if self.scope else []

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Claims:
        known = set(cls.model_fields) - {"extra"}
        return cls(
            **{key: value for key, value in payload.items() if key in known},
            extra={key: value for key, value in payload.items() if key not in known},
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for name in set(type(self).model_fields) - {"extra"}:
            value = getattr(self, name)
            if value is None:
                continue
            payload[name] = int(value.timestamp()) if isinstance(value, datetime) else value
        payload.update(self.extra)
        return payload


def encode_token(
    config: JWTConfig,
    claims: Claims | dict[str, Any],
    *,
    expires_in: timedelta | None = None,
) -> str:
    """Sign a token with the configured algorithm and key material."""
    jwt = require_jwt()
    key = config.resolve_private_key()
    if not key:
        raise ConfigurationError(f"jwt: no signing key configured for {config.algorithm}")

    payload = claims.to_payload() if isinstance(claims, Claims) else dict(claims)

    now = datetime.now(tz=UTC)
    payload.setdefault("iat", int(now.timestamp()))
    if "exp" not in payload:
        lifetime = expires_in or timedelta(minutes=config.access_token_expire_minutes)
        payload["exp"] = int((now + lifetime).timestamp())
    if config.issuer:
        payload.setdefault("iss", config.issuer)
    if config.audience:
        payload.setdefault("aud", config.audience)

    token: str = jwt.encode(payload, key, algorithm=config.algorithm)
    return token


def decode_token(config: JWTConfig, token: str) -> Claims:
    """Verify a token and return its claims, or raise :class:`AuthenticationError`.

    Only the single configured algorithm is accepted, which closes the
    classic ``alg`` confusion attack (e.g. an RS256 verifier tricked into
    treating the public key as an HS256 secret).
    """
    jwt = require_jwt()
    key = config.resolve_public_key()
    if not key:
        raise ConfigurationError(f"jwt: no verification key configured for {config.algorithm}")

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[config.algorithm],
            issuer=config.issuer,
            audience=config.audience,
            leeway=config.leeway_seconds,
            options={
                "require": ["exp"],
                "verify_aud": config.audience is not None,
                "verify_iss": config.issuer is not None,
            },
        )
    except Exception as exc:
        # One message for every failure mode: expired, bad signature, wrong
        # issuer, malformed. The cause is chained for logs, not for callers.
        raise AuthenticationError("invalid or expired token") from exc

    return Claims.from_payload(payload)
