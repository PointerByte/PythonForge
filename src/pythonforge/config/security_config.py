from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class JWTConfig(BaseModel):
    # No insecure default: unset until the security/cryptography module (later
    # phase) requires it, at which point it must be provided explicitly.
    secret_key: SecretStr | None = Field(default=None)
    algorithm: Literal["HS256", "RS256", "PS256", "EdDSA"] = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=1)
