from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pythonforge.cli import build_app
from pythonforge.cli.scaffold import scaffold

runner = CliRunner()


@pytest.fixture
def app():
    return build_app()


# --- Scaffolding -------------------------------------------------------


@pytest.mark.parametrize("flavor", ["fastapi", "grpc", "hybrid"])
def test_scaffold_writes_the_expected_files(tmp_path: Path, flavor: str) -> None:
    created = scaffold(tmp_path / "svc", "my-service", flavor)  # type: ignore[arg-type]
    names = {path.name for path in created}
    assert names == {"application.yaml", "main.py", "README.md"}
    assert all(path.exists() for path in created)


@pytest.mark.parametrize("flavor", ["fastapi", "grpc", "hybrid"])
def test_generated_main_is_valid_python(tmp_path: Path, flavor: str) -> None:
    """A scaffold that doesn't even compile is worse than no scaffold."""
    scaffold(tmp_path / "svc", "my-service", flavor)  # type: ignore[arg-type]
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "py_compile", str(tmp_path / "svc" / "main.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("flavor", ["fastapi", "grpc", "hybrid"])
def test_generated_config_loads(tmp_path: Path, flavor: str) -> None:
    from pythonforge.config import load_config

    scaffold(tmp_path / "svc", "my-service", flavor)  # type: ignore[arg-type]
    config = load_config(config_dir=tmp_path / "svc")
    assert config.app.name == "my-service"
    assert config.logger.format == "json"


def test_generated_yaml_is_the_default_format(tmp_path: Path) -> None:
    created = scaffold(tmp_path / "svc", "svc", "fastapi")
    assert any(path.suffix == ".yaml" for path in created)
    assert not any(path.suffix == ".json" for path in created)


@pytest.mark.parametrize("flavor", ["fastapi", "grpc", "hybrid"])
def test_cli_new_command(app, tmp_path: Path, flavor: str) -> None:
    result = runner.invoke(app, ["new", flavor, "svc", "--dir", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out" / "main.py").exists()
    assert "python3 -m venv" in result.output


def test_cli_refuses_to_overwrite_a_non_empty_directory(app, tmp_path: Path) -> None:
    target = tmp_path / "out"
    target.mkdir()
    (target / "existing.txt").write_text("keep me")

    result = runner.invoke(app, ["new", "fastapi", "svc", "--dir", str(target)])
    assert result.exit_code == 1
    assert (target / "existing.txt").read_text() == "keep me"


def test_cli_scaffold_never_installs_anything(app, tmp_path: Path) -> None:
    """Installation must stay the user's explicit, in-venv decision."""
    result = runner.invoke(app, ["new", "fastapi", "svc", "--dir", str(tmp_path / "out")])
    assert "never installs anything for you" in result.output


def test_cli_version(app) -> None:
    from pythonforge import __version__

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


# --- Certificates ------------------------------------------------------


def test_generate_self_signed_certificate(tmp_path: Path) -> None:
    from pythonforge.cli.certs import generate_self_signed

    written = generate_self_signed(tmp_path / "certs", common_name="example.test")
    assert written["cert"].exists()
    assert written["key"].exists()
    assert written["cert"].read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")


def test_generated_private_key_is_not_world_readable(tmp_path: Path) -> None:
    from pythonforge.cli.certs import generate_self_signed

    written = generate_self_signed(tmp_path / "certs")
    assert written["key"].stat().st_mode & 0o077 == 0


def test_generate_with_ca_emits_a_signing_ca(tmp_path: Path) -> None:
    from pythonforge.cli.certs import generate_self_signed

    written = generate_self_signed(tmp_path / "certs", also_generate_ca=True)
    assert {"cert", "key", "ca_cert", "ca_key"} <= written.keys()
    assert written["ca_cert"].read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")


def test_generated_certificate_is_usable_by_the_tls_config(tmp_path: Path) -> None:
    """The output must satisfy ServerHTTPConfig's TLS validation."""
    from pythonforge.cli.certs import generate_self_signed
    from pythonforge.config import ServerHTTPConfig

    written = generate_self_signed(tmp_path / "certs", also_generate_ca=True)
    config = ServerHTTPConfig(
        tls_enabled=True,
        cert_file=str(written["cert"]),
        key_file=str(written["key"]),
        ca_file=str(written["ca_cert"]),
        mtls_required=True,
    )
    assert config.tls_enabled


def test_invalid_validity_is_rejected(tmp_path: Path) -> None:
    from pythonforge.cli.certs import generate_self_signed
    from pythonforge.errors import CryptographyError

    with pytest.raises(CryptographyError):
        generate_self_signed(tmp_path / "certs", days=0)


def test_cli_certs_command(app, tmp_path: Path) -> None:
    result = runner.invoke(app, ["certs", "--dir", str(tmp_path / "certs"), "--with-ca"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "certs" / "cert.pem").exists()
    assert (tmp_path / "certs" / "ca.pem").exists()
    assert "local development only" in result.output
