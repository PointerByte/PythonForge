# Observabilidad

*Read this in English: [observability.md](observability.md)*

`pythonforge.logger` y `pythonforge.telemetry` implementan el esquema de
logs y las convenciones de trazado compartidas con GoForge/DenoForge.

## Logging

```python
import logging
from pythonforge.config import LoggerConfig
from pythonforge.logger import configure_logging, get_logger, log_event

configure_logging(LoggerConfig(level="INFO", format="json"))
logger = get_logger()  # logger "pythonforge"; create_app ya llama esto por ti

log_event(
    logger, logging.INFO, "request finished",
    process="http", method="GET", latency_ms=12.3,
    details={"path": "/health", "status_code": 200},
)
```

`configure_logging` es idempotente — llamarlo de nuevo (por ejemplo, una vez
por `create_app`) reemplaza los handlers anteriores en vez de apilarlos.

### Esquema

Cada entrada tiene los mismos campos, tanto en HTTP como (una vez
implementado) en gRPC:

| Campo | Significado |
| --- | --- |
| `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `timestamp` | ISO 8601, UTC |
| `trace_id` | Del `RequestContext` actual, si existe |
| `request_id` | Del `RequestContext` actual, si existe |
| `message` | El mensaje del log |
| `details` | Payload estructurado y sanitizado |
| `process` | Componente lógico, ej. `"http"` |
| `method` | ej. método HTTP o nombre de RPC |
| `line` | Línea de origen de la llamada al log |
| `latency_ms` | Duración, cuando aplica |

Usa `log_event(...)` en vez de `logger.info(..., extra={"process": ...})`
directamente: el módulo `logging` de la stdlib reserva `process`/
`processName` para el PID del sistema operativo, así que pasar `process` vía
`extra` lanza un `KeyError`. `log_event` se encarga de ese remapeo por ti.

### Redacción

`pythonforge.logger.sanitizer.redact` recorre `details` recursivamente
(dicts, listas, tuplas, a cualquier profundidad) y reemplaza los valores
sensibles con `***REDACTED***`, comparando sin distinguir
mayúsculas/minúsculas. `Authorization` y `Cookie` siempre se redactan;
`LoggerConfig.sensitive_keys` agrega más:

```python
configure_logging(LoggerConfig(sensitive_keys=["x-internal-token"]))
```

Los cuerpos de request/response nunca se leen ni se registran a menos que un
handler lo habilite explícitamente para esa operación.

### Sinks

- **stdout/stderr** — siempre configurado (`logging.StreamHandler`).
- **Archivo, con rotación** — fija `LoggerConfig.file_path`; `max_bytes` y
  `backup_count` controlan la rotación (`logging.handlers.RotatingFileHandler`).

### Formato

`LoggerConfig.format` es `"json"` (por defecto) o `"text"`. Ambos formatos
llevan los mismos campos del esquema.

## Telemetría

```python
from pythonforge.config import TraceConfig
from pythonforge.telemetry import configure_telemetry

provider = configure_telemetry(TraceConfig(enabled=True, exporter="console"))
with provider.tracer.start_as_current_span("do-work"):
    ...
provider.shutdown()
```

`create_app` llama a `configure_telemetry(config.trace)` por ti e instrumenta
la app FastAPI (`provider.instrument_fastapi(app)`); llama tú mismo a
`provider.instrument_httpx()` si usas HTTPX directamente en vez de
`ForgeClient`.

### Diseñado para fallar de forma segura

La telemetría nunca debe romper la aplicación:

- `trace.enabled = False` → un provider no-op (`NoOpTelemetryProvider`);
  cada método es un no-op seguro.
- `trace.enabled = True` pero el extra `telemetry` no está instalado →
  también un provider no-op, después de registrar un warning. Esto difiere
  de la regla general de "extra faltante" (que lanza `MissingExtraError`) —
  la observabilidad nunca puede tumbar la aplicación.
- `trace.exporter = "otlp"` sin el paquete del exportador OTLP instalado →
  cae de vuelta al exportador de consola con un warning.

Instala `pythonforge[telemetry]` para obtener spans reales, exportados vía
`opentelemetry-instrumentation-fastapi` / `-httpx` (la instrumentación de
gRPC está declarada pero sin uso hasta que exista el transporte gRPC).
