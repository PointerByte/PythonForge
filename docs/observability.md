# Observability

*Lee esto en español: [observability.es.md](observability.es.md)*

`pythonforge.logger` and `pythonforge.telemetry` implement the log schema
and tracing conventions shared with GoForge/DenoForge.

## Logging

```python
import logging
from pythonforge.config import LoggerConfig
from pythonforge.logger import configure_logging, get_logger, log_event

configure_logging(LoggerConfig(level="INFO", format="json"))
logger = get_logger()  # "pythonforge" logger; create_app calls this for you

log_event(
    logger, logging.INFO, "request finished",
    process="http", method="GET", latency_ms=12.3,
    details={"path": "/health", "status_code": 200},
)
```

`configure_logging` is idempotent — calling it again (e.g. once per
`create_app`) replaces the previous handlers instead of stacking them.

### Schema

Every entry has the same fields, in both HTTP and (once implemented) gRPC:

| Field | Meaning |
| --- | --- |
| `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `timestamp` | ISO 8601, UTC |
| `trace_id` | From the current `RequestContext`, if any |
| `request_id` | From the current `RequestContext`, if any |
| `message` | The log message |
| `details` | Structured, sanitized payload |
| `process` | Logical component, e.g. `"http"` |
| `method` | e.g. HTTP method or RPC name |
| `line` | Source line of the log call |
| `latency_ms` | Duration, when applicable |

Use `log_event(...)` rather than `logger.info(..., extra={"process": ...})`
directly: the stdlib `logging` module reserves `process`/`processName` for
the OS PID, so passing `process` via `extra` raises a `KeyError`. `log_event`
handles the remapping for you.

### Redaction

`pythonforge.logger.sanitizer.redact` walks `details` recursively (dicts,
lists, tuples, at any depth) and replaces sensitive values with
`***REDACTED***`, matching case-insensitively. `Authorization` and `Cookie`
are always redacted; `LoggerConfig.sensitive_keys` adds more:

```python
configure_logging(LoggerConfig(sensitive_keys=["x-internal-token"]))
```

Request/response bodies are never read or logged unless a handler
explicitly opts in for that operation.

### Sinks

- **stdout/stderr** — always configured (`logging.StreamHandler`).
- **File, with rotation** — set `LoggerConfig.file_path`; `max_bytes` and
  `backup_count` control rotation (`logging.handlers.RotatingFileHandler`).

### Format

`LoggerConfig.format` is `"json"` (default) or `"text"`. Both formats carry
the same schema fields.

## Telemetry

```python
from pythonforge.config import TraceConfig
from pythonforge.telemetry import configure_telemetry

provider = configure_telemetry(TraceConfig(enabled=True, exporter="console"))
with provider.tracer.start_as_current_span("do-work"):
    ...
provider.shutdown()
```

`create_app` calls `configure_telemetry(config.trace)` for you and
instruments the FastAPI app (`provider.instrument_fastapi(app)`); call
`provider.instrument_httpx()` yourself if you use HTTPX directly instead of
`ForgeClient`.

### Fail-open by design

Telemetry must never break the app:

- `trace.enabled = False` → a no-op provider (`NoOpTelemetryProvider`); every
  method is a safe no-op.
- `trace.enabled = True` but the `telemetry` extra isn't installed → also a
  no-op provider, after logging one warning. This differs from the general
  "missing extra" rule (which raises `MissingExtraError`) — observability is
  never allowed to take the app down.
- `trace.exporter = "otlp"` without the OTLP exporter package installed →
  falls back to the console exporter with a warning.

Install `pythonforge[telemetry]` to get real spans, exported via
`opentelemetry-instrumentation-fastapi` / `-httpx` (gRPC instrumentation is
declared but unused until the gRPC transport exists).
