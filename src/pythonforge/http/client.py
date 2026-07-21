import httpx
import asyncio
from typing import Any, Dict, Optional
from ..context import RequestContext, TraceContext
from contextvars import request_context_var

class ForgeClient:
    """
    HTTPX-based async client with automatic context and trace propagation.
    """
    def __init__(self, base_url: str, timeout: float = 30.0, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        ctx = request_context_var.get()
        headers = kwargs.pop("headers", {})
        
        # Propagate request_id
        if ctx.request_id:
            headers["X-Request-Id"] = ctx.request_id
        
        # Propagate traceparent
        if ctx.trace_context:
            headers["traceparent"] = ctx.trace_context.to_traceparent()
        
        # Propagate deadlines
        if ctx.deadline:
            headers["X-Deadline"] = str(ctx.deadline)

        # Implement retries
        last_exception = None
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.request(method, path, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code >= 500:
                    continue
                raise e
            except Exception as e:
                last_exception = e
                if attempt == self.retries:
                    raise e
                await asyncio.sleep(2 ** attempt)
        
        raise last_exception

    async def close(self):
        await self.client.aclose()
