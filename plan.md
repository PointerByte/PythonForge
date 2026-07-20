# Plan de implementación de PythonForge

## Objetivo

Construir una dependencia Python modular inspirada en DenoForge y GoForge para
servicios modernos. FastAPI será el framework principal y gRPC será un transporte
de primera clase compatible: ambos compartirán configuración, seguridad,
observabilidad, contexto de petición y ciclo de vida.

## Principios obligatorios

- Usar Python 3.12 o superior y APIs asíncronas para I/O.
- No instalar paquetes globalmente. Toda instalación se hará en `.venv`.
- Mantener el núcleo pequeño; gRPC, telemetría, KMS cloud, CLI y desarrollo se
  separarán en extras.
- No registrar secretos, tokens, cookies, credenciales ni cuerpos por defecto.
- Mantener lógica reusable independiente de FastAPI y grpcio mediante protocolos
  y adaptadores.
- Probar HTTP y gRPC con los mismos contratos de contexto, auth y observabilidad.

## Preparación del entorno

Ejecutar desde la raíz de `PythonForge` antes de instalar dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Después de crear `pyproject.toml`, instalar desarrollo únicamente dentro del
entorno activo:

```bash
python -m pip install -e ".[dev]"
```

En Windows PowerShell, la activación equivalente será:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -e ".[dev]"
```

## Estrategia de dependencias

| Grupo | Propósito | Dependencias previstas |
| --- | --- | --- |
| Núcleo | HTTP, modelos, settings y cliente | `fastapi`, `pydantic-settings`, `httpx`, `PyYAML` |
| Seguridad | JWT y primitivas locales | `PyJWT[crypto]`, `cryptography`, `blake3` |
| `grpc` | Transporte RPC | `grpcio`, `protobuf` |
| `telemetry` | Trazas, métricas e instrumentación | paquetes `opentelemetry-*` para FastAPI, HTTPX y gRPC |
| `aws` | AWS KMS | `boto3` |
| `azure` | Azure Key Vault | `azure-identity`, `azure-keyvault-keys` |
| `gcp` | Google Cloud KMS | `google-cloud-kms` |
| `cli` | Scaffolding y certificados | `typer` |
| `dev` | Calidad, pruebas y publicación | `pytest`, `pytest-asyncio`, `pytest-cov`, `grpcio-tools`, `ruff`, `mypy`, `bandit`, `pip-audit`, `build`, `twine` |

Antes de fijar versiones, comprobar compatibilidad con Python 3.12+, FastAPI,
Pydantic v2, `grpc.aio` y la versión de protobuf elegida. Declarar rangos directos
en `pyproject.toml`; mantener un lock reproducible separado para desarrollo/CI.

## Fases

### 1. Fundación y empaquetado

Crear `pyproject.toml` con backend de build, metadata PyPI, licencia Apache-2.0,
extras, entry points y configuración de herramientas. Crear el layout
`src/pythonforge`, tests, ejemplos, documentación y un API público mínimo. Añadir
un smoke test que instale el wheel en una `.venv` limpia. Actualizar `.gitignore`
para excluir `.venv/`, `dist/`, `build/`, `*.egg-info`, caches y reportes locales.

Resultado: `python -m build` genera wheel y sdist válidos, y el paquete base se
puede importar sin instalar extras cloud o gRPC.

### 2. Configuración y contexto común

Implementar modelos Pydantic para `app`, `server.http`, `server.grpc`, `client`,
`logger`, `traces`, `jwt` y `encrypt`. La precedencia será defaults, archivo de
aplicación, archivos `.env`, entorno y overrides explícitos. Implementar un
`RequestContext` basado en `contextvars` con request ID, trace context, claims,
deadline y procesos downstream.

Resultado: FastAPI y gRPC pueden consumir los mismos settings y contexto sin
estado global obligatorio.

### 3. Runtime FastAPI principal

Crear un factory de aplicación con lifespan, health configurable, manejo estable
de errores y graceful shutdown. Integrar middleware para contexto, seguridad,
logging, OpenTelemetry, CORS y rate limit. Crear cliente HTTPX asíncrono con
timeouts, TLS/mTLS y propagación de trazas.

Resultado: un ejemplo FastAPI sirve `/health` y `/api/v1/hello`, y las pruebas
ASGI validan éxito, errores, auth, logs y apagado.

### 4. Compatibilidad gRPC

Implementar servidor y cliente sobre `grpc.aio`; soportar RPC unary, server/client
streaming y bidi streaming. Añadir interceptores para contexto, bearer JWT,
logging, tracing, rate limit y mapeo de errores. Soportar TLS/mTLS, metadata,
deadlines, cancelación y health. Generar stubs de manera reproducible.

Crear un runtime híbrido que coordine FastAPI y gRPC en el mismo proceso y cierre
ambos transportes si uno falla o recibe una señal de terminación.

Resultado: pruebas de integración sobre puertos efímeros demuestran paridad de
auth, trazas, logs y shutdown entre HTTP y gRPC.

### 5. Logging y telemetría

Implementar el esquema común de GoForge/DenoForge en JSON y texto, logging con
contexto, procesos downstream, latencia, rotación y sinks reemplazables. Sanitizar
headers y campos sensibles antes del formatter. Incorporar OpenTelemetry como
extra para trazas y métricas, sin alterar handlers cuando esté deshabilitado.

Resultado: los contratos verifican el mismo esquema para FastAPI y gRPC y que
ningún secreto ni body deshabilitado llegue al sink.

### 6. Seguridad y criptografía

Implementar JWT HS256, RS256, PS256 y EdDSA; auth bearer/cookie en FastAPI y
bearer metadata en gRPC; validadores, claims tipados y headers HTTP de seguridad.
Implementar repositorios para AES-GCM, HMAC/SHA-256/BLAKE3, RSA-OAEP, ECDH y
firmas Ed25519/RSA. Añadir adaptadores KMS opcionales con protocolos inyectables.

Resultado: round-trips criptográficos, casos negativos y dobles AWS/Azure/GCP
funcionan sin acceder a servicios cloud.

### 7. Jobs, workers y herramientas

Implementar jobs de intervalo/cron y workers con concurrencia acotada,
backpressure, pause/resume/stop, modo test y cierre desde el lifespan. Crear
`qpython new fastapi|grpc|hybrid` y una utilidad para claves/certificados.

Resultado: los scaffolds se ejecutan, usan YAML por defecto y nunca instalan sus
dependencias fuera de un entorno virtual explícitamente creado por el usuario.

### 8. Calidad, documentación y release

Documentar instalación por extras, configuración, ejemplos FastAPI/gRPC/híbrido,
seguridad y migraciones. Ejecutar Ruff, mypy, pytest con cobertura mínima de 85 %,
Bandit y pip-audit. Validar wheel/sdist con Twine e instalar el wheel en una
`.venv` nueva. Publicar primero en TestPyPI, realizar smoke test y después en PyPI.

Resultado: CI en verde, documentación bilingüe, artefactos reproducibles y tag
`v0.1.0` asociado exactamente al commit publicado.

## Orden de entrega recomendado

1. Fundación, configuración y contexto.
2. FastAPI y cliente HTTP.
3. Logging/telemetría compartidos.
4. gRPC e híbrido.
5. Seguridad y criptografía local.
6. Jobs/workers, KMS cloud y CLIs.
7. Endurecimiento, documentación y publicación.

## Criterios de finalización

- Todos los requisitos de `openspec/changes/create-pythonforge/specs/` tienen pruebas.
- FastAPI es usable con la instalación principal documentada.
- gRPC unary/streaming funciona mediante el extra `grpc` y comparte contexto.
- No hay importaciones obligatorias de SDKs cloud en el paquete base.
- Lint, tipado, tests, cobertura y análisis de seguridad pasan en CI.
- Wheel y sdist pasan `twine check` y se instalan en un entorno limpio.
- README, changelog y comandos de `push.txt` reflejan la versión de release.
