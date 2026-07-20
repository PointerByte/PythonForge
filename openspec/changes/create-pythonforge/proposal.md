# Propuesta: crear PythonForge

## Por qué

DenoForge y GoForge ofrecen las mismas convenciones esenciales —configuración,
transporte HTTP/gRPC, observabilidad, JWT, criptografía, jobs y workers— pero no
existe un paquete equivalente para servicios Python. PythonForge debe cubrir ese
vacío con APIs idiomáticas de Python y una experiencia coherente entre servicios
FastAPI y gRPC.

## Qué cambia

- Se crea el paquete distribuible `pythonforge` con layout `src/` y soporte para
  Python 3.12 o superior.
- FastAPI se adopta como framework principal para HTTP/ASGI.
- `grpcio` se integra como transporte de primera clase, con servidores, clientes
  e interceptores unary y streaming compatibles con las capacidades comunes.
- Se crean módulos independientes para configuración, observabilidad, seguridad,
  criptografía, trabajo en segundo plano y scaffolding.
- Se define una instalación base pequeña y extras explícitos para gRPC,
  OpenTelemetry, proveedores KMS, CLI y desarrollo.
- Se prepara la distribución reproducible en PyPI y una CLI `qpython` para crear
  servicios FastAPI, gRPC o híbridos.

## Capacidades

### Capacidades nuevas

- `project-foundation`: paquete, compatibilidad de Python, dependencias y API pública.
- `transport-runtime`: runtime FastAPI y gRPC, clientes y ciclo de vida compartido.
- `configuration`: carga validada de YAML/JSON, `.env` y variables de entorno.
- `observability`: logs estructurados, sanitización, contexto y OpenTelemetry.
- `security-cryptography`: JWT, middleware/interceptores, headers y proveedores criptográficos.
- `background-work`: jobs y workers asíncronos controlados por el ciclo de vida.
- `tooling-distribution`: CLI, pruebas, calidad, documentación y publicación en PyPI.

### Capacidades modificadas

Ninguna. PythonForge parte de un directorio sin implementación previa.

## Impacto

- Nuevos archivos bajo `src/pythonforge/`, `tests/`, `examples/`, `docs/` y
  `protos/`, además de `pyproject.toml`, README, licencia y workflows.
- Dependencias base: FastAPI, Pydantic Settings, HTTPX, PyYAML, criptografía/JWT
  y utilidades de concurrencia compatibles con ASGI.
- Dependencias opcionales: gRPC/protobuf, OpenTelemetry, AWS KMS, Azure Key Vault,
  Google Cloud KMS, scaffolding y toolchain de desarrollo/publicación.
- La API pública seguirá la intención funcional de DenoForge y GoForge, sin
  copiar nombres que no sean idiomáticos en Python.

## Fuera de alcance

- Implementar lógica de negocio o persistencia específica de una aplicación.
- Mantener compatibilidad binaria con Go o Deno.
- Ejecutar servicios cloud reales durante la suite unitaria.
- Publicar una versión antes de aprobar todos los criterios de aceptación.

## Criterios de éxito

- Un consumidor puede crear un servicio FastAPI, uno gRPC o uno híbrido usando
  los mismos settings, autenticación, logging, trazas y apagado ordenado.
- La instalación base no obliga a descargar SDKs cloud.
- Los módulos se pueden importar y probar de forma independiente.
- La suite valida HTTP, gRPC unary/streaming, criptografía, JWT, jobs, workers y
  adaptadores KMS falsos, con al menos 85 % de cobertura de líneas.
- El wheel y el sdist se construyen, se validan con Twine y se pueden instalar en
  un entorno virtual limpio.
