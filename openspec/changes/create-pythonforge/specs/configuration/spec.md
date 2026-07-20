## ADDED Requirements

### Requirement: Configuración tipada

El proyecto DEBE modelar con Pydantic Settings las secciones de aplicación,
servidores HTTP/gRPC, clientes, logger, trazas, JWT, cifrado, jobs y workers.

#### Scenario: Configuración válida

- **WHEN** las fuentes contienen valores compatibles con los modelos
- **THEN** el consumidor recibe settings tipados y normalizados

### Requirement: Precedencia determinista

La precedencia DEBE ser defaults, archivo `application`, archivos declarados en
`env.files`, variables de entorno y overrides explícitos del constructor, en ese
orden de menor a mayor prioridad.

#### Scenario: Override por entorno

- **WHEN** una clave existe en YAML y en una variable de entorno
- **THEN** prevalece el valor de la variable de entorno

### Requirement: Descubrimiento de archivo de aplicación

El loader DEBE aceptar una ruta explícita o buscar `application.yaml`,
`application.yml` y `application.json` en el directorio de configuración
resuelto. Para proyectos nuevos, YAML DEBE ser el formato generado por defecto.

#### Scenario: Archivo YAML presente

- **WHEN** `application.yaml` existe en el directorio resuelto
- **THEN** se carga antes de aplicar env files, entorno y overrides

### Requirement: Variables anidadas

Las variables de entorno DEBEN mapear settings anidados con doble guion bajo y
normalización documentada, por ejemplo `SERVER__GRPC__PORT`.

#### Scenario: Configurar un puerto gRPC

- **WHEN** `SERVER__GRPC__PORT=50051` está definido
- **THEN** `settings.server.grpc.port` vale `50051`

### Requirement: Validación antes del inicio

Los valores incompatibles, puertos inválidos, archivos faltantes requeridos y
combinaciones TLS/JWT ambiguas DEBEN fallar antes de abrir sockets o iniciar jobs.

#### Scenario: Configuración TLS incompleta

- **WHEN** TLS está habilitado sin certificado o llave requeridos
- **THEN** el inicio falla con un error de configuración que identifica el campo

### Requirement: Protección de secretos

Secrets, tokens y material privado DEBEN usar representaciones que oculten su
valor en `repr`, serialización diagnóstica, validaciones y logs.

#### Scenario: Error de validación con secreto

- **WHEN** una configuración que contiene un secreto produce un error
- **THEN** el mensaje no contiene el valor original ni una parte recuperable

### Requirement: Settings inyectables

Cada factory DEBE aceptar una instancia de settings y NO DEBE exigir un singleton
global. La carga implícita sólo podrá existir como conveniencia documentada.

#### Scenario: Dos aplicaciones en una prueba

- **WHEN** una prueba crea dos aplicaciones con settings diferentes
- **THEN** cada aplicación conserva su configuración sin contaminación cruzada
