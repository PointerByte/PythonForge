# Seguridad y criptografía

*Read this in English: [security.md](security.md)*

Requiere el extra `security` (`pip install "pythonforge[security]"`), que
trae PyJWT y `cryptography`. Los adaptadores KMS necesitan su propio extra
de nube (`aws`, `azure`, `gcp`).

## JWT

Algoritmos soportados: HS256, RS256, PS256, EdDSA.

```yaml
jwt:
  enabled: true
  algorithm: HS256
  # HS256 usa secret_key; los algoritmos asimétricos usan llaves
  # privada/pública (PEM inline, o rutas *_file).
  issuer: my-issuer
  audience: my-api
  access_token_expire_minutes: 60
```

Define el secreto por variable de entorno en vez de en el archivo:
`PYTHONFORGE_JWT__SECRET_KEY=...`

```python
from pythonforge.security import Claims, decode_token, encode_token

token = encode_token(config.jwt, Claims(sub="user-1", scope="widgets:read"))
claims = decode_token(config.jwt, token)   # lanza AuthenticationError si es inválido
```

`Claims` modela los claims registrados (`sub`, `iss`, `aud`, `exp`, `nbf`,
`iat`, `jti`, `scope`) y conserva todo lo demás en `claims.extra`, así los
claims específicos de la aplicación sobreviven el round trip.
`claims.scopes` separa el claim `scope` delimitado por espacios;
`claims.has_scope(...)` verifica uno.

**Diseñado para fallar cerrado:**

- La verificación fija `algorithms=[configurado]`, cerrando el clásico
  ataque de confusión de `alg` — un token firmado con HS256 nunca puede
  validar contra un verificador RS256.
- `exp` es obligatorio; el issuer y la audience se verifican cuando están
  configurados.
- Cada fallo lanza `AuthenticationError("invalid or expired token")`. El
  mensaje es deliberadamente idéntico para tokens expirados, falsificados,
  malformados y con issuer incorrecto: decirle al llamador *por qué* se
  rechazó su token es un oráculo. La causa real queda encadenada para los
  logs.
- `JWTConfig` valida al cargar — `enabled: true` sin material de llave
  utilizable se rechaza antes de la primera petición, no durante ella.

## Autenticación sobre HTTP

```python
from fastapi import Depends
from pythonforge.security import Claims, require_auth

auth = require_auth(config.jwt, scopes=["widgets:read"])

@router.get("/widgets")
async def widgets(claims: Claims = Depends(auth)) -> ...:
    ...
```

- Lee `Authorization: Bearer <token>`, o una cookie cuando se define
  `require_auth(..., cookie_name="session")`.
- Publica los claims en `RequestContext().claims`, para que la lógica de
  negocio lea la identidad a través del contexto compartido en vez de un
  tipo de FastAPI.
- Token ausente/inválido → 401; scope faltante → 403 (ya mapeados al
  envelope de error estándar por `create_app`).
- `optional_auth(...)` permite peticiones anónimas pero igual rechaza un
  token falsificado — "opcional" significa *puede estar ausente*, nunca
  *puede ser inválido*.

Las dependencias son `async` a propósito: FastAPI corre las dependencias
síncronas en un hilo de trabajo, que recibe una *copia* del contexto, así
que los claims publicados ahí nunca llegarían al handler.

## Autenticación sobre gRPC

```python
from pythonforge.transport.grpc.interceptors.auth import JWTAuthInterceptor

server = create_grpc_server(
    config.server.grpc,
    auth=JWTAuthInterceptor(config.jwt, scopes=["widgets:read"]),
)
```

Los mismos tokens, los mismos claims, la misma semántica de fallo que en
HTTP — sólo cambia el portador (metadata `authorization`).
`/grpc.health.v1.Health/Check` está exento por defecto para que los
orquestadores puedan sondear sin credenciales; ajústalo con
`exempt_methods=`.

## Headers de seguridad

`create_app` siempre fija `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` y `Referrer-Policy: no-referrer`. CORS está apagado
salvo que `server.http.cors_origins` no esté vacío.

## Criptografía local

```python
from pythonforge.encrypt.local import decrypt, encrypt, generate_key

key = generate_key()                    # AES-256 por defecto
payload = encrypt(key, b"secret")       # nonce || ciphertext || tag
assert decrypt(key, payload) == b"secret"
```

| Área | Funciones |
| --- | --- |
| Simétrica | `generate_key`, `encrypt`, `decrypt` (AES-GCM) |
| Hashing | `sha256`, `hmac_sha256`, `verify_hmac_sha256`, `blake3` |
| RSA | `generate_rsa_key`, `rsa_encrypt`/`rsa_decrypt` (OAEP), `rsa_sign`/`rsa_verify` (PSS) |
| Ed25519 | `generate_ed25519_key`, `ed25519_sign`, `ed25519_verify` |
| ECDH | `generate_ec_key`, `ecdh_shared_key` (P-256 + HKDF-SHA256) |

Detalles que importan:

- AES-GCM genera un nonce aleatorio nuevo en cada llamada — reutilizar un
  nonce rompe GCM de forma catastrófica, así que nunca es un parámetro que
  provea el llamador.
- Los fallos de descifrado lanzan un único `CryptographyError` sin importar
  la causa (tag inválido, llave incorrecta, datos corruptos):
  distinguirlos es un oráculo.
- `verify_hmac_sha256` compara en tiempo constante.
- `ecdh_shared_key` pasa la salida cruda de ECDH por HKDF, porque esa
  salida no es uniformemente aleatoria y nunca debe usarse como llave
  directamente.
- Las llaves RSA por debajo de 2048 bits se rechazan.

### `KeyData`

El material de llave se transporta en `KeyData(kind, provider, reference,
public, secret)`. `secret` nunca aparece en `repr()` ni `str()` — estos
objetos terminan en líneas de log y contexto de excepciones con demasiada
facilidad. `key.public_only()` devuelve una copia segura para entregar a
cualquier cosa que sólo verifique o cifre.

## Proveedores KMS

`KMSProvider` es un `typing.Protocol`, así que un doble de prueba es
cualquier objeto con los métodos correctos — sin credenciales, sin red, sin
clase base del proveedor.

```python
from pythonforge.encrypt.kms import InMemoryKMS

kms = InMemoryKMS({"alias/test": b"k" * 32})     # fake determinista
ciphertext = await kms.encrypt("alias/test", b"msg")
```

Los adaptadores reales reciben un cliente inyectable:

```python
from pythonforge.encrypt.kms.aws import AWSKMSProvider

provider = AWSKMSProvider()                 # o AWSKMSProvider(client=fake)
```

- **AWS** (extra `aws`) — boto3 es síncrono, así que las llamadas corren en
  un hilo de trabajo en vez de bloquear el event loop.
- **Azure** (extra `azure`) — Key Vault; `client_factory` es inyectable.
- **GCP** (extra `gcp`) — Cloud KMS. No tiene RPC de verificación, así que
  `verify` obtiene la llave pública y verifica la firma localmente.

Todos traducen los errores del proveedor a `ProviderError`, para que los
llamadores nunca tengan que atrapar tipos de excepción de
boto3/azure/google.
