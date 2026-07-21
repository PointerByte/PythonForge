from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from pythonforge.config import LoggerConfig
from pythonforge.context import RequestContext, TraceContext
from pythonforge.logger import configure_logging, get_logger, log_event
from pythonforge.logger.formatter import TextFormatter
from pythonforge.logger.schema import SCHEMA_FIELDS


@pytest.fixture(autouse=True)
def _reset_logger() -> Iterator[None]:
    yield
    logger = logging.getLogger("pythonforge")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)


def test_configure_logging_sets_level() -> None:
    configure_logging(LoggerConfig(level="DEBUG"))
    assert get_logger().level == logging.DEBUG


def test_configure_logging_is_idempotent() -> None:
    configure_logging(LoggerConfig())
    configure_logging(LoggerConfig())
    assert len(get_logger().handlers) == 1


def test_configure_logging_adds_file_handler(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    configure_logging(LoggerConfig(file_path=str(log_file)))
    handlers = get_logger().handlers
    assert len(handlers) == 2
    assert any(isinstance(h, RotatingFileHandler) for h in handlers)

    log_event(get_logger(), logging.INFO, "to file")
    assert log_file.exists()
    assert "to file" in log_file.read_text()


def test_log_event_emits_schema_shaped_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggerConfig(format="json"))
    log_event(
        get_logger(),
        logging.INFO,
        "hello",
        process="http",
        method="GET",
        latency_ms=1.5,
        details={"path": "/x"},
    )
    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert set(SCHEMA_FIELDS) <= payload.keys()
    assert payload["message"] == "hello"
    assert payload["process"] == "http"
    assert payload["method"] == "GET"
    assert payload["latency_ms"] == 1.5
    assert payload["details"] == {"path": "/x"}


def test_context_filter_injects_trace_and_request_id(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggerConfig(format="json"))
    ctx = RequestContext()
    with ctx.bind(request_id="req-1", trace_context=TraceContext(trace_id="a" * 32)):
        log_event(get_logger(), logging.INFO, "in request")
    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert payload["trace_id"] == "a" * 32
    assert payload["request_id"] == "req-1"


def test_sensitive_details_redacted_in_output(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggerConfig(format="json", sensitive_keys=["custom-secret"]))
    log_event(
        get_logger(),
        logging.INFO,
        "with secret",
        details={"password": "hunter2", "custom-secret": "shh"},
    )
    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert payload["details"]["password"] == "***REDACTED***"
    assert payload["details"]["custom-secret"] == "***REDACTED***"


def test_text_formatter_output_is_readable(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggerConfig(format="text"))
    handler = get_logger().handlers[0]
    assert isinstance(handler.formatter, TextFormatter)

    ctx = RequestContext()
    with ctx.bind(trace_context=TraceContext(trace_id="a" * 32)):
        log_event(
            get_logger(),
            logging.INFO,
            "hello there",
            process="http",
            method="GET",
            latency_ms=2.5,
            details={"path": "/x"},
        )
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert "[INFO]" in line
    assert "process=http" in line
    assert "method=GET" in line
    assert f"trace_id={'a' * 32}" in line
    assert "latency_ms=2.50" in line
    assert "hello there" in line
    assert "details=" in line


def test_text_formatter_omits_optional_fields_when_absent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LoggerConfig(format="text"))
    log_event(get_logger(), logging.INFO, "bare message")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert "bare message" in line
    assert "process=" not in line
    assert "details=" not in line
