"""A stable representation for key material, whatever provider holds it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

KeyProvider = Literal["local", "aws", "azure", "gcp"]
KeyKind = Literal["symmetric", "rsa", "ec", "ed25519"]


@dataclass(frozen=True)
class KeyData:
    """Key material plus enough metadata to route operations to a provider.

    ``secret`` (private/symmetric material) is never included in ``repr`` or
    ``str``: these objects end up in log lines and exception context by
    accident far too easily.
    """

    kind: KeyKind
    provider: KeyProvider = "local"
    # Provider-side identifier: a KMS key ARN/URI, or a local alias.
    reference: str | None = None
    public: bytes | None = None
    secret: bytes | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        held = "secret+public" if self.secret and self.public else "secret" if self.secret else "public"
        return (
            f"KeyData(kind={self.kind!r}, provider={self.provider!r}, "
            f"reference={self.reference!r}, material={held})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def has_secret(self) -> bool:
        return self.secret is not None

    def public_only(self) -> KeyData:
        """A copy safe to hand to anything that only needs to verify/encrypt."""
        return KeyData(
            kind=self.kind,
            provider=self.provider,
            reference=self.reference,
            public=self.public,
            secret=None,
        )
