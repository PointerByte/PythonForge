from pydantic import BaseModel, Field

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
