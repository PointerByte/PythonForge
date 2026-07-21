from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator


SYMMETRIC_ALGORITHMS = ("HS256",)
ASYMMETRIC_ALGORITHMS = ("RS256", "PS256", "EdDSA")


class JWTConfig(BaseModel):
    """JWT signing/verification settings.

    HS256 uses ``secret_key``; the asymmetric algorithms use
    ``private_key``/``public_key`` (PEM, either inline or via ``*_file``).
    Validation is fail-closed: an algorithm without usable key material is
    rejected at load time rather than at the first request.
    """

    # No insecure default -- a missing secret must fail loudly, not silently
    # sign tokens anyone can forge.
    secret_key: SecretStr | None = Field(default=None)
    algorithm: Literal["HS256", "RS256", "PS256", "EdDSA"] = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=1)

    private_key: SecretStr | None = Field(default=None)
    private_key_file: str | None = Field(default=None)
    public_key: str | None = Field(default=None)
    public_key_file: str | None = Field(default=None)

    issuer: str | None = Field(default=None)
    audience: str | None = Field(default=None)
    leeway_seconds: int = Field(default=0, ge=0)

    # Auth is only enforced where a route/RPC asks for it; this flag decides
    # whether the JWT machinery is usable at all.
    enabled: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_key_material(self) -> JWTConfig:
        if not self.enabled:
            return self
        if self.algorithm in SYMMETRIC_ALGORITHMS:
            if not self.secret_key:
                raise ValueError(f"jwt: {self.algorithm} requires secret_key")
        elif not (self.public_key or self.public_key_file):
            raise ValueError(f"jwt: {self.algorithm} requires public_key or public_key_file")
        return self

    def resolve_private_key(self) -> str | None:
        """Return the PEM private key (or HS256 secret), reading the file if needed."""
        if self.algorithm in SYMMETRIC_ALGORITHMS:
            return self.secret_key.get_secret_value() if self.secret_key else None
        if self.private_key:
            return self.private_key.get_secret_value()
        if self.private_key_file:
            return Path(self.private_key_file).read_text()
        return None

    def resolve_public_key(self) -> str | None:
        """Return the PEM public key (or HS256 secret), reading the file if needed."""
        if self.algorithm in SYMMETRIC_ALGORITHMS:
            return self.secret_key.get_secret_value() if self.secret_key else None
        if self.public_key:
            return self.public_key
        if self.public_key_file:
            return Path(self.public_key_file).read_text()
        return None
