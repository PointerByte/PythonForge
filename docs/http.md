# HTTP transport

*Lee esto en español: [http.es.md](http.es.md)*

`pythonforge.transport.http` wraps FastAPI/Starlette and HTTPX without
hiding their APIs: `create_app` returns a plain `FastAPI` instance, and
`ForgeClient` returns plain `httpx.Response` objects.

## `create_app`

```python
from fastapi import APIRouter
from pythonforge.config import load_config
from pythonforge.transport.http import create_app

router = APIRouter()

@router.get("/api/v1/hello")
async def hello() -> dict[str, str]:
    return {"message": "hi"}

config = load_config()
app = create_app(
    config,
    routers=[router],
    readiness_checks=[lambda: True],   # sync or async, evaluated by /health/ready
    on_startup=[lambda app: print("starting")],
    on_shutdown=[lambda app: print("stopping")],
)
```

No global state is required: `config` drives everything, so building
multiple apps from different configs in the same process (e.g. in tests)
never cross-contaminates. `create_app` does not bind a socket — pass `app`
to any ASGI server (uvicorn, hypercorn, ...).

### What `create_app` wires up

- **Logging and telemetry** — `configure_logging(config.logger)` and
  `configure_telemetry(config.trace)` run before the app is built; see
  [observability.md](observability.md).
- **`RequestContextMiddleware`** — populates `RequestContext` from
  `X-Request-Id`, `traceparent`/`tracestate`, and `X-Deadline` headers (see
  the context section below), logs one structured line per request, and
  sets `X-Request-Id` on the response.
- **`SecurityHeadersMiddleware`** — always sets `X-Content-Type-Options`,
  `X-Frame-Options`, and `Referrer-Policy`.
- **CORS** — added only if `server.http.cors_origins` is non-empty.
- **Rate limiting** — added only if `server.http.rate_limit_enabled` is
  true: an in-memory, single-process, fixed-window limiter keyed by client
  IP. `health_path`/`ready_path` are always exempt. Not a substitute for a
  distributed rate limiter behind multiple workers/replicas.
- **Exception handlers** — every response, success or failure, is JSON:
  ```json
  {"error": {"code": 500, "message": "internal server error", "request_id": "..."}}
  ```
  `StarletteHTTPException` and `RequestValidationError` map to their status
  code; `pythonforge.errors.AuthenticationError` → 401,
  `AuthorizationError` → 403, any other `PythonForgeError` → 400, and any
  other exception → 500 with a generic message (the real exception is
  logged, never echoed to the client).
- **Health/readiness** — `GET {health_path}` (default `/health`) always
  returns `{"status": "ok"}` and never reveals configuration. `GET
  {ready_path}` (default `/health/ready`) returns 503 until the lifespan's
  startup hooks finish, then runs every `readiness_checks` callable (sync or
  async) and returns 503 if any of them is falsy.

### TLS/mTLS for the server

`create_app` doesn't bind sockets, so `server.http.tls_enabled`,
`cert_file`, `key_file`, `ca_file`, and `mtls_required` are meant to be
handed to your ASGI runner:

```python
import uvicorn

http_config = app.state.config.server.http
uvicorn.run(
    app,
    host=http_config.host,
    port=http_config.port,
    ssl_certfile=http_config.cert_file if http_config.tls_enabled else None,
    ssl_keyfile=http_config.key_file if http_config.tls_enabled else None,
    ssl_ca_certs=http_config.ca_file if http_config.tls_enabled else None,
)
```

See `examples/fastapi_service/main.py` for the full runnable version.

## Request context

`pythonforge.context.RequestContext` is a `contextvars`-backed proxy —
cheap to construct anywhere, always reflecting the current task's values:

```python
from pythonforge.context import RequestContext

@router.get("/whoami")
async def whoami() -> dict[str, str | None]:
    ctx = RequestContext()
    return {"request_id": ctx.request_id, "trace_id": ctx.trace_context and ctx.trace_context.trace_id}
```

Reusable/domain logic should depend on `RequestContext`, never on FastAPI's
`Request`, so it stays testable and framework-agnostic.

## `ForgeClient`

An async HTTPX wrapper that propagates context downstream and returns the
raw `httpx.Response`:

```python
from pythonforge.config import ClientConfig
from pythonforge.transport.http import ForgeClient

async with ForgeClient("https://api.internal", ClientConfig(retries=3)) as client:
    response = await client.get("/widgets")
    response.raise_for_status()
    data = response.json()
```

- **Context propagation** — `X-Request-Id`, `traceparent`/`tracestate`, and
  `X-Deadline` are forwarded automatically when a `RequestContext` is bound
  (e.g. inside a request handler).
- **Deadlines** — if `RequestContext().deadline` is set and closer than the
  configured timeout, the effective timeout is clamped to it; a call made
  after the deadline has already passed raises `TransportError` without
  making the request.
- **Retries** — idempotent methods (`GET`, `HEAD`, `PUT`, `DELETE`,
  `OPTIONS`) retry on 5xx responses and transport errors with exponential
  backoff (`ClientConfig.retries` / `retry_backoff_seconds`); non-idempotent
  methods and 4xx responses are never retried.
- **Downstream logging** — every attempt appends a
  `pythonforge.context.DownstreamCall` to
  `RequestContext().downstream_processes`, so a request handler's log line
  can report every outbound call it made.
- **TLS/mTLS** — `ClientConfig.verify`, `cert_file`/`key_file`, and
  `ca_file` map onto `httpx.AsyncClient`'s TLS options.

Testability: pass `transport=httpx.MockTransport(...)` or
`transport=httpx.ASGITransport(app=...)` to `ForgeClient(...)` to avoid real
sockets in tests.
