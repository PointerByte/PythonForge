from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class LoggerConfig(BaseModel):
    level: str = Field(default="INFO")
    format: Literal["json", "text"] = Field(default="json")
    file_path: str | None = None
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=0)
    backup_count: int = Field(default=3, ge=0)

    sensitive_keys: list[str] = Field(default_factory=list)
    include_body: bool = Field(default=False)
    max_body_size: int = Field(default=4096, ge=0)

    @field_validator("level")
    @classmethod
    def _validate_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _LEVELS:
            raise ValueError(f"logger.level must be one of {_LEVELS}")
        return upper
