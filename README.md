# PythonForge

A modular Python library for building modern services with FastAPI and gRPC,
implementing conventions shared with the sibling **DenoForge** and **GoForge**
projects: shared configuration, request context, security, structured
logging, and OpenTelemetry across transports. It is not a new web framework —
it does not hide or wrap the normal FastAPI/Starlette/HTTPX APIs.

*Lee esto en español: [README.es.md](README.es.md)*

## Project status

PythonForge is under active development. Implemented so far:

- **Configuration** (`pythonforge.config`) — typed settings via
  `pydantic-settings`, with YAML/JSON discovery, `.env` files, and
  environment variables.
- **Request context** (`pythonforge.context`) — a transport-agnostic
  `RequestContext` backed by `contextvars`, with W3C Trace Context support.
- **HTTP transport** (`pythonforge.transport.http`) — a FastAPI app factory,
  middleware stack, health/readiness endpoints, and an async HTTPX client.
- **Logging** (`pythonforge.logger`) — structured JSON/text logs with
  automatic secret redaction.
- **Telemetry** (`pythonforge.telemetry`) — optional OpenTelemetry
  integration for FastAPI and HTTPX.

Not implemented yet: gRPC transport, JWT/cryptography, KMS providers,
background jobs/workers, and the `qpython` scaffolding CLI. See
`openspec/changes/create-pythonforge/tasks.md` for the full backlog.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The base install only pulls in `fastapi`, `pydantic-settings`, `httpx`,
`PyYAML`, and `python-dotenv`. Everything else is an extra:

| Extra | Adds |
| --- | --- |
| `telemetry` | OpenTelemetry SDK + FastAPI/HTTPX/gRPC instrumentation |
| `grpc` | `grpcio`, `protobuf` (transport not implemented yet) |
| `aws` / `azure` / `gcp` | One KMS provider SDK each (not implemented yet) |
| `cli` | `typer` (scaffolding CLI not implemented yet) |
| `dev` | pytest, coverage, mypy, ruff, bandit, pip-audit, build, twine, uvicorn |

## Quick start

```python
from fastapi import APIRouter
from pythonforge.config import load_config
from pythonforge.transport.http import create_app

router = APIRouter()


@router.get("/api/v1/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from PythonForge"}


config = load_config()  # discovers application.yaml in the cwd, if present
app = create_app(config, routers=[router])
```

Run it with any ASGI server, e.g. `uvicorn myapp:app`. See
`examples/fastapi_service/` for a complete runnable example, including how
`ServerHTTPConfig`'s TLS fields map onto uvicorn's `ssl_*` options.

## Documentation

- [docs/configuration.md](docs/configuration.md) — settings model, source
  precedence, file discovery, environment variables, secrets.
- [docs/http.md](docs/http.md) — `create_app`, middleware, health/readiness,
  error handling, `ForgeClient`.
- [docs/observability.md](docs/observability.md) — log schema, redaction,
  and OpenTelemetry integration.

Spanish translations are available alongside each file (`*.es.md`).

## Development

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src tests
python -m pytest --cov=pythonforge --cov-report=term-missing --cov-fail-under=85
python -m bandit -q -r src
python -m pip_audit
```
