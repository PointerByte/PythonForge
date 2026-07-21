from __future__ import annotations

from pathlib import Path

APPLICATION_FILENAMES = ("application.yaml", "application.yml", "application.json")


def discover_application_file(config_dir: str | Path | None = None) -> Path | None:
    """Look for ``application.{yaml,yml,json}`` in ``config_dir`` (default: cwd)."""
    base = Path(config_dir) if config_dir is not None else Path.cwd()
    for name in APPLICATION_FILENAMES:
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None
