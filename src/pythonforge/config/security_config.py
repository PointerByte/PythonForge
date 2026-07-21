from pydantic import BaseModel, Field

class JWTConfig(BaseModel):
    secret_key: str = Field(..., description="Secret key for HS256")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)
