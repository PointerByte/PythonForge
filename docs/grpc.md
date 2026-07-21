# gRPC transport and the hybrid runtime

*Lee esto en español: [grpc.es.md](grpc.es.md)*

Requires the `grpc` extra (`pip install "pythonforge[grpc]"`). Importing
`pythonforge.transport.grpc` without it raises `MissingExtraError` naming
the extra, rather than a bare `ModuleNotFoundError`.

## Server

```python
from pythonforge.config import load_config
from pythonforge.transport.grpc import create_grpc_server

config = load_config()
server = create_grpc_server(config.server.grpc)
my_pb2_grpc.add_MyServiceServicer_to_server(MyService(), server)
await server.start()
```

`create_grpc_server` returns a plain `grpc.aio.Server`, already configured
with the default interceptor chain, message size limits, TLS/mTLS from
config, and the standard `grpc.health.v1` health service. Two convenience
attributes are attached:

- `server.pythonforge_port` — the port actually bound. With
  `ServerGRPCConfig(port=0)` the OS picks an ephemeral port, which is how
  integration tests avoid port collisions.
- `server.pythonforge_health` — the health servicer, so readiness can flip
  services to `NOT_SERVING` while draining.

### Interceptor chain

`default_interceptors()` returns, outermost first:

1. **`RequestContextInterceptor`** — translates `x-request-id`,
   `traceparent`/`tracestate` metadata into the same `RequestContext` the
   HTTP middleware populates.
2. **`LoggingInterceptor`** — one entry per RPC, in the shared log schema.
3. **`ErrorInterceptor`** — maps exceptions to `grpc.StatusCode`.
4. **`JWTAuthInterceptor`** (optional) — see below.

**Order is load-bearing.** `interceptors[0]` wraps everything after it, so
`ErrorInterceptor` must sit *outside* auth — otherwise an authentication
failure bypasses it and surfaces as an unhandled crash instead of
`UNAUTHENTICATED`. Passing `auth=` to `create_grpc_server` places it
correctly for you:

```python
from pythonforge.transport.grpc.interceptors.auth import JWTAuthInterceptor

server = create_grpc_server(
    config.server.grpc,
    auth=JWTAuthInterceptor(config.jwt, scopes=["widgets:read"]),
)
```

Only override `interceptors=` wholesale if you accept responsibility for the
ordering.

### Error mapping

Symmetrical with the HTTP exception handlers:

| Exception | gRPC status | HTTP equivalent |
| --- | --- | --- |
| `AuthenticationError` | `UNAUTHENTICATED` | 401 |
| `AuthorizationError` | `PERMISSION_DENIED` | 403 |
| `ConfigurationError` | `FAILED_PRECONDITION` | — |
| `TransportError` | `UNAVAILABLE` | — |
| other `PythonForgeError` | `INVALID_ARGUMENT` | 400 |
| anything else | `INTERNAL` (generic message) | 500 |

Internal exception detail is logged, never returned to the caller.

### Writing servicers

Interceptors accept both `async def` and plain `def` handlers — grpc's own
health servicer is synchronous, and third-party servicers may be too.

## Client

```python
from pythonforge.transport.grpc import context_metadata, context_timeout, create_channel

async with create_channel("service:50051", config.client) as channel:
    stub = MyServiceStub(channel)
    response = await stub.MyRpc(
        request,
        metadata=context_metadata(),        # propagates request id + traceparent
        timeout=context_timeout(5.0),        # clamped to the context deadline
    )
```

`context_timeout` raises `TransportError` if the request's deadline has
already passed, so an expired request never opens a new downstream call.
Use `force_insecure=True` for plaintext local development.

## Stub generation

Stubs are generated at development time and committed; `grpcio-tools` is
never a runtime dependency:

```bash
./scripts/gen_protos.sh
```

Output goes to `src/transport/grpc/generated/`, which is excluded from
ruff, mypy and coverage.

## Hybrid runtime

`ServiceRuntime` runs FastAPI and gRPC in one process. It lives in
`pythonforge.transport` (not under `grpc/`) so an HTTP-only service can use
it without the `grpc` extra.

```python
import uvicorn
from pythonforge.transport import ServiceRuntime

runtime = ServiceRuntime(config, shutdown_timeout=30.0)
runtime.add_uvicorn_server(uvicorn.Server(uvicorn.Config(app, ...)))
runtime.add_grpc_server(grpc_server)
await runtime.serve_forever()   # returns on SIGINT/SIGTERM
```

- **Atomic start** — if any transport fails to come up, those already
  started are torn down before the `LifecycleError` propagates.
- **Graceful stop** — transports stop in reverse order, in-flight work
  drains, and a slow or failing transport can't block the rest of the
  shutdown (both are bounded by `shutdown_timeout` and logged).
- `serve_forever(handle_signals=False)` skips signal handlers; `async with
  runtime:` starts and stops around a block.

`qpython new hybrid <name>` generates a working example of all of this.
