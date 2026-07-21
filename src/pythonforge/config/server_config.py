from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ServerHTTPConfig(BaseModel):
    # Must be reachable outside its container by default.
    host: str = Field(default="0.0.0.0")  # noqa: S104  # nosec B104
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    keep_alive: bool = Field(default=True)

    health_path: str = Field(default="/health")
    ready_path: str = Field(default="/health/ready")

    cors_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = Field(default=False)

    rate_limit_enabled: bool = Field(default=False)
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window_seconds: float = Field(default=60.0, gt=0)

    tls_enabled: bool = Field(default=False)
    cert_file: str | None = Field(default=None)
    key_file: str | None = Field(default=None)
    ca_file: str | None = Field(default=None)
    mtls_required: bool = Field(default=False)
    min_tls_version: str = Field(default="TLSv1.2")

    @model_validator(mode="after")
    def _validate_tls(self) -> ServerHTTPConfig:
        if self.tls_enabled and (not self.cert_file or not self.key_file):
            raise ValueError("server.http: tls_enabled requires cert_file and key_file")
        if self.mtls_required and not self.ca_file:
            raise ValueError("server.http: mtls_required requires ca_file")
        return self


class ServerGRPCConfig(BaseModel):
    # Must be reachable outside its container by default.
    host: str = Field(default="0.0.0.0")  # noqa: S104  # nosec B104
    port: int = Field(default=50051, ge=1, le=65535)
    max_workers: int = Field(default=10, ge=1)
    max_message_length: int = Field(default=4 * 1024 * 1024, ge=1)

    tls_enabled: bool = Field(default=False)
    cert_file: str | None = Field(default=None)
    key_file: str | None = Field(default=None)
    ca_file: str | None = Field(default=None)
    mtls_required: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_tls(self) -> ServerGRPCConfig:
        if self.tls_enabled and (not self.cert_file or not self.key_file):
            raise ValueError("server.grpc: tls_enabled requires cert_file and key_file")
        if self.mtls_required and not self.ca_file:
            raise ValueError("server.grpc: mtls_required requires ca_file")
        return self


class ServerConfig(BaseModel):
    http: ServerHTTPConfig = Field(default_factory=ServerHTTPConfig)
    grpc: ServerGRPCConfig = Field(default_factory=ServerGRPCConfig)
