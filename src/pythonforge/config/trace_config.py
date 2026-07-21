from pydantic import BaseModel, Field

class TraceConfig(BaseModel):
    enabled: bool = Field(default=True)
    sample_rate: float = Field(default=1.0)
