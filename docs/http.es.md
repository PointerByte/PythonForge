# Transporte HTTP

*Read this in English: [http.md](http.md)*

`pythonforge.transport.http` envuelve FastAPI/Starlette y HTTPX sin ocultar
sus APIs: `create_app` devuelve una instancia `FastAPI` normal, y
`ForgeClient` devuelve objetos `httpx.Response` normales.

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
    readiness_checks=[lambda: True],   # sync o async, evaluado por /health/ready
    on_startup=[lambda app: print("starting")],
    on_shutdown=[lambda app: print("stopping")],
)
```

No requiere estado global: `config` gobierna todo, así que construir varias
apps a partir de configuraciones distintas en el mismo proceso (por ejemplo,
en tests) nunca se contamina entre sí. `create_app` no abre ningún socket —
pasa `app` a cualquier servidor ASGI (uvicorn, hypercorn, ...).

### Qué conecta `create_app`

- **Logging y telemetría** — `configure_logging(config.logger)` y
  `configure_telemetry(config.trace)` se ejecutan antes de construir la app;
  ver [observability.es.md](observability.es.md).
- **`RequestContextMiddleware`** — puebla `RequestContext` desde los headers
  `X-Request-Id`, `traceparent`/`tracestate` y `X-Deadline` (ver la sección
  de contexto más abajo), registra una línea estructurada por petición, y
  fija `X-Request-Id` en la respuesta.
- **`SecurityHeadersMiddleware`** — siempre fija `X-Content-Type-Options`,
  `X-Frame-Options` y `Referrer-Policy`.
- **CORS** — se agrega sólo si `server.http.cors_origins` no está vacío.
- **Rate limiting** — se agrega sólo si `server.http.rate_limit_enabled` es
  verdadero: un limitador en memoria, de un solo proceso, de ventana fija,
  por IP de cliente. `health_path`/`ready_path` siempre están exentos. No es
  un sustituto de un rate limiter distribuido detrás de varios
  workers/réplicas.
- **Manejadores de excepciones** — toda respuesta, éxito o fallo, es JSON:
  ```json
  {"error": {"code": 500, "message": "internal server error", "request_id": "..."}}
  ```
  `StarletteHTTPException` y `RequestValidationError` mapean a su código de
  estado; `pythonforge.errors.AuthenticationError` → 401,
  `AuthorizationError` → 403, cualquier otro `PythonForgeError` → 400, y
  cualquier otra excepción → 500 con un mensaje genérico (la excepción real
  se registra en el log, nunca se devuelve al cliente).
- **Health/readiness** — `GET {health_path}` (por defecto `/health`)
  siempre devuelve `{"status": "ok"}` y nunca revela configuración. `GET
  {ready_path}` (por defecto `/health/ready`) devuelve 503 hasta que
  terminan los hooks de arranque del lifespan, luego ejecuta cada callable
  de `readiness_checks` (sync o async) y devuelve 503 si alguno es falsy.

### TLS/mTLS para el servidor

`create_app` no abre sockets, así que `server.http.tls_enabled`,
`cert_file`, `key_file`, `ca_file` y `mtls_required` están pensados para
pasarse a tu runner ASGI:

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

Ver `examples/fastapi_service/main.py` para la versión completa ejecutable.

## Contexto de petición

`pythonforge.context.RequestContext` es un proxy respaldado por
`contextvars` — barato de construir en cualquier lugar, siempre refleja los
valores de la tarea actual:

```python
from pythonforge.context import RequestContext

@router.get("/whoami")
async def whoami() -> dict[str, str | None]:
    ctx = RequestContext()
    return {"request_id": ctx.request_id, "trace_id": ctx.trace_context and ctx.trace_context.trace_id}
```

La lógica reutilizable/de dominio debe depender de `RequestContext`, nunca
del `Request` de FastAPI, para seguir siendo testeable e independiente del
framework.

## `ForgeClient`

Un wrapper async de HTTPX que propaga el contexto hacia adelante y devuelve
el `httpx.Response` crudo:

```python
from pythonforge.config import ClientConfig
from pythonforge.transport.http import ForgeClient

async with ForgeClient("https://api.internal", ClientConfig(retries=3)) as client:
    response = await client.get("/widgets")
    response.raise_for_status()
    data = response.json()
```

- **Propagación de contexto** — `X-Request-Id`, `traceparent`/`tracestate`
  y `X-Deadline` se reenvían automáticamente cuando hay un `RequestContext`
  vinculado (por ejemplo, dentro de un handler de petición).
- **Deadlines** — si `RequestContext().deadline` está fijado y es más
  cercano que el timeout configurado, el timeout efectivo se recorta a ese
  valor; una llamada hecha después de que el deadline ya pasó lanza
  `TransportError` sin llegar a hacer la petición.
- **Reintentos** — los métodos idempotentes (`GET`, `HEAD`, `PUT`,
  `DELETE`, `OPTIONS`) reintentan ante respuestas 5xx y errores de
  transporte con backoff exponencial (`ClientConfig.retries` /
  `retry_backoff_seconds`); los métodos no idempotentes y las respuestas
  4xx nunca se reintentan.
- **Registro de llamadas downstream** — cada intento agrega un
  `pythonforge.context.DownstreamCall` a
  `RequestContext().downstream_processes`, así la línea de log de un
  handler puede reportar cada llamada saliente que hizo.
- **TLS/mTLS** — `ClientConfig.verify`, `cert_file`/`key_file` y `ca_file`
  se mapean a las opciones TLS de `httpx.AsyncClient`.

Testabilidad: pasa `transport=httpx.MockTransport(...)` o
`transport=httpx.ASGITransport(app=...)` a `ForgeClient(...)` para evitar
sockets reales en los tests.
