"""Self-signed certificate generation for local TLS/mTLS development.

Explicitly a development tool: the certificates it produces are unsuitable
for anything but a laptop or a test suite, and the CLI says so when it runs.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from ..errors import CryptographyError
from ..security._optional import require_cryptography


def _crypto() -> tuple[Any, Any, Any, Any]:
    require_cryptography()
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    return x509, hashes, serialization, rsa


def generate_self_signed(
    output_dir: str | Path,
    *,
    common_name: str = "localhost",
    days: int = 365,
    key_size: int = 2048,
    also_generate_ca: bool = False,
) -> dict[str, Path]:
    """Write ``cert.pem``/``key.pem`` (and optionally a CA pair) to ``output_dir``.

    Returns a mapping of role to written path. ``also_generate_ca`` produces
    a separate CA that signs the leaf, which is what mTLS setups need in
    order to have something to put in ``ca_file``.
    """
    x509, hashes, serialization, rsa = _crypto()

    if days < 1:
        raise CryptographyError("certificate validity must be at least one day")

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(tz=datetime.UTC)
    written: dict[str, Path] = {}

    def subject_for(name: str) -> Any:
        return x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, name)])

    def write(path: Path, data: bytes, *, private: bool) -> None:
        path.write_bytes(data)
        # Private keys must not be world-readable, even in a dev tree.
        path.chmod(0o600 if private else 0o644)

    ca_key = None
    ca_certificate = None
    if also_generate_ca:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        ca_certificate = (
            x509.CertificateBuilder()
            .subject_name(subject_for(f"{common_name} dev CA"))
            .issuer_name(subject_for(f"{common_name} dev CA"))
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=days))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(ca_key, hashes.SHA256())
        )
        ca_cert_path = directory / "ca.pem"
        ca_key_path = directory / "ca-key.pem"
        write(ca_cert_path, ca_certificate.public_bytes(serialization.Encoding.PEM), private=False)
        write(
            ca_key_path,
            ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            private=True,
        )
        written["ca_cert"] = ca_cert_path
        written["ca_key"] = ca_key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject_for(common_name))
        .issuer_name(ca_certificate.subject if ca_certificate else subject_for(common_name))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name), x509.DNSName("localhost")]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    )
    certificate = builder.sign(ca_key or key, hashes.SHA256())

    cert_path = directory / "cert.pem"
    key_path = directory / "key.pem"
    write(cert_path, certificate.public_bytes(serialization.Encoding.PEM), private=False)
    write(
        key_path,
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        private=True,
    )
    written["cert"] = cert_path
    written["key"] = key_path

    return written
