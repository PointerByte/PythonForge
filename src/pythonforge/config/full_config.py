from __future__ import annotations

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from .app_config import AppConfig
from .client_config import ClientConfig
from .encrypt_config import EncryptConfig
from .logger_config import LoggerConfig
from .security_config import JWTConfig
from .server_config import ServerConfig
from .trace_config import TraceConfig


class FullConfig(BaseSettings):
    """Composed, typed settings for the whole application.

    Precedence (lowest to highest): field defaults < ``application.yaml``
    (or the file named by ``model_config["yaml_file"]``) < ``env.files`` <
    environment variables (``PYTHONFORGE_<SECTION>__<FIELD>``) < constructor
    overrides. Build instances through :func:`pythonforge.config.load_config`
    rather than the constructor directly.
    """

    model_config = SettingsConfigDict(
        env_prefix="PYTHONFORGE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    trace: TraceConfig = Field(default_factory=TraceConfig)
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    encrypt: EncryptConfig = Field(default_factory=EncryptConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Order = precedence, highest first: constructor overrides, then env
        # vars, then env.files (dotenv), then the discovered application file.
        # Field defaults are appended automatically by the base class.
        sources: tuple[PydanticBaseSettingsSource, ...] = (
            init_settings,
            env_settings,
            dotenv_settings,
        )
        if json_file := settings_cls.model_config.get("json_file"):
            sources += (JsonConfigSettingsSource(settings_cls, json_file=json_file),)
        elif yaml_file := settings_cls.model_config.get("yaml_file"):
            sources += (YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file),)
        return sources
