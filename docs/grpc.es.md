# Transporte gRPC y runtime híbrido

*Read this in English: [grpc.md](grpc.md)*

Requiere el extra `grpc` (`pip install "pythonforge[grpc]"`). Importar
`pythonforge.transport.grpc` sin él lanza `MissingExtraError` nombrando el
extra, en vez de un `ModuleNotFoundError` pelado.

## Servidor

```python
from pythonforge.config import load_config
from pythonforge.transport.grpc import create_grpc_server

config = load_config()
server = create_grpc_server(config.server.grpc)
my_pb2_grpc.add_MyServiceServicer_to_server(MyService(), server)
await server.start()
```

`create_grpc_server` devuelve un `grpc.aio.Server` normal, ya configurado
con la cadena de interceptores por defecto, límites de tamaño de mensaje,
TLS/mTLS desde la configuración, y el servicio estándar `grpc.health.v1`.
Se le adjuntan dos atributos de conveniencia:

- `server.pythonforge_port` — el puerto realmente enlazado. Con
  `ServerGRPCConfig(port=0)` el sistema operativo elige un puerto efímero,
  que es como los tests de integración evitan colisiones de puertos.
- `server.pythonforge_health` — el servicer de health, para que readiness
  pueda pasar servicios a `NOT_SERVING` mientras drena.

### Cadena de interceptores

`default_interceptors()` devuelve, del más externo al más interno:

1. **`RequestContextInterceptor`** — traduce la metadata `x-request-id`,
   `traceparent`/`tracestate` al mismo `RequestContext` que puebla el
   middleware HTTP.
2. **`LoggingInterceptor`** — una entrada por RPC, con el esquema de logs
   compartido.
3. **`ErrorInterceptor`** — mapea excepciones a `grpc.StatusCode`.
4. **`JWTAuthInterceptor`** (opcional) — ver más abajo.

**El orden es determinante.** `interceptors[0]` envuelve a todo lo que
viene después, así que `ErrorInterceptor` debe quedar *por fuera* de auth —
si no, un fallo de autenticación lo esquiva y sale como un crash sin
manejar en vez de `UNAUTHENTICATED`. Pasar `auth=` a `create_grpc_server`
lo coloca correctamente por ti:

```python
from pythonforge.transport.grpc.interceptors.auth import JWTAuthInterceptor

server = create_grpc_server(
    config.server.grpc,
    auth=JWTAuthInterceptor(config.jwt, scopes=["widgets:read"]),
)
```

Sólo reemplaza `interceptors=` por completo si asumes la responsabilidad
del ordenamiento.

### Mapeo de errores

Simétrico con los manejadores de excepciones de HTTP:

| Excepción | Estado gRPC | Equivalente HTTP |
| --- | --- | --- |
| `AuthenticationError` | `UNAUTHENTICATED` | 401 |
| `AuthorizationError` | `PERMISSION_DENIED` | 403 |
| `ConfigurationError` | `FAILED_PRECONDITION` | — |
| `TransportError` | `UNAVAILABLE` | — |
| otro `PythonForgeError` | `INVALID_ARGUMENT` | 400 |
| cualquier otra cosa | `INTERNAL` (mensaje genérico) | 500 |

El detalle interno de la excepción se registra en el log, nunca se devuelve
al llamador.

### Escribir servicers

Los interceptores aceptan handlers `async def` y `def` normales — el propio
servicer de health de grpc es síncrono, y los servicers de terceros pueden
serlo también.

## Cliente

```python
from pythonforge.transport.grpc import context_metadata, context_timeout, create_channel

async with create_channel("service:50051", config.client) as channel:
    stub = MyServiceStub(channel)
    response = await stub.MyRpc(
        request,
        metadata=context_metadata(),        # propaga request id + traceparent
        timeout=context_timeout(5.0),        # recortado al deadline del contexto
    )
```

`context_timeout` lanza `TransportError` si el deadline de la petición ya
venció, así que una petición expirada nunca abre una nueva llamada
downstream. Usa `force_insecure=True` para desarrollo local en texto plano.

## Generación de stubs

Los stubs se generan en tiempo de desarrollo y se commitean; `grpcio-tools`
nunca es una dependencia de runtime:

```bash
./scripts/gen_protos.sh
```

La salida va a `src/transport/grpc/generated/`, excluido de ruff, mypy y
cobertura.

## Runtime híbrido

`ServiceRuntime` corre FastAPI y gRPC en un solo proceso. Vive en
`pythonforge.transport` (no bajo `grpc/`) para que un servicio sólo-HTTP
pueda usarlo sin el extra `grpc`.

```python
import uvicorn
from pythonforge.transport import ServiceRuntime

runtime = ServiceRuntime(config, shutdown_timeout=30.0)
runtime.add_uvicorn_server(uvicorn.Server(uvicorn.Config(app, ...)))
runtime.add_grpc_server(grpc_server)
await runtime.serve_forever()   # retorna ante SIGINT/SIGTERM
```

- **Inicio atómico** — si algún transporte falla al levantar, los que ya
  arrancaron se cierran antes de que se propague el `LifecycleError`.
- **Apagado ordenado** — los transportes se detienen en orden inverso, el
  trabajo en curso drena, y un transporte lento o que falla no puede
  bloquear el resto del apagado (ambos casos acotados por
  `shutdown_timeout` y registrados en el log).
- `serve_forever(handle_signals=False)` omite los manejadores de señales;
  `async with runtime:` arranca y detiene alrededor de un bloque.

`qpython new hybrid <nombre>` genera un ejemplo funcional de todo esto.
