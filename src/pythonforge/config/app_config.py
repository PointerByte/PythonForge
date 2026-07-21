from pydantic import BaseModel, Field
from typing import Optional

class AppConfig(BaseModel):
    name: str = Field(default="PythonForge")
    env: str = Field(default="development")
    debug: bool = Field(default=True)
    version: str = Field(default="0.1.0")
