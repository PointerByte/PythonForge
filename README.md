# PythonForge

A modular Python library for building modern services with FastAPI and gRPC,
implementing conventions shared with the sibling **DenoForge** and **GoForge**
projects: shared configuration, request context, security, structured
logging, and OpenTelemetry across transports. It is not a new web framework —
it does not hide or wrap the normal FastAPI/Starlette/HTTPX APIs.

*Lee esto en español: [README.es.md](README.es.md)*

## What's included

- **Configuration** (`pythonforge.config`) — typed settings via
  `pydantic-settings`, with YAML/JSON discovery, `.env` files, and
  environment variables.
- **Request context** (`pythonforge.context`) — a transport-agnostic
  `RequestContext` backed by `contextvars`, with W3C Trace Context support.
- **HTTP transport** (`pythonforge.transport.http`) — a FastAPI app factory,
  middleware stack, health/readiness endpoints, and an async HTTPX client.
- **gRPC transport** (`pythonforge.transport.grpc`) — `grpc.aio` server and
  channels, interceptors for context/logging/errors/auth, all four RPC
  patterns, TLS/mTLS and the standard health service.
- **Hybrid runtime** (`pythonforge.transport.ServiceRuntime`) — FastAPI and
  gRPC in one process, with atomic startup and drained shutdown.
- **Security** (`pythonforge.security`) — JWT (HS256/RS256/PS256/EdDSA),
  bearer/cookie auth for FastAPI and bearer metadata for gRPC.
- **Cryptography** (`pythonforge.encrypt`) — AES-GCM, HMAC/SHA-256/BLAKE3,
  RSA-OAEP, ECDH, Ed25519, plus injectable AWS/Azure/GCP KMS adapters.
- **Background work** (`pythonforge.tools`) — interval/cron jobs and a
  bounded worker pool with real backpressure.
- **CLI** (`qpython`) — scaffolds FastAPI, gRPC or hybrid services and
  generates development certificates.
- **Logging** (`pythonforge.logger`) — structured JSON/text logs with
  automatic secret redaction.
- **Telemetry** (`pythonforge.telemetry`) — optional OpenTelemetry
  integration for FastAPI, HTTPX and gRPC.

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
| `grpc` | `grpcio`, `grpcio-health-checking`, `protobuf` |
| `security` | `PyJWT[crypto]`, `cryptography`, `blake3` |
| `telemetry` | OpenTelemetry SDK + FastAPI/HTTPX/gRPC instrumentation |
| `aws` / `azure` / `gcp` | One KMS provider SDK each |
| `cli` | `typer` (the `qpython` scaffolding CLI) |
| `all` | Every runtime capability above, excluding `dev` |
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

Or scaffold a whole service:

```bash
pip install "pythonforge[cli,grpc]"
qpython new hybrid my-service   # FastAPI + gRPC in one process
```

## Documentation

- [docs/configuration.md](docs/configuration.md) — settings model, source
  precedence, file discovery, environment variables, secrets.
- [docs/http.md](docs/http.md) — `create_app`, middleware, health/readiness,
  error handling, `ForgeClient`.
- [docs/grpc.md](docs/grpc.md) — gRPC server/client, interceptors, stub
  generation, and the hybrid `ServiceRuntime`.
- [docs/security.md](docs/security.md) — JWT, authentication on both
  transports, local cryptography, and KMS providers.
- [docs/background-work.md](docs/background-work.md) — jobs, workers, and
  the `qpython` CLI.
- [docs/observability.md](docs/observability.md) — log schema, redaction,
  and OpenTelemetry integration.

Spanish translations are available alongside each file (`*.es.md`).

## Development

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy .typing/pythonforge tests
python -m pytest --cov=pythonforge --cov-report=term-missing --cov-fail-under=85
python -m bandit -q -r src
python -m pip_audit
```
