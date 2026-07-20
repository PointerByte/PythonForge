## ADDED Requirements

### Requirement: FastAPI es el framework HTTP principal

El proyecto DEBE proporcionar un factory `create_app` que devuelva una instancia
FastAPI configurable, sin estado global obligatorio y compatible con routers,
dependencias, middleware y lifespan nativos de FastAPI.

#### Scenario: Crear un servicio HTTP

- **WHEN** un consumidor crea una aplicación y registra un router
- **THEN** las rutas se sirven mediante FastAPI/ASGI
- **AND** el lifespan inicia y cierra únicamente los recursos de esa instancia

### Requirement: Servidor y cliente gRPC asíncronos

El extra `grpc` DEBE ofrecer servidor y cliente sobre `grpc.aio` para llamadas
unary, client-streaming, server-streaming y bidirectional-streaming.

#### Scenario: Ejecutar RPCs de todos los tipos

- **WHEN** el servidor registra un servicio generado y un cliente llama sus RPCs
- **THEN** cada patrón de llamada entrega mensajes protobuf válidos
- **AND** respeta metadata, deadlines y cancelación

### Requirement: Contexto compartido entre transportes

FastAPI y gRPC DEBEN poblar el mismo modelo `RequestContext` con request ID,
trace context W3C, claims, deadline, atributos y procesos downstream. El contexto
DEBE aislarse entre ejecuciones concurrentes.

#### Scenario: Propagar una identidad de petición

- **WHEN** una petición HTTP o RPC incluye identificadores válidos de trazado
- **THEN** el handler obtiene esos valores mediante la misma API
- **AND** llamadas salientes propagan el contexto sin mezclar otras peticiones

### Requirement: Runtime híbrido

El proyecto DEBE permitir ejecutar FastAPI y gRPC en el mismo proceso, con inicio
atómico y apagado coordinado. Una falla parcial de inicio DEBE cerrar los recursos
ya adquiridos.

#### Scenario: Apagado del servicio híbrido

- **WHEN** el proceso recibe una señal de terminación
- **THEN** ambos transportes dejan de aceptar trabajo nuevo
- **AND** drenan trabajo en curso dentro del timeout configurado
- **AND** cierran jobs, telemetría, clientes y sockets

### Requirement: Salud y disponibilidad

El runtime DEBE exponer health configurable para FastAPI y el protocolo estándar
de gRPC Health. Readiness DEBE reflejar si los recursos obligatorios terminaron
de iniciar; liveness NO DEBE revelar configuración sensible.

#### Scenario: Servicio aún no disponible

- **WHEN** un recurso obligatorio no ha completado su inicialización
- **THEN** readiness responde no disponible en HTTP y gRPC
- **AND** liveness sigue describiendo sólo el estado del proceso

### Requirement: TLS y mTLS

Los servidores y clientes HTTP/gRPC DEBEN soportar TLS y mTLS mediante rutas o
material inyectado, versión mínima configurable y validación de hostname.

#### Scenario: mTLS requerido

- **WHEN** el servidor exige certificado cliente y éste falta o no es confiable
- **THEN** el handshake falla antes de ejecutar el handler

### Requirement: Clientes salientes instrumentables

El proyecto DEBE ofrecer un cliente HTTPX asíncrono y helpers de canal gRPC con
timeouts por defecto, TLS/mTLS, propagación de contexto y hooks de observabilidad.

#### Scenario: Timeout downstream

- **WHEN** una dependencia excede el timeout configurado
- **THEN** la llamada se cancela con un error público de transporte
- **AND** la traza registra el resultado sin incluir credenciales ni cuerpos
