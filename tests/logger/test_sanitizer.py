from __future__ import annotations

from pythonforge.logger.sanitizer import REDACTED, redact


def test_redacts_authorization_and_cookie_case_insensitively() -> None:
    data = {"Authorization": "Bearer x", "cookie": "a=b", "COOKIE": "c=d"}
    result = redact(data)
    assert result["Authorization"] == REDACTED
    assert result["cookie"] == REDACTED
    assert result["COOKIE"] == REDACTED


def test_authorization_and_cookie_redacted_even_without_config() -> None:
    result = redact({"authorization": "secret"}, extra_sensitive_keys=())
    assert result["authorization"] == REDACTED


def test_redacts_nested_structures() -> None:
    data = {"user": {"password": "hunter2", "profile": {"api_key": "abc"}}}
    result = redact(data)
    assert result["user"]["password"] == REDACTED
    assert result["user"]["profile"]["api_key"] == REDACTED


def test_redacts_inside_lists_and_tuples() -> None:
    data = {"items": [{"token": "t1"}, {"token": "t2"}], "pair": ({"secret": "s"},)}
    result = redact(data)
    assert result["items"][0]["token"] == REDACTED
    assert result["items"][1]["token"] == REDACTED
    assert result["pair"][0]["secret"] == REDACTED
    assert isinstance(result["pair"], tuple)


def test_extra_sensitive_keys_are_case_insensitive() -> None:
    result = redact({"X-Api-Key": "abc"}, extra_sensitive_keys=["x-api-key"])
    assert result["X-Api-Key"] == REDACTED


def test_non_sensitive_values_pass_through() -> None:
    data = {"path": "/health", "status_code": 200, "nested": {"count": 3}}
    assert redact(data) == data
