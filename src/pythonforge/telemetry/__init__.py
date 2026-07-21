"""Optional OpenTelemetry integration for FastAPI and HTTPX.

Unlike the general "missing extra" rule (which raises an actionable error),
telemetry must never break the app: if ``trace.enabled`` is ``False`` *or*
the ``telemetry`` extra isn't installed, :func:`configure_telemetry` returns a
no-op provider (logging a single warning in the latter case) instead of
raising. See the observability spec's "OpenTelemetry opcional" requirement.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol

from ..config import TraceConfig
from ..logger import get_logger

logger = get_logger(f"{__name__.rsplit('.', 1)[0]}.telemetry")


class Span(Protocol):
    def __enter__(self) -> Span: ...
    def __exit__(self, *exc_info: object) -> None: ...
    def set_attribute(self, key: str, value: Any) -> None: ...


class Tracer(Protocol):
    def start_as_current_span(self, name: str) -> AbstractContextManager[Span]: ...


class TelemetryProvider(Protocol):
    enabled: bool
    tracer: Tracer

    def instrument_fastapi(self, app: Any) -> None: ...
    def instrument_httpx(self) -> None: ...
    def shutdown(self) -> None: ...


class _NoOpSpan:
    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        return None


class _NoOpTracer:
    def start_as_current_span(self, name: str) -> _NoOpSpan:
        return _NoOpSpan()


class NoOpTelemetryProvider:
    enabled = False
    tracer: Tracer = _NoOpTracer()

    def instrument_fastapi(self, app: Any) -> None:
        return None

    def instrument_httpx(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class _OTelTelemetryProvider:
    enabled = True

    def __init__(self, tracer: Any, provider: Any) -> None:
        self.tracer = tracer
        self._provider = provider

    def instrument_fastapi(self, app: Any) -> None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)

    def instrument_httpx(self) -> None:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

    def shutdown(self) -> None:
        self._provider.shutdown()


def configure_telemetry(config: TraceConfig) -> TelemetryProvider:
    if not config.enabled:
        return NoOpTelemetryProvider()

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        logger.warning(
            "trace.enabled is true but the 'telemetry' extra is not installed; falling back "
            "to a no-op tracer. Install pythonforge[telemetry] to enable OpenTelemetry."
        )
        return NoOpTelemetryProvider()

    exporter: Any = ConsoleSpanExporter()
    if config.exporter == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        except ImportError:
            logger.warning(
                "trace.exporter is 'otlp' but no OTLP exporter package is installed; "
                "falling back to the console exporter."
            )
        else:
            exporter = (
                OTLPSpanExporter(endpoint=config.otlp_endpoint)
                if config.otlp_endpoint
                else OTLPSpanExporter()
            )

    provider = TracerProvider(resource=Resource.create({"service.name": config.service_name}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return _OTelTelemetryProvider(trace.get_tracer(config.service_name), provider)


__all__ = [
    "NoOpTelemetryProvider",
    "Span",
    "TelemetryProvider",
    "Tracer",
    "configure_telemetry",
]
