"""JWT, authentication and security headers (requires the ``security`` extra)."""

from .http import extract_bearer_token, optional_auth, require_auth
from .jwt import Claims, decode_token, encode_token

__all__ = [
    "Claims",
    "decode_token",
    "encode_token",
    "extract_bearer_token",
    "optional_auth",
    "require_auth",
]
