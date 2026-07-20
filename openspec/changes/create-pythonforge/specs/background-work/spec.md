## ADDED Requirements

### Requirement: Jobs programables

El módulo tools DEBE registrar jobs de intervalo y cron con identificador único,
timeout opcional y operaciones de inicio, pausa, reanudación y detención.

#### Scenario: Pausar un job

- **WHEN** un job activo se pausa
- **THEN** no inicia nuevas ejecuciones hasta reanudarse
- **AND** su estado puede consultarse de forma segura

### Requirement: Integración con lifespan

Los jobs DEBEN iniciar después de que el servicio esté listo y detenerse durante
el lifespan antes de cerrar las dependencias que utilizan.

#### Scenario: Apagado con job activo

- **WHEN** comienza el graceful shutdown durante una ejecución
- **THEN** el runtime espera o cancela según la política y timeout configurados
- **AND** no deja tareas huérfanas

### Requirement: Workers con concurrencia acotada

El proyecto DEBE ofrecer una cola asíncrona con límite de concurrencia,
backpressure, manejo explícito de errores y operaciones de start/stop/restart.

#### Scenario: Cola saturada

- **WHEN** se alcanza la capacidad configurada
- **THEN** el productor espera o recibe el resultado de rechazo configurado
- **AND** el runtime no crea tareas sin límite

### Requirement: Aislamiento de fallas

El fallo de una tarea NO DEBE detener silenciosamente otros workers. El error DEBE
registrarse de forma sanitizada y seguir una política explícita de reintento o
dead-letter.

#### Scenario: Tarea fallida

- **WHEN** una tarea lanza una excepción
- **THEN** se aplica la política configurada
- **AND** la capacidad restante continúa disponible

### Requirement: Modo test

El runtime DEBE disponer de un modo de prueba que impida iniciar trabajo en
segundo plano automáticamente y permita ejecutar jobs/workers de forma manual y
determinista.

#### Scenario: Aplicación bajo prueba

- **WHEN** `mode_test` está habilitado y comienza el lifespan
- **THEN** ningún job periódico ni worker consume tareas automáticamente
