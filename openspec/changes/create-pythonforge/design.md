# Diseño: PythonForge

## Contexto

PythonForge trasladará a Python las capacidades documentadas en DenoForge y
GoForge. DenoForge favorece módulos independientes y dependencias cloud lazy;
GoForge aporta configuración central, bootstrap de transportes, interceptores,
OpenTelemetry y CLIs de scaffolding. PythonForge conservará esas propiedades,
usando patrones ASGI y `asyncio` idiomáticos.

## Objetivos

- Hacer de FastAPI el framework principal sin acoplar la lógica reutilizable a
  objetos `Request` o `Context` concretos.
- Dar a gRPC el mismo nivel de soporte que HTTP, incluyendo unary, streaming,
  metadata, auth, logging, tracing, TLS/mTLS y graceful shutdown.
- Ofrecer instalaciones por extras y evitar SDKs pesados en el núcleo.
- Exponer APIs tipadas, asíncronas y sencillas de sustituir en pruebas.

## No objetivos

- Crear un framework web nuevo encima de FastAPI.
- Ocultar las APIs normales de FastAPI, Starlette o grpcio.
- Acoplar el paquete a un contenedor de inyección de dependencias específico.

## Arquitectura

```text
PythonForge/
├── src/pythonforge/
│   ├── config/                 # settings y carga de fuentes
│   ├── transport/
│   │   ├── http/               # factory/lifespan FastAPI y cliente HTTPX
│   │   └── grpc/               # servidor, canal e interceptores grpc.aio
│   ├── logger/                 # esquema, formatter, sanitizer y adaptadores
│   ├── telemetry/              # trazas, métricas y propagación
│   ├── security/               # JWT, cookies, headers e integración de transporte
│   ├── encrypt/
│   │   ├── local/              # AES, RSA, ECDH, Ed25519, hashes
│   │   └── kms/                # AWS, Azure y GCP mediante extras
│   ├── tools/                  # jobs, workers y modo test
│   └── cli/                    # qpython y utilidades de certificados
├── protos/                     # contratos de ejemplo y health
├── tests/                      # unitarias, integración y contratos
├── examples/                   # FastAPI, gRPC e híbrido
└── docs/                       # uso, configuración y publicación
```

La lógica común recibe un `RequestContext` propio almacenado en `contextvars`.
Los adaptadores FastAPI y gRPC traducen request/metadata al mismo contexto. Esto
permite compartir request ID, W3C Trace Context, claims, deadline, atributos y
procesos downstream sin importar el transporte.

## Decisiones

### FastAPI como runtime principal

`create_app(settings, ...) -> FastAPI` será el factory canónico. Usará el
lifespan de FastAPI para iniciar y cerrar telemetría, jobs y clientes. No habrá
estado global obligatorio; una instancia podrá coexistir con otras en pruebas.

### gRPC asíncrono y compatible

La implementación usará `grpc.aio`. `create_grpc_server(...)` instalará cadenas
de interceptores para contexto, tracing, logging y JWT. Los stubs se generarán
con `grpcio-tools` durante desarrollo y los artefactos Python requeridos se
incluirán en el paquete. El runtime no dependerá de `grpcio-tools`.

Un `ServiceRuntime` opcional coordinará FastAPI y gRPC en el mismo proceso. Si
uno falla al iniciar, cerrará lo ya iniciado; al terminar, dejará de aceptar
trabajo, drenará requests/RPCs y cerrará recursos con timeout configurable.

### Configuración tipada

Pydantic Settings será la fuente de verdad. El orden de precedencia será:
defaults < `application.yaml|yml|json` < archivos declarados en `env.files` <
variables de entorno < overrides del constructor. Las claves anidadas usarán
`__` en variables (por ejemplo, `SERVER__GRPC__PORT`). Los secretos usarán tipos
secretos y nunca aparecerán completos en `repr`, errores ni logs.

### Dependencias y extras

El `pyproject.toml` declarará dependencias directas con rangos compatibles y un
lock separado para desarrollo/CI. Extras previstos:

- `grpc`: `grpcio`, `protobuf`.
- `telemetry`: SDK e instrumentaciones OpenTelemetry para FastAPI, HTTPX y gRPC.
- `aws`, `azure`, `gcp`: un SDK por proveedor KMS.
- `cli`: Typer y sus dependencias de interfaz.
- `dev`: pytest, cobertura, tipado, lint, auditoría, build y Twine.
- `all`: unión documentada de capacidades de runtime, excluyendo `dev`.

Las importaciones opcionales fallarán con un mensaje que indique el extra que
debe instalarse, por ejemplo `pythonforge[grpc]`.

### Seguridad y criptografía

El backend local usará `cryptography`; JWT soportará HS256, RS256, PS256 y
EdDSA. Las llaves tendrán una representación `KeyData` estable con proveedor,
referencia, material público y material privado/simétrico sólo cuando corresponda.
Los KMS implementarán protocolos inyectables para probar sin credenciales ni red.

### Observabilidad segura

El esquema de log conservará los campos comunes de los Forge: `level`,
`timestamp`, `trace_id`, `message`, `details`, `process`, `method`, `line` y
`latency_ms`. Los cuerpos estarán deshabilitados por defecto. Authorization,
Cookie y claves configuradas como sensibles se redactarán antes de llegar a un
sink. OpenTelemetry se podrá deshabilitar sin cambiar los handlers.

## Manejo de errores

- La configuración inválida falla antes de abrir sockets.
- Errores HTTP se traducen a respuestas JSON estables y errores gRPC a códigos
  `StatusCode`, sin exponer excepciones internas.
- Auth inválida responde HTTP 401 o gRPC `UNAUTHENTICATED`; autorización
  insuficiente usa HTTP 403 o gRPC `PERMISSION_DENIED`.
- Timeouts y cancelación se propagan a operaciones downstream cuando sea posible.

## Estrategia de pruebas

- Unitarias por módulo y sin red para configuración, logger, JWT y criptografía.
- Integración FastAPI con transporte ASGI de HTTPX.
- Integración gRPC sobre puerto efímero para unary y streaming.
- Contratos compartidos que comparan contexto, auth y esquema de logging en HTTP
  y gRPC.
- Dobles inyectados para AWS, Azure y GCP KMS.
- Smoke test del wheel en un entorno virtual limpio.

## Riesgos y mitigaciones

- **Superficie de dependencias grande:** extras y carga perezosa.
- **Diferencias entre ASGI y gRPC:** contexto propio y pruebas de contrato.
- **Captura accidental de secretos:** allowlist de campos, redacción previa al
  sink y cuerpos desactivados.
- **Código protobuf desactualizado:** generación reproducible y verificación CI.
- **Tareas huérfanas al apagar:** ownership explícito y `TaskGroup`/lifespan.

## Migración

No existe una versión Python anterior. La primera versión será `0.1.0` y podrá
ajustar APIs dentro de la serie `0.x`, documentando cada cambio en un changelog.
