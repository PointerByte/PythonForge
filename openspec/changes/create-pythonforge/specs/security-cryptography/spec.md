## ADDED Requirements

### Requirement: Servicio JWT

El módulo security DEBE crear, verificar y decodificar JWT HS256, RS256, PS256 y
EdDSA, validar el algoritmo esperado y aceptar validadores adicionales de claims.

#### Scenario: Algoritmo no esperado

- **WHEN** un token firmado con otro algoritmo llega al servicio
- **THEN** la verificación falla sin intentar un fallback inseguro

### Requirement: Autenticación FastAPI

El proyecto DEBE ofrecer dependencias/middleware para bearer y cookie JWT en
FastAPI, guardar claims tipados en el contexto común y distinguir autenticación
inválida de autorización insuficiente.

#### Scenario: Bearer inválido

- **WHEN** una ruta protegida recibe un bearer ausente, expirado o inválido
- **THEN** responde HTTP 401 sin ejecutar la lógica protegida

### Requirement: Autenticación gRPC

El proyecto DEBE ofrecer interceptores para RPC unary y streaming que lean
`authorization: Bearer <token>` desde metadata y agreguen claims al contexto.

#### Scenario: Stream sin autorización

- **WHEN** un cliente abre un stream protegido sin bearer válido
- **THEN** el servidor termina con `UNAUTHENTICATED` antes de entregar mensajes

### Requirement: Headers HTTP de seguridad

FastAPI DEBE poder aplicar defaults configurables para HSTS, CSP, Referrer-Policy,
X-Content-Type-Options, X-Frame-Options y Permissions-Policy.

#### Scenario: Respuesta protegida

- **WHEN** el middleware de headers está habilitado
- **THEN** una respuesta incluye las políticas configuradas sin sobrescribir una
  política explícita más restrictiva del consumidor

### Requirement: Repositorio criptográfico local

El backend local DEBE soportar AES-GCM con AAD, HMAC-SHA256, SHA-256, BLAKE3,
RSA-OAEP, acuerdo ECDH con derivación autenticada y firmas Ed25519, RSA-PSS y
RSA PKCS#1 v1.5 SHA-256 usando bibliotecas criptográficas mantenidas.

#### Scenario: Round-trip AES-GCM

- **WHEN** se cifra y descifra un valor con la misma llave y AAD
- **THEN** se recupera exactamente el texto original
- **AND** modificar nonce, ciphertext, tag o AAD hace fallar la autenticación

### Requirement: Modelo estable de llaves

Las operaciones de generación DEBEN devolver `KeyData` con proveedor,
identificador/referencia y llave pública cuando sea exportable. Material privado o
simétrico NO DEBE exponerse para una llave gestionada por KMS.

#### Scenario: Llave cloud

- **WHEN** un proveedor KMS crea o resuelve una llave
- **THEN** el resultado contiene sólo referencias y material público permitido

### Requirement: Proveedores KMS opcionales

AWS KMS, Azure Key Vault y Google Cloud KMS DEBEN implementar protocolos comunes
para encrypt/decrypt, sign/verify y ciclo de vida cuando el proveedor lo soporte.
Sus SDKs DEBEN cargarse de forma perezosa mediante extras separados.

#### Scenario: Probar un proveedor sin nube

- **WHEN** se inyecta una implementación falsa del protocolo KMS
- **THEN** se prueba la lógica del adaptador sin credenciales ni llamadas de red

### Requirement: Manejo seguro de material

La implementación NO DEBE registrar llaves, plaintext, tokens, credenciales ni
firmas sensibles. Las comparaciones de autenticadores DEBEN ser resistentes a
timing cuando aplique, y errores criptográficos DEBEN fallar cerrados.

#### Scenario: Ciphertext manipulado

- **WHEN** el backend detecta un ciphertext inválido
- **THEN** no devuelve plaintext parcial
- **AND** el error público no contiene llave ni contenido sensible
