from __future__ import annotations

import pytest
from pydantic import ValidationError

from pythonforge.config import ClientConfig, LoggerConfig
from pythonforge.config.server_config import ServerGRPCConfig, ServerHTTPConfig


def test_client_config_key_without_cert_is_rejected() -> None:
    with pytest.raises(ValidationError, match="key_file requires cert_file"):
        ClientConfig(key_file="key.pem")


def test_logger_config_rejects_unknown_level() -> None:
    with pytest.raises(ValidationError, match="logger.level"):
        LoggerConfig(level="NOT-A-LEVEL")


def test_logger_config_normalizes_level_case() -> None:
    assert LoggerConfig(level="debug").level == "DEBUG"


def test_server_http_mtls_required_without_ca_file_is_rejected() -> None:
    with pytest.raises(ValidationError, match="mtls_required requires ca_file"):
        ServerHTTPConfig(mtls_required=True)


def test_server_grpc_tls_enabled_without_cert_is_rejected() -> None:
    with pytest.raises(ValidationError, match="tls_enabled requires cert_file"):
        ServerGRPCConfig(tls_enabled=True)


def test_server_grpc_mtls_required_without_ca_file_is_rejected() -> None:
    with pytest.raises(ValidationError, match="mtls_required requires ca_file"):
        ServerGRPCConfig(tls_enabled=True, cert_file="c", key_file="k", mtls_required=True)
