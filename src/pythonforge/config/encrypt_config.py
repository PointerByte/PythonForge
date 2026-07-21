from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EncryptConfig(BaseModel):
    enabled: bool = Field(default=False)
    provider: Literal["local", "aws", "azure", "gcp"] = Field(default="local")
