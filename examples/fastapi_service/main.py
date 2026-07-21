"""Minimal runnable FastAPI service built on PythonForge.

Loads ``application.yaml`` from this directory, wires a router through
``create_app``, and runs it with uvicorn -- showing how ``ServerHTTPConfig``'s
TLS fields map onto uvicorn's own ``ssl_*`` options (PythonForge does not
bind sockets itself; that stays uvicorn's job).

Run with:  python examples/fastapi_service/main.py
Then:      curl http://127.0.0.1:8000/health
           curl http://127.0.0.1:8000/api/v1/hello
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI

from pythonforge.config import FullConfig, load_config
from pythonforge.context import RequestContext
from pythonforge.transport.http import create_app

router = APIRouter()


@router.get("/api/v1/hello")
async def hello() -> dict[str, str | None]:
    return {"message": "Hello from PythonForge", "request_id": RequestContext().request_id}


def build_app(config: FullConfig | None = None) -> FastAPI:
    config = config or load_config(config_dir=Path(__file__).parent)
    return create_app(config, routers=[router])


app = build_app()

if __name__ == "__main__":
    http_config = app.state.config.server.http
    uvicorn.run(
        app,
        host=http_config.host,
        port=http_config.port,
        ssl_certfile=http_config.cert_file if http_config.tls_enabled else None,
        ssl_keyfile=http_config.key_file if http_config.tls_enabled else None,
        ssl_ca_certs=http_config.ca_file if http_config.tls_enabled else None,
    )
