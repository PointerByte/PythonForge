# Security and cryptography

*Lee esto en español: [security.es.md](security.es.md)*

Requires the `security` extra (`pip install "pythonforge[security]"`), which
brings in PyJWT and `cryptography`. KMS adapters need their own cloud extra
(`aws`, `azure`, `gcp`).

## JWT

Supported algorithms: HS256, RS256, PS256, EdDSA.

```yaml
jwt:
  enabled: true
  algorithm: HS256
  # HS256 uses secret_key; the asymmetric algorithms use private/public keys
  # (inline PEM, or *_file paths).
  issuer: my-issuer
  audience: my-api
  access_token_expire_minutes: 60
```

Set the secret via environment variable rather than in the file:
`PYTHONFORGE_JWT__SECRET_KEY=...`

```python
from pythonforge.security import Claims, decode_token, encode_token

token = encode_token(config.jwt, Claims(sub="user-1", scope="widgets:read"))
claims = decode_token(config.jwt, token)   # raises AuthenticationError if invalid
```

`Claims` models the registered claims (`sub`, `iss`, `aud`, `exp`, `nbf`,
`iat`, `jti`, `scope`) and preserves anything else in `claims.extra`, so
application-specific claims survive a round trip. `claims.scopes` splits the
space-delimited `scope` claim; `claims.has_scope(...)` checks one.

**Fail-closed by design:**

- Verification pins `algorithms=[configured]`, closing the classic `alg`
  confusion attack — an HS256-signed token can never validate against an
  RS256 verifier.
- `exp` is required; issuer and audience are verified when configured.
- Every failure raises `AuthenticationError("invalid or expired token")`.
  The message is deliberately identical for expired, forged, malformed and
  wrong-issuer tokens: telling a caller *why* their token was rejected is
  an oracle. The real cause is chained for logs.
- `JWTConfig` validates at load time — `enabled: true` without usable key
  material is rejected before the first request, not during it.

## Authentication over HTTP

```python
from fastapi import Depends
from pythonforge.security import Claims, require_auth

auth = require_auth(config.jwt, scopes=["widgets:read"])

@router.get("/widgets")
async def widgets(claims: Claims = Depends(auth)) -> ...:
    ...
```

- Reads `Authorization: Bearer <token>`, or a cookie when
  `require_auth(..., cookie_name="session")` is set.
- Publishes claims to `RequestContext().claims`, so business logic reads
  identity through the shared context rather than a FastAPI type.
- Missing/invalid token → 401; missing scope → 403 (already mapped to the
  standard error envelope by `create_app`).
- `optional_auth(...)` allows anonymous requests but still rejects a forged
  token — "optional" means *may be absent*, never *may be invalid*.

The dependencies are `async` on purpose: FastAPI runs sync dependencies in a
worker thread, which gets a *copy* of the context, so claims published there
would never reach the handler.

## Authentication over gRPC

```python
from pythonforge.transport.grpc.interceptors.auth import JWTAuthInterceptor

server = create_grpc_server(
    config.server.grpc,
    auth=JWTAuthInterceptor(config.jwt, scopes=["widgets:read"]),
)
```

Same tokens, same claims, same failure semantics as HTTP — only the carrier
differs (`authorization` metadata). `/grpc.health.v1.Health/Check` is exempt
by default so orchestrators can probe without credentials; override with
`exempt_methods=`.

## Security headers

`create_app` always sets `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`. CORS is off
unless `server.http.cors_origins` is non-empty.

## Local cryptography

```python
from pythonforge.encrypt.local import decrypt, encrypt, generate_key

key = generate_key()                    # AES-256 by default
payload = encrypt(key, b"secret")       # nonce || ciphertext || tag
assert decrypt(key, payload) == b"secret"
```

| Area | Functions |
| --- | --- |
| Symmetric | `generate_key`, `encrypt`, `decrypt` (AES-GCM) |
| Hashing | `sha256`, `hmac_sha256`, `verify_hmac_sha256`, `blake3` |
| RSA | `generate_rsa_key`, `rsa_encrypt`/`rsa_decrypt` (OAEP), `rsa_sign`/`rsa_verify` (PSS) |
| Ed25519 | `generate_ed25519_key`, `ed25519_sign`, `ed25519_verify` |
| ECDH | `generate_ec_key`, `ecdh_shared_key` (P-256 + HKDF-SHA256) |

Notes that matter:

- AES-GCM generates a fresh random nonce per call — nonce reuse breaks GCM
  catastrophically, so it is never a caller-supplied parameter.
- Decryption failures raise a single `CryptographyError` regardless of
  cause (bad tag, wrong key, corrupt data): distinguishing them is an
  oracle.
- `verify_hmac_sha256` compares in constant time.
- `ecdh_shared_key` runs the raw ECDH output through HKDF, because raw ECDH
  output is not uniformly random and must never be used as a key directly.
- RSA keys below 2048 bits are rejected.

### `KeyData`

Key material is carried in `KeyData(kind, provider, reference, public,
secret)`. `secret` never appears in `repr()` or `str()` — these objects end
up in log lines and exception context far too easily. `key.public_only()`
returns a copy safe to hand to anything that only verifies or encrypts.

## KMS providers

`KMSProvider` is a `typing.Protocol`, so a test double is any object with
the right methods — no credentials, no network, no provider base class.

```python
from pythonforge.encrypt.kms import InMemoryKMS

kms = InMemoryKMS({"alias/test": b"k" * 32})     # deterministic fake
ciphertext = await kms.encrypt("alias/test", b"msg")
```

Real adapters take an injectable client:

```python
from pythonforge.encrypt.kms.aws import AWSKMSProvider

provider = AWSKMSProvider()                 # or AWSKMSProvider(client=fake)
```

- **AWS** (`aws` extra) — boto3 is synchronous, so calls run in a worker
  thread rather than blocking the event loop.
- **Azure** (`azure` extra) — Key Vault; `client_factory` is injectable.
- **GCP** (`gcp` extra) — Cloud KMS. It has no verify RPC, so `verify`
  fetches the public key and checks the signature locally.

All of them translate provider errors into `ProviderError`, so callers never
catch boto3/azure/google exception types.
