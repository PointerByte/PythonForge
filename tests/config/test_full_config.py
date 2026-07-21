from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonforge.config import load_config
from pythonforge.errors import ConfigurationError


def test_defaults(tmp_path: Path) -> None:
    cfg = load_config(config_dir=tmp_path)
    assert cfg.app.name == "PythonForge"
    assert cfg.server.http.port == 8000
    assert cfg.server.grpc.port == 50051


def test_discovers_application_yaml(tmp_path: Path) -> None:
    (tmp_path / "application.yaml").write_text(
        textwrap.dedent(
            """
            app:
              name: FromYaml
            server:
              http:
                port: 9000
              grpc:
                port: 51000
            """
        )
    )
    cfg = load_config(config_dir=tmp_path)
    assert cfg.app.name == "FromYaml"
    assert cfg.server.http.port == 9000
    assert cfg.server.grpc.port == 51000


def test_discovers_application_json_when_no_yaml(tmp_path: Path) -> None:
    (tmp_path / "application.json").write_text('{"app": {"name": "FromJson"}}')
    cfg = load_config(config_dir=tmp_path)
    assert cfg.app.name == "FromJson"


def test_explicit_config_path_beats_discovery(tmp_path: Path) -> None:
    (tmp_path / "application.yaml").write_text("app:\n  name: Discovered\n")
    explicit = tmp_path / "other.yaml"
    explicit.write_text("app:\n  name: Explicit\n")
    cfg = load_config(config_path=explicit, config_dir=tmp_path)
    assert cfg.app.name == "Explicit"


def test_env_var_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "application.yaml").write_text("server:\n  grpc:\n    port: 51000\n")
    monkeypatch.setenv("PYTHONFORGE_SERVER__GRPC__PORT", "55555")
    cfg = load_config(config_dir=tmp_path)
    assert cfg.server.grpc.port == 55555


def test_env_file_overrides_yaml_but_not_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "application.yaml").write_text("app:\n  name: FromYaml\n")
    env_file = tmp_path / ".env"
    env_file.write_text("PYTHONFORGE_APP__NAME=FromEnvFile\n")

    cfg = load_config(config_dir=tmp_path, env_files=str(env_file))
    assert cfg.app.name == "FromEnvFile"

    monkeypatch.setenv("PYTHONFORGE_APP__NAME", "FromEnvVar")
    cfg2 = load_config(config_dir=tmp_path, env_files=str(env_file))
    assert cfg2.app.name == "FromEnvVar"


def test_constructor_override_wins_over_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "application.yaml").write_text("app:\n  name: FromYaml\n")
    monkeypatch.setenv("PYTHONFORGE_APP__NAME", "FromEnvVar")
    cfg = load_config(config_dir=tmp_path, app={"name": "FromOverride"})
    assert cfg.app.name == "FromOverride"


def test_two_loads_do_not_cross_contaminate(tmp_path: Path) -> None:
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "application.yaml").write_text("app:\n  name: ServiceA\n")
    (dir_b / "application.yaml").write_text("app:\n  name: ServiceB\n")

    cfg_a = load_config(config_dir=dir_a)
    cfg_b = load_config(config_dir=dir_b)

    assert cfg_a.app.name == "ServiceA"
    assert cfg_b.app.name == "ServiceB"


def test_secret_hidden_in_repr(tmp_path: Path) -> None:
    cfg = load_config(config_dir=tmp_path, jwt={"secret_key": "super-secret"})
    assert "super-secret" not in repr(cfg.jwt)
    assert "super-secret" not in str(cfg.jwt)
    assert "super-secret" not in repr(cfg)


def test_invalid_tls_config_fails_before_startup(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        load_config(config_dir=tmp_path, server={"http": {"tls_enabled": True}})
    assert "cert_file" in str(exc_info.value)


def test_validation_error_omits_raw_input_value(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        load_config(config_dir=tmp_path, app={"env": "not-a-real-env"})
    assert "not-a-real-env" not in str(exc_info.value)


def test_invalid_port_range_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_config(config_dir=tmp_path, server={"http": {"port": 99999}})


def test_missing_application_file_falls_back_to_defaults(tmp_path: Path) -> None:
    cfg = load_config(config_dir=tmp_path / "does-not-exist")
    assert cfg.app.name == "PythonForge"
