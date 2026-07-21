from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

ReadinessCheck = Callable[[], "Awaitable[bool] | bool"]


def build_health_router(
    *,
    health_path: str,
    ready_path: str,
    readiness_checks: list[ReadinessCheck],
) -> APIRouter:
    """Liveness never reveals configuration; readiness reflects startup + checks."""
    router = APIRouter()

    @router.get(health_path, include_in_schema=False)
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(ready_path, include_in_schema=False)
    async def readiness(request: Request, response: Response) -> dict[str, str]:
        if not getattr(request.app.state, "ready", False):
            response.status_code = HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "starting"}
        for check in readiness_checks:
            result = check()
            if isinstance(result, Awaitable):
                result = await result
            if not result:
                response.status_code = HTTP_503_SERVICE_UNAVAILABLE
                return {"status": "not_ready"}
        return {"status": "ready"}

    return router
