from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ...config import FullConfig
from ...context import RequestContext
from ...errors import AuthenticationError, AuthorizationError, PythonForgeError
from ...logger import configure_logging, get_logger
from ...telemetry import TelemetryProvider, configure_telemetry
from .health import ReadinessCheck, build_health_router
from .middleware import RateLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware

StartupHook = Callable[[FastAPI], "Awaitable[None] | None"]


def _error_response(
    status_code: int, message: str, *, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": status_code,
                "message": message,
                "request_id": RequestContext().request_id,
            }
        },
        headers=headers,
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(422, "request validation failed")

    @app.exception_handler(AuthenticationError)
    async def _handle_authentication_error(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        return _error_response(401, str(exc))

    @app.exception_handler(AuthorizationError)
    async def _handle_authorization_error(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        return _error_response(403, str(exc))

    @app.exception_handler(PythonForgeError)
    async def _handle_pythonforge_error(request: Request, exc: PythonForgeError) -> JSONResponse:
        return _error_response(400, str(exc))

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        get_logger("pythonforge.http").exception("unhandled exception")
        return _error_response(500, "internal server error")


def create_app(
    config: FullConfig,
    *,
    routers: list[APIRouter] | None = None,
    readiness_checks: list[ReadinessCheck] | None = None,
    on_startup: list[StartupHook] | None = None,
    on_shutdown: list[StartupHook] | None = None,
) -> FastAPI:
    """Build a FastAPI app from a :class:`FullConfig` instance.

    No global state is required: every value the app needs comes from
    ``config``, so building several apps from different configs in the same
    process (e.g. in tests) never cross-contaminates.
    """
    configure_logging(config.logger)
    telemetry: TelemetryProvider = configure_telemetry(config.trace)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for hook in on_startup or []:
            result = hook(app)
            if result is not None:
                await result
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            for hook in on_shutdown or []:
                result = hook(app)
                if result is not None:
                    await result
            telemetry.shutdown()

    app = FastAPI(title=config.app.name, version=config.app.version, lifespan=lifespan)
    app.state.ready = False
    app.state.config = config
    app.state.telemetry = telemetry

    telemetry.instrument_fastapi(app)

    if config.server.http.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.server.http.cors_origins,
            allow_credentials=config.server.http.cors_allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(SecurityHeadersMiddleware)

    if config.server.http.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=config.server.http.rate_limit_requests,
            window_seconds=config.server.http.rate_limit_window_seconds,
            exempt_paths=frozenset({config.server.http.health_path, config.server.http.ready_path}),
        )

    app.add_middleware(RequestContextMiddleware)

    _register_exception_handlers(app)

    app.include_router(
        build_health_router(
            health_path=config.server.http.health_path,
            ready_path=config.server.http.ready_path,
            readiness_checks=readiness_checks or [],
        )
    )
    for router in routers or []:
        app.include_router(router)

    return app
