## ADDED Requirements

### Requirement: Esquema de log compartido

Los logs DEBEN poder emitir JSON o texto con los campos `level`, `timestamp`,
`trace_id`, `message`, `details`, `process`, `method`, `line` y `latency_ms`,
manteniendo semántica equivalente en FastAPI y gRPC.

#### Scenario: Finalizar una petición

- **WHEN** termina una petición HTTP o un RPC
- **THEN** se emite una entrada con transporte, operación, estado y latencia
- **AND** conserva el mismo esquema en ambos transportes

### Requirement: Sanitización previa a la salida

El logger DEBE redactar de forma case-insensitive Authorization, Cookie y todas
las claves sensibles configuradas, incluyendo valores dentro de estructuras
anidadas, antes de entregar la entrada a formatters, sinks o exportadores.

#### Scenario: Log con credenciales anidadas

- **WHEN** los detalles contienen un password o bearer token a cualquier nivel
- **THEN** todos esos valores llegan redactados al sink

### Requirement: Cuerpos deshabilitados por defecto

Los cuerpos de request, response y mensajes gRPC NO DEBEN capturarse salvo que el
handler los habilite explícitamente para esa operación. Aun habilitados, DEBEN
aplicar límites de tamaño, sanitización y tratamiento seguro de contenido binario.

#### Scenario: Logging normal

- **WHEN** un request transporta un body y no se habilita su captura
- **THEN** el body no se lee, almacena ni incluye en la entrada de log

### Requirement: OpenTelemetry opcional

El extra `telemetry` DEBE integrar trazas y métricas de FastAPI, HTTPX y gRPC,
aceptar exportadores configurables y funcionar como no-op cuando se deshabilita.

#### Scenario: Telemetría deshabilitada

- **WHEN** OpenTelemetry está deshabilitado o el extra no está instalado
- **THEN** los handlers funcionan sin cambios ni errores de importación

### Requirement: Propagación estándar

El proyecto DEBE extraer, validar y propagar `traceparent` y `tracestate` W3C en
HTTP, y su equivalente en metadata gRPC, sin confiar en valores malformados.

#### Scenario: Traceparent inválido

- **WHEN** llega un `traceparent` inválido
- **THEN** se inicia un contexto válido nuevo
- **AND** el valor inválido no se refleja ciegamente en respuestas o downstream

### Requirement: Procesos downstream

El logger DEBE permitir registrar llamadas downstream o pasos internos con
sistema, proceso, método, destino, estado y latencia bajo la traza activa.

#### Scenario: Llamada a otro servicio

- **WHEN** un handler delimita una llamada downstream
- **THEN** el log final incluye el proceso y su resultado sin incluir el secreto

### Requirement: Cierre de proveedores y sinks

Los proveedores OpenTelemetry y sinks con recursos DEBEN vaciar buffers y cerrar
dentro del graceful shutdown, respetando un timeout y sin impedir el cierre total.

#### Scenario: Exportador no responde

- **WHEN** un exportador excede el timeout de cierre
- **THEN** el runtime registra el fallo de forma segura y continúa el apagado
