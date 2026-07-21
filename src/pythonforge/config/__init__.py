from pydantic import BaseModel, Field
from typing import Optional

class AppConfig(BaseModel):
    name: str = Field(default="PythonForge")
    env: str = Field(default="development")
    debug: bool = Field(default=True)

class ServerHTTPConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=1)
    keep_alive: bool = Field(default=True)

class ServerGRPCConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=50051)
    max_workers: int = Field(default=10)
    max_message_length: int = Field(default=4 * 1024 * 1024)

class ClientConfig(BaseModel):
    timeout: float = Field(default=30.0)
    retries: int = Field(default=3)
    connect_timeout: float = Field(default=5.0)

class LoggerConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="json")
    file_path: Optional[str] = None

class TraceConfig(BaseModel):
    enabled: bool = Field(default=True)
    sample_rate: float = Field(default=1.0)

class JWTConfig(BaseModel):
    secret_key: str = Field(..., description="Secret key for HS256")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)

class EncryptConfig(BaseModel):
    enabled: bool = Field(default=False)
    provider: str = Field(default="local")
