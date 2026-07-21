from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..errors import ConfigurationError
from .full_config import FullConfig
from .sources import discover_application_file


def load_config(
    *,
    config_path: str | Path | None = None,
    config_dir: str | Path | None = None,
    env_files: str | Path | list[str | Path] | None = None,
    **overrides: Any,
) -> FullConfig:
    """Build a :class:`FullConfig` with the documented source precedence.

    ``config_path`` takes an explicit ``application.yaml|yml|json`` path; if
    omitted, ``config_dir`` (default: cwd) is searched for one. ``env_files``
    maps to pydantic-settings' ``env.files`` layer. Anything in ``overrides``
    wins over every other source, matching the constructor-override
    precedence required by the configuration spec.
    """
    file_path = (
        Path(config_path) if config_path is not None else discover_application_file(config_dir)
    )

    config_cls: type[FullConfig] = FullConfig
    if file_path is not None:
        # A fresh subclass per call keeps the discovered file scoped to this
        # load, so concurrent/sequential loads with different files or
        # settings never contaminate each other. Only the config key that's
        # actually consumed (yaml_file vs. json_file) is set, to avoid
        # pydantic-settings' "unused config key" warning for the other one.
        key = "json_file" if file_path.suffix == ".json" else "yaml_file"
        scoped_config: dict[str, Any] = {**FullConfig.model_config, key: str(file_path)}
        config_cls = type(FullConfig.__name__, (FullConfig,), {"model_config": scoped_config})

    try:
        return config_cls(_env_file=env_files, **overrides)
    except ValidationError as exc:
        # Only surface field locations and messages -- never the offending
        # input value, which could be a secret that failed validation.
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigurationError(f"invalid configuration: {details}") from exc
