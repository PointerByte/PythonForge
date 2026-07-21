from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TraceConfig(BaseModel):
    enabled: bool = Field(default=True)
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    service_name: str = Field(default="pythonforge-service")
    exporter: Literal["console", "otlp"] = Field(default="console")
    otlp_endpoint: str | None = Field(default=None)
