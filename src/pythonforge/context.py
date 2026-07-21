import contextvars
from typing import Dict, Any, Optional

# Context variables for request-scoped data
request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
trace_context: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar("trace_context", default=None)
claims: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("claims", default=None)
deadline: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar("deadline", default=None)
downstream_processes: contextvars.ContextVar[list[str]] = contextvars.ContextVar("downstream_processes", default=[])

class TraceContext:
    """
    W3C Trace Context compatible trace information.
    """
    def __init__(self, trace_id: str, parent_id: Optional[str] = None, trace_flags: str = "00", tracestate: Optional[Dict[str, str]] = None):
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.trace_flags = trace_flags
        self.tracestate = tracestate or {}

    def to_traceparent(self) -> str:
        # format: version-traceid-parentid-texport
        # version is 00
        parent_id = self.parent_id or "0000000000000000"
        return f"00-{self.trace_id}-{parent_id}-{self.trace_flags}"

    @classmethod
    def from_traceparent(cls, traceparent: str) -> 'TraceContext':
        parts = traceparent.split("-")
        if len(parts) < 4:
            raise ValueError("Invalid traceparent format")
        return cls(trace_id=parts[1], parent_id=parts[2], trace_flags=parts[3])

class RequestContext:
    """
    Context object representing the current request state.
    Values are retrieved from the underlying contextvars.
    """
    @property
    def request_id(self) -> Optional[str]:
        return request_id.get()

    @request_id.setter
    def request_id(self, value: Optional[str]):
        request_id.set(value)

    @property
    def trace_context(self) -> Optional[TraceContext]:
        return trace_context.get()

    @trace_context.setter
    def trace_context(self, value: Optional[TraceContext]):
        trace_context.set(value)

    @property
    def claims(self) -> Optional[Dict[str, Any]]:
        return claims.get()

    @claims.setter
    def claims(self, value: Optional[Dict[str, Any]]):
        claims.set(value)

    @property
    def deadline(self) -> Optional[float]:
        return deadline.get()

    @deadline.setter
    def deadline(self, value: Optional[float]):
        deadline.set(value)

    @property
    def downstream_processes(self) -> list[str]:
        return downstream_processes.get()

    @downstream_processes.setter
    def downstream_processes(self, value: list[str]):
        downstream_processes.set(value)
