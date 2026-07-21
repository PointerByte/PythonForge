from __future__ import annotations

import builtins

import pytest

from pythonforge.config import TraceConfig
from pythonforge.telemetry import NoOpTelemetryProvider, configure_telemetry


def test_disabled_returns_noop_provider() -> None:
    provider = configure_telemetry(TraceConfig(enabled=False))
    assert isinstance(provider, NoOpTelemetryProvider)
    assert provider.enabled is False


def test_noop_span_is_a_no_op_context_manager() -> None:
    provider = configure_telemetry(TraceConfig(enabled=False))
    with provider.tracer.start_as_current_span("op") as span:
        span.set_attribute("a", 1)


def test_noop_instrument_and_shutdown_are_safe() -> None:
    provider = configure_telemetry(TraceConfig(enabled=False))
    provider.instrument_fastapi(object())
    provider.instrument_httpx()
    provider.shutdown()


def test_enabled_with_extra_installed_returns_working_tracer() -> None:
    provider = configure_telemetry(TraceConfig(enabled=True, exporter="console"))
    assert provider.enabled is True
    with provider.tracer.start_as_current_span("op"):
        pass
    provider.shutdown()


def test_otlp_exporter_without_package_falls_back_to_console() -> None:
    provider = configure_telemetry(TraceConfig(enabled=True, exporter="otlp"))
    assert provider.enabled is True
    provider.shutdown()


def test_missing_telemetry_extra_falls_back_to_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "opentelemetry":
            raise ImportError("simulated missing extra")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    provider = configure_telemetry(TraceConfig(enabled=True))
    assert isinstance(provider, NoOpTelemetryProvider)
