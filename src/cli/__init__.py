"""``qpython`` -- the PythonForge scaffolding CLI (requires the ``cli`` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import MissingExtraError


def _require_typer() -> Any:
    try:
        import typer
    except ImportError as exc:
        raise MissingExtraError(extra="cli", feature="The qpython CLI") from exc
    return typer


def build_app() -> Any:
    """Construct the Typer application.

    Built lazily inside a function rather than at import time so that
    ``import pythonforge.cli`` without the extra raises the actionable
    :class:`MissingExtraError` instead of an ImportError traceback.
    """
    typer = _require_typer()

    app = typer.Typer(
        name="qpython",
        help="Scaffolding and helper tools for PythonForge services.",
        no_args_is_help=True,
        add_completion=False,
    )
    new_app = typer.Typer(help="Create a new service.", no_args_is_help=True)
    app.add_typer(new_app, name="new")

    def _create(flavor: str, name: str, directory: Path | None) -> None:
        from .scaffold import scaffold

        destination = directory or Path(name)
        if destination.exists() and any(destination.iterdir()):
            typer.secho(
                f"refusing to scaffold into non-empty directory: {destination}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        created = scaffold(destination, name, flavor)  # type: ignore[arg-type]
        typer.secho(f"Created {flavor} service {name!r} in {destination}", fg=typer.colors.GREEN)
        for path in created:
            typer.echo(f"  {path}")
        typer.echo(
            "\nNext steps (PythonForge never installs anything for you):\n"
            f"  cd {destination}\n"
            "  python3 -m venv .venv\n"
            "  source .venv/bin/activate\n"
            "  python -m pip install --upgrade pip\n"
            "  python -m pip install -e '.[dev]'  # or the packages in README.md\n"
            "  python main.py"
        )

    @new_app.command("fastapi")
    def new_fastapi(
        name: str,
        directory: Path = typer.Option(None, "--dir", help="Target directory."),  # noqa: B008
    ) -> None:
        """Create a FastAPI (HTTP-only) service."""
        _create("fastapi", name, directory)

    @new_app.command("grpc")
    def new_grpc(
        name: str,
        directory: Path = typer.Option(None, "--dir", help="Target directory."),  # noqa: B008
    ) -> None:
        """Create a gRPC-only service."""
        _create("grpc", name, directory)

    @new_app.command("hybrid")
    def new_hybrid(
        name: str,
        directory: Path = typer.Option(None, "--dir", help="Target directory."),  # noqa: B008
    ) -> None:
        """Create a service running FastAPI and gRPC in one process."""
        _create("hybrid", name, directory)

    @app.command("certs")
    def certs(
        directory: Path = typer.Option(Path("certs"), "--dir", help="Output directory."),  # noqa: B008
        common_name: str = typer.Option("localhost", "--cn", help="Certificate common name."),
        days: int = typer.Option(365, help="Validity in days."),
        with_ca: bool = typer.Option(False, "--with-ca", help="Also emit a signing CA (for mTLS)."),
    ) -> None:
        """Generate self-signed certificates for local TLS/mTLS development."""
        from .certs import generate_self_signed

        written = generate_self_signed(
            directory, common_name=common_name, days=days, also_generate_ca=with_ca
        )
        typer.secho("Generated development certificates:", fg=typer.colors.GREEN)
        for role, path in written.items():
            typer.echo(f"  {role}: {path}")
        typer.secho(
            "\nThese are self-signed and for local development only -- never deploy them.",
            fg=typer.colors.YELLOW,
        )

    @app.command("version")
    def version() -> None:
        """Print the installed PythonForge version."""
        from .. import __version__

        typer.echo(__version__)

    return app


def main() -> None:
    """Entry point for the ``qpython`` console script."""
    build_app()()


__all__ = ["build_app", "main"]
