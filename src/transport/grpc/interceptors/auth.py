"""Bearer-token authentication for gRPC, mirroring the FastAPI dependency.

Same tokens, same claims, same failure semantics as
``pythonforge.security.http.require_auth`` -- only the carrier differs
(``authorization`` metadata instead of a header).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from ....config import JWTConfig
from ....context import RequestContext
from ....errors import AuthenticationError, AuthorizationError
from .base import HandlerWrappingInterceptor

BEARER_PREFIX = "bearer "


class JWTAuthInterceptor(HandlerWrappingInterceptor):
    """Rejects RPCs without a valid token and publishes claims to the context.

    ``exempt_methods`` holds fully-qualified method names that skip auth --
    health checking and reflection typically belong there. Everything else
    is fail-closed: unknown methods require a token.
    """

    def __init__(
        self,
        config: JWTConfig,
        *,
        scopes: Sequence[str] = (),
        exempt_methods: Sequence[str] = ("/grpc.health.v1.Health/Check",),
    ) -> None:
        self._config = config
        self._scopes = tuple(scopes)
        self._exempt = frozenset(exempt_methods)

    def _authenticate(self, context: Any, method: str) -> None:
        if method in self._exempt:
            return

        from ....security.jwt import decode_token

        token = None
        for entry in context.invocation_metadata() or ():
            if entry.key.lower() == "authorization" and entry.value.lower().startswith(
                BEARER_PREFIX
            ):
                token = entry.value[len(BEARER_PREFIX) :].strip()
                break

        if not token:
            raise AuthenticationError("missing bearer token")

        claims = decode_token(self._config, token)

        missing = [scope for scope in self._scopes if not claims.has_scope(scope)]
        if missing:
            raise AuthorizationError(f"missing required scope: {', '.join(missing)}")

        RequestContext().claims = claims.model_dump(mode="json")

    async def wrap_unary(self, behavior: Any, request: Any, context: Any, method: str) -> Any:
        self._authenticate(context, method)
        return await behavior(request, context)

    async def wrap_stream(
        self, behavior: Any, request: Any, context: Any, method: str
    ) -> AsyncIterator[Any]:
        self._authenticate(context, method)
        async for response in behavior(request, context):
            yield response
