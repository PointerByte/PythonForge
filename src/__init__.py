"""PythonForge: shared config, context, transport, logging and telemetry for
FastAPI + gRPC services.

The root package intentionally re-exports nothing beyond ``__version__`` --
submodules (``pythonforge.config``, ``pythonforge.context``,
``pythonforge.transport.http``, ``pythonforge.logger``,
``pythonforge.telemetry``, ...) stay independently importable, so picking one
capability never pulls in dependencies the others need (e.g. importing
``pythonforge.encrypt`` alone must never import FastAPI or a cloud SDK).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pythonforge")
except PackageNotFoundError:  # pragma: no cover - only hit outside an install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
