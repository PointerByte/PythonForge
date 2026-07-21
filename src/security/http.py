"""FastAPI authentication: bearer header or cookie, into the shared context.

The dependency populates ``RequestContext.claims``, so business logic reads
identity through the same API in HTTP and gRPC handlers alike.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from fastapi import Request

from ..config import JWTConfig
from ..context import RequestContext
from ..errors import AuthenticationError, AuthorizationError
from .jwt import Claims, decode_token

BEARER_PREFIX = "bearer "


def extract_bearer_token(request: Request, *, cookie_name: str | None = None) -> str | None:
    """Read a token from the ``Authorization`` header, falling back to a cookie."""
    header = request.headers.get("authorization")
    if header and header.lower().startswith(BEARER_PREFIX):
        return header[len(BEARER_PREFIX) :].strip()
    if cookie_name:
        return request.cookies.get(cookie_name)
    return None


def require_auth(
    config: JWTConfig,
    *,
    scopes: Sequence[str] = (),
    cookie_name: str | None = None,
) -> Callable[[Request], Awaitable[Claims]]:
    """Build a FastAPI dependency enforcing a valid token and optional scopes.

    Usage::

        auth = require_auth(config.jwt, scopes=["widgets:read"])

        @router.get("/widgets")
        async def widgets(claims: Claims = Depends(auth)) -> ...:
            ...

    Raises :class:`AuthenticationError` (401) when the token is missing or
    invalid, and :class:`AuthorizationError` (403) when a scope is missing --
    both already mapped to responses by ``create_app``.
    """

    # Must be async: FastAPI runs sync dependencies in a worker thread, which
    # gets a *copy* of the context, so the claims we publish below would never
    # reach the route handler.
    async def dependency(request: Request) -> Claims:
        token = extract_bearer_token(request, cookie_name=cookie_name)
        if not token:
            raise AuthenticationError("missing bearer token")

        claims = decode_token(config, token)

        missing = [scope for scope in scopes if not claims.has_scope(scope)]
        if missing:
            # Name the requirement, not the token's actual scopes.
            raise AuthorizationError(f"missing required scope: {', '.join(missing)}")

        RequestContext().claims = claims.model_dump(mode="json")
        return claims

    return dependency


def optional_auth(
    config: JWTConfig, *, cookie_name: str | None = None
) -> Callable[[Request], Awaitable[Claims | None]]:
    """Like :func:`require_auth`, but anonymous requests are allowed through.

    An invalid token is still rejected -- "optional" means "may be absent",
    never "may be forged".
    """

    async def dependency(request: Request) -> Claims | None:
        token = extract_bearer_token(request, cookie_name=cookie_name)
        if not token:
            return None
        claims = decode_token(config, token)
        RequestContext().claims = claims.model_dump(mode="json")
        return claims

    return dependency
