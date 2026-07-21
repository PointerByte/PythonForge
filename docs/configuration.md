# Configuration

*Lee esto en español: [configuration.es.md](configuration.es.md)*

`pythonforge.config` provides a typed settings model built on
[`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
Every value is validated up front — an invalid combination (e.g. TLS enabled
without a certificate) fails before any socket opens.

## Loading settings

```python
from pythonforge.config import load_config

config = load_config()
```

`load_config` builds a `FullConfig` instance with this precedence, lowest to
highest:

1. Field defaults.
2. A discovered `application.yaml` / `application.yml` / `application.json`
   (first match, in that order) in `config_dir` (default: the current
   working directory), or the exact file given via `config_path`.
3. Files passed via `env_files` (dotenv format).
4. Environment variables (`PYTHONFORGE_<SECTION>__<FIELD>`, case-insensitive).
5. Keyword overrides passed directly to `load_config(...)`.

```python
from pathlib import Path
from pythonforge.config import load_config

config = load_config(
    config_dir=Path("./config"),      # search this dir for application.yaml
    env_files=".env",                  # or a list of paths
    server={"http": {"port": 9000}},   # highest-precedence override
)
```

Two independent calls never share state — `load_config` never mutates a
process-wide singleton, so building several configs (e.g. one per test) is
safe.

## Sections

| Section | Model | Notes |
| --- | --- | --- |
| `app` | `AppConfig` | `name`, `env` (`development`/`staging`/`production`/`test`), `debug`, `version` |
| `server.http` | `ServerHTTPConfig` | host/port, health/ready paths, CORS, rate limiting, TLS/mTLS |
| `server.grpc` | `ServerGRPCConfig` | host/port, TLS/mTLS (transport not implemented yet) |
| `client` | `ClientConfig` | timeouts, retries, TLS/mTLS for `ForgeClient` |
| `logger` | `LoggerConfig` | level, `json`/`text` format, file rotation, extra sensitive keys |
| `trace` | `TraceConfig` | OpenTelemetry enable flag, sampling, exporter |
| `jwt` | `JWTConfig` | reserved for the security module (not implemented yet) |
| `encrypt` | `EncryptConfig` | reserved for the encryption module (not implemented yet) |

Access nested fields normally: `config.server.http.port`,
`config.logger.level`, etc.

## Environment variables

Nested fields map to `PYTHONFORGE_<SECTION>__<FIELD>` using a double
underscore, matching the nesting depth:

```bash
export PYTHONFORGE_SERVER__HTTP__PORT=9000
export PYTHONFORGE_SERVER__GRPC__PORT=51000
export PYTHONFORGE_LOGGER__LEVEL=DEBUG
```

## `application.yaml` example

```yaml
app:
  name: my-service
  env: production

server:
  http:
    port: 8080
    cors_origins:
      - https://app.example.com
    rate_limit_enabled: true
    rate_limit_requests: 100
    rate_limit_window_seconds: 60

logger:
  level: INFO
  format: json
  sensitive_keys:
    - x-internal-token

trace:
  enabled: true
  exporter: console
```

## Secrets

Fields that hold sensitive material (currently `jwt.secret_key`) use
Pydantic's `SecretStr`. They never appear in full in `repr()`, `str()`, or in
the message of a `ConfigurationError` raised on invalid input — only the
field location and a generic message are included, never the offending
value.

## Errors

Invalid configuration raises `pythonforge.errors.ConfigurationError` (a
`PythonForgeError` subclass) with the failing field paths, before any
resource is created:

```python
from pythonforge.config import load_config
from pythonforge.errors import ConfigurationError

try:
    load_config(server={"http": {"tls_enabled": True}})  # missing cert/key
except ConfigurationError as exc:
    print(exc)  # "invalid configuration: server.http: Value error, ..."
```
