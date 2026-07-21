from fastapi import FastAPI, Request, Response
from contextvars import ContextVar
from typing import Callable, Any
from .context import RequestContext
import time
import uuid

# Context variable for the request context object
request_context_var: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())

async def context_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    """
    Middleware to populate the RequestContext from request headers and other metadata.
    """
    # Example: Extract request_id from header or generate one
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    
    # Initialize context
    ctx = RequestContext()
    ctx.request_id = request_id
    request_context_var.set(ctx)
    
    # Example: Extract Traceparent
    traceparent = request.headers.get("traceparent")
    if traceparent:
        try:
            from ..context import TraceContext
            ctx.trace_context = TraceContext.from_traceparent(traceparent)
        except ValueError:
            pass

    # Example: Set deadline
    deadline_str = request.headers.get("X-Deadline")
    if deadline_str:
        try:
            ctx.deadline = float(deadline_str)
        except ValueError:
            pass

    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        # Log duration (placeholder for actual logging)
        duration = time.perf_counter() - start_time
        # print(f"Request {request_id} took {duration:.4f}s")

def create_app(config_data: Any) -> FastAPI:
    """
    Factory to create the FastAPI application with standard middlewares.
    """
    app = FastAPI(title=config_data.app.name, version=config_data.app.version)
    
    app.middleware("http")(context_middleware)
    
    # Add other middlewares here (Logging, Auth, etc.)
    
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/v1/hello")
    async def hello():
        return {"message": "Hello from PythonForge", "request_id": request_context_var.get().request_id}

    return app
