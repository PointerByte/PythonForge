from pydantic import BaseModel, Field
from typing import Optional

class LoggerConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="json")
    file_path: Optional[str] = None
