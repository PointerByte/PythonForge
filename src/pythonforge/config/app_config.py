from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = Field(default="PythonForge")
    env: Literal["development", "staging", "production", "test"] = Field(default="development")
    debug: bool = Field(default=True)
    version: str = Field(default="0.1.0")
