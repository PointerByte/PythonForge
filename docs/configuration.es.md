# Configuración

*Read this in English: [configuration.md](configuration.md)*

`pythonforge.config` provee un modelo de settings tipado construido sobre
[`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
Cada valor se valida por adelantado — una combinación inválida (por ejemplo,
TLS habilitado sin certificado) falla antes de abrir cualquier socket.

## Cargar la configuración

```python
from pythonforge.config import load_config

config = load_config()
```

`load_config` construye una instancia `FullConfig` con esta precedencia, de
menor a mayor:

1. Valores por defecto de los campos.
2. Un `application.yaml` / `application.yml` / `application.json`
   descubierto (la primera coincidencia, en ese orden) en `config_dir`
   (por defecto: el directorio de trabajo actual), o el archivo exacto
   indicado en `config_path`.
3. Archivos pasados en `env_files` (formato dotenv).
4. Variables de entorno (`PYTHONFORGE_<SECCIÓN>__<CAMPO>`, sin distinguir
   mayúsculas/minúsculas).
5. Overrides por keyword pasados directamente a `load_config(...)`.

```python
from pathlib import Path
from pythonforge.config import load_config

config = load_config(
    config_dir=Path("./config"),      # busca application.yaml en este directorio
    env_files=".env",                  # o una lista de rutas
    server={"http": {"port": 9000}},   # override de mayor precedencia
)
```

Dos llamadas independientes nunca comparten estado — `load_config` nunca
muta un singleton a nivel de proceso, así que construir varias
configuraciones (por ejemplo, una por test) es seguro.

## Secciones

| Sección | Modelo | Notas |
| --- | --- | --- |
| `app` | `AppConfig` | `name`, `env` (`development`/`staging`/`production`/`test`), `debug`, `version` |
| `server.http` | `ServerHTTPConfig` | host/puerto, rutas health/ready, CORS, rate limiting, TLS/mTLS |
| `server.grpc` | `ServerGRPCConfig` | host/puerto, TLS/mTLS (transporte aún no implementado) |
| `client` | `ClientConfig` | timeouts, reintentos, TLS/mTLS para `ForgeClient` |
| `logger` | `LoggerConfig` | nivel, formato `json`/`text`, rotación de archivo, claves sensibles extra |
| `trace` | `TraceConfig` | flag de habilitación de OpenTelemetry, muestreo, exportador |
| `jwt` | `JWTConfig` | reservado para el módulo de seguridad (aún no implementado) |
| `encrypt` | `EncryptConfig` | reservado para el módulo de cifrado (aún no implementado) |

Accede a los campos anidados normalmente: `config.server.http.port`,
`config.logger.level`, etc.

## Variables de entorno

Los campos anidados se mapean a `PYTHONFORGE_<SECCIÓN>__<CAMPO>` usando un
doble guion bajo, siguiendo la profundidad del anidamiento:

```bash
export PYTHONFORGE_SERVER__HTTP__PORT=9000
export PYTHONFORGE_SERVER__GRPC__PORT=51000
export PYTHONFORGE_LOGGER__LEVEL=DEBUG
```

## Ejemplo de `application.yaml`

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

## Secretos

Los campos que guardan material sensible (actualmente `jwt.secret_key`)
usan `SecretStr` de Pydantic. Nunca aparecen completos en `repr()`, `str()`,
ni en el mensaje de un `ConfigurationError` lanzado por una entrada
inválida — sólo se incluyen la ruta del campo y un mensaje genérico, nunca
el valor ofensivo.

## Errores

Una configuración inválida lanza `pythonforge.errors.ConfigurationError`
(subclase de `PythonForgeError`) con las rutas de los campos que fallaron,
antes de crear cualquier recurso:

```python
from pythonforge.config import load_config
from pythonforge.errors import ConfigurationError

try:
    load_config(server={"http": {"tls_enabled": True}})  # falta cert/key
except ConfigurationError as exc:
    print(exc)  # "invalid configuration: server.http: Value error, ..."
```
