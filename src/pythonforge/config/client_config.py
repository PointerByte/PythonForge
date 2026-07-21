from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ClientConfig(BaseModel):
    timeout: float = Field(default=30.0, gt=0)
    connect_timeout: float = Field(default=5.0, gt=0)
    retries: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)

    verify: bool = Field(default=True)
    cert_file: str | None = Field(default=None)
    key_file: str | None = Field(default=None)
    ca_file: str | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_mtls(self) -> ClientConfig:
        if self.key_file and not self.cert_file:
            raise ValueError("client: key_file requires cert_file")
        return self
