# PythonForge

Una librería Python modular para construir servicios modernos con FastAPI y
gRPC, que implementa las convenciones compartidas con los proyectos hermanos
**DenoForge** y **GoForge**: configuración compartida, contexto de petición,
seguridad, logging estructurado y OpenTelemetry entre transportes. No es un
framework web nuevo — no oculta ni envuelve las APIs normales de
FastAPI/Starlette/HTTPX.

*Read this in English: [README.md](README.md)*

## Qué incluye

- **Configuración** (`pythonforge.config`) — settings tipados vía
  `pydantic-settings`, con descubrimiento de YAML/JSON, archivos `.env` y
  variables de entorno.
- **Contexto de petición** (`pythonforge.context`) — un `RequestContext`
  independiente del transporte, respaldado por `contextvars`, con soporte
  para W3C Trace Context.
- **Transporte HTTP** (`pythonforge.transport.http`) — un factory de
  aplicación FastAPI, stack de middleware, endpoints de health/readiness y un
  cliente HTTPX asíncrono.
- **Transporte gRPC** (`pythonforge.transport.grpc`) — servidor y canales
  `grpc.aio`, interceptores de contexto/logging/errores/auth, los cuatro
  patrones de RPC, TLS/mTLS y el servicio de health estándar.
- **Runtime híbrido** (`pythonforge.transport.ServiceRuntime`) — FastAPI y
  gRPC en un proceso, con inicio atómico y apagado drenado.
- **Seguridad** (`pythonforge.security`) — JWT (HS256/RS256/PS256/EdDSA),
  auth bearer/cookie para FastAPI y bearer por metadata para gRPC.
- **Criptografía** (`pythonforge.encrypt`) — AES-GCM, HMAC/SHA-256/BLAKE3,
  RSA-OAEP, ECDH, Ed25519, más adaptadores KMS inyectables de AWS/Azure/GCP.
- **Trabajo en segundo plano** (`pythonforge.tools`) — jobs de
  intervalo/cron y una cola de workers acotada con backpressure real.
- **CLI** (`qpython`) — genera servicios FastAPI, gRPC o híbridos y
  certificados de desarrollo.
- **Logging** (`pythonforge.logger`) — logs estructurados en JSON/texto con
  redacción automática de secretos.
- **Telemetría** (`pythonforge.telemetry`) — integración opcional de
  OpenTelemetry para FastAPI, HTTPX y gRPC.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

La instalación base sólo trae `fastapi`, `pydantic-settings`, `httpx`,
`PyYAML` y `python-dotenv`. Todo lo demás es un extra:

| Extra | Agrega |
| --- | --- |
| `grpc` | `grpcio`, `grpcio-health-checking`, `protobuf` |
| `security` | `PyJWT[crypto]`, `cryptography`, `blake3` |
| `telemetry` | SDK de OpenTelemetry + instrumentación FastAPI/HTTPX/gRPC |
| `aws` / `azure` / `gcp` | Un SDK de proveedor KMS cada uno |
| `cli` | `typer` (la CLI de scaffolding `qpython`) |
| `all` | Todas las capacidades de runtime anteriores, excluyendo `dev` |
| `dev` | pytest, cobertura, mypy, ruff, bandit, pip-audit, build, twine, uvicorn |

## Inicio rápido

```python
from fastapi import APIRouter
from pythonforge.config import load_config
from pythonforge.transport.http import create_app

router = APIRouter()


@router.get("/api/v1/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from PythonForge"}


config = load_config()  # descubre application.yaml en el directorio actual, si existe
app = create_app(config, routers=[router])
```

Ejecútalo con cualquier servidor ASGI, por ejemplo `uvicorn myapp:app`. Ver
`examples/fastapi_service/` para un ejemplo completo ejecutable, incluyendo
cómo los campos TLS de `ServerHTTPConfig` se mapean a las opciones `ssl_*` de
uvicorn.

O genera un servicio completo:

```bash
pip install "pythonforge[cli,grpc]"
qpython new hybrid my-service   # FastAPI + gRPC en un proceso
```

## Documentación

- [docs/configuration.es.md](docs/configuration.es.md) — modelo de settings,
  precedencia de fuentes, descubrimiento de archivos, variables de entorno,
  secretos.
- [docs/http.es.md](docs/http.es.md) — `create_app`, middleware,
  health/readiness, manejo de errores, `ForgeClient`.
- [docs/grpc.es.md](docs/grpc.es.md) — servidor/cliente gRPC,
  interceptores, generación de stubs y el `ServiceRuntime` híbrido.
- [docs/security.es.md](docs/security.es.md) — JWT, autenticación en ambos
  transportes, criptografía local y proveedores KMS.
- [docs/background-work.es.md](docs/background-work.es.md) — jobs, workers
  y la CLI `qpython`.
- [docs/observability.es.md](docs/observability.es.md) — esquema de logs,
  redacción e integración con OpenTelemetry.

Las versiones en inglés están disponibles junto a cada archivo (sin sufijo
`.es`).

## Desarrollo

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy .typing/pythonforge tests
python -m pytest --cov=pythonforge --cov-report=term-missing --cov-fail-under=85
python -m bandit -q -r src
python -m pip_audit
```
