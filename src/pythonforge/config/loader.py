import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel
from .app_config import AppConfig
from .server_config import ServerHTTPConfig, ServerGRPCConfig
from .logger_config import LoggerConfig
from .trace_config import TraceConfig
from .security_config import JWTConfig
from .encrypt_config import EncryptConfig

class FullConfig(BaseModel):
    app: AppConfig
    server_http: ServerHTTPConfig
    server_grpc: ServerGRPCConfig
    logger: LoggerConfig
    trace: TraceConfig
    jwt: JWTConfig
    encrypt: EncryptConfig

def load_config(config_path: Optional[str] = None) -> FullConfig:
    """
    Loads configuration with the following precedence:
    Defaults < YAML File < Environment Variables < Overrides
    """
    # 1. Default Values
    config_data: Dict[str, Any] = {
        "app": AppConfig().model_dump(),
        "server_http": ServerHTTPConfig().model_dump(),
        "server_grpc": ServerGRPCConfig().model_dump(),
        "logger": LoggerConfig().model_dump(),
        "trace": TraceConfig().model_dump(),
        "jwt": JWTConfig(secret_key="default_secret_key").model_dump(),
        "encrypt": EncryptConfig().model_dump(),
    }

    # 2. Load from YAML if provided
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            yaml_data = yaml.safe_load(f)
            if yaml_data:
                # Deep merge or simple update depending on structure
                for key in config_data.keys():
                    if key in yaml_data:
                        config_data[key].update(yaml_data[key])

    # 3. Load from Environment Variables
    # Convention: PYTHONFORGE_APP__NAME, PYTHONFORGE_SERVER_HTTP__PORT, etc.
    prefix = "PYTHONFORGE_"
    for env_key, env_val in os.environ.items():
        if env_key.startswith(prefix):
            parts = env_key[len(prefix):].lower().split("__")
            if len(parts) >= 2:
                section, field = parts[0], parts[1]
                if section in config_data and field in config_data[section]:
                    # Try to cast to correct type based on existing config
                    current_val = config_data[section][field]
                    try:
                        if isinstance(current_val, bool):
                            config_data[section][field] = env_val.lower() in ("true", "1", "yes")
                        elif isinstance(current_val, int):
                            config_data[section][field] = int(env_val)
                        elif isinstance(current_val, float):
                            config_data[section][field] = float(env_val)
                        else:
                            config_data[section][field] = env_val
                    except (ValueError, TypeError):
                        pass

    return FullConfig(**config_data)
