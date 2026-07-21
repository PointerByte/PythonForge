# Agent Instructions for PythonForge

## Architecture & Context
- **PythonForge** is a modular library for building services, not a business application. It implements conventions shared by DenoForge and GoForge.
- **Frameworks**: Uses FastAPI (HTTP/ASGI) and `grpc.aio` (gRPC).
- **Core Principle**: Shared configuration, request context, security, logging, and OpenTelemetry across both HTTP and gRPC transports.
- **Context Management**: Uses a custom `RequestContext` stored in `contextvars`. Both FastAPI and gRPC adapters translate transport-specific metadata into this common context.
- **Layout**: `src/` layout for the `pythonforge` package.

## Key Modules & Ownership
- `config/`: Pydantic Settings, YAML/JSON/Env loading.
- `transport/`: 
    - `http/`: FastAPI factory (`create_app`), HTTPX client.
    - `grpc/`: Server, channels, interceptors.
- `logger/`: Structured logging, sanitization, adapters.
- `telemetry/`: Traces, metrics, OTel propagation.
- `security/`: JWT, cookies, headers, transport integration.
- `encrypt/`: Local (AES, RSA, etc.) and KMS (AWS, Azure, GCP) via extras.
- `tools/`: Jobs, workers, test mode.
- `cli/`: `qpython` utility for scaffolding.

## Development & Execution
- **Environment**: Always execute installations and run tasks inside a `.venv`.
- **Extras**: The base installation is lightweight. Install specific capabilities via extras:
    - `pythonforge[grpc]`
    - `pythonforge[telemetry]`
    - `pythonforge[aws|azure|gcp]`
    - `pythonforge[cli]`
    - `pythonforge[dev]` (includes pytest, coverage, mypy, lint, etc.)
- **Commands**:
    - Follow the sequence: `lint -> typecheck -> test` for verification.
    - Use `pip install -e .[dev]` for local development.
- **Testing**:
    - Unit tests must be network-free and mock external dependencies (KMS, DBs).
    - Integration tests use ephemeral ports for gRPC and HTTPX for FastAPI.
    - Contract tests ensure context/auth/logging parity between HTTP and gRPC.

## Rules & Constraints
- **Secrets**: Never log or expose secrets (tokens, cookies, keys). Use Pydantic's `SecretStr` where applicable.
- **Error Handling**: Translate external errors to internal public exceptions; preserve internal cause for logs but redact sensitive data.
- **Shutdown**: Ensure graceful shutdown (draining requests, closing jobs/telemetry/sockets) with configurable timeouts.
- **Code Style**: Follow idiomatic Python 3.12+ (asyncio, type hints).
- **Protobufs**: Stubs are generated with `grpcio-tools` during development; do not include `grpcio-tools` in the runtime package.
