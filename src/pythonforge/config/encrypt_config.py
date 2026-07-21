from pydantic import BaseModel, Field

class EncryptConfig(BaseModel):
    enabled: bool = Field(default=False)
    provider: str = Field(default="local")
