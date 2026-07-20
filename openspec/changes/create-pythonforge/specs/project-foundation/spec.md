## ADDED Requirements

### Requirement: Paquete Python distribuible

El proyecto DEBE producir un paquete `pythonforge` instalable desde wheel y
sdist, con layout `src/`, metadata completa, licencia Apache-2.0 y compatibilidad
declarada con Python 3.12 o superior.

#### Scenario: Instalación desde wheel

- **WHEN** se construye el wheel y se instala en un entorno virtual limpio
- **THEN** `import pythonforge` funciona sin acceder a red ni requerir extras
- **AND** la versión importada coincide con la metadata del artefacto

### Requirement: API modular

El paquete DEBE exponer los módulos `config`, `transport`, `logger`, `telemetry`,
`security`, `encrypt` y `tools` de forma independiente, además de una API raíz
que no produzca colisiones entre tipos con nombres similares.

#### Scenario: Uso de un módulo aislado

- **WHEN** un consumidor importa únicamente `pythonforge.encrypt`
- **THEN** no se importan FastAPI, grpcio ni SDKs cloud que no sean necesarios

### Requirement: Dependencias opcionales por extras

El proyecto DEBE separar como extras las capacidades gRPC, telemetría, AWS,
Azure, GCP, CLI y desarrollo. La instalación base NO DEBE instalar SDKs cloud.

#### Scenario: Falta un extra opcional

- **WHEN** se invoca una capacidad cuyo extra no está instalado
- **THEN** se genera un error accionable que nombra el extra requerido
- **AND** el resto del paquete permanece utilizable

### Requirement: APIs asíncronas y tipadas

Las operaciones de I/O DEBEN ofrecer APIs `async` y tipos públicos verificables
por mypy. Los protocolos de repositorio, transporte, sink y proveedor DEBEN poder
implementarse mediante dobles de prueba sin heredar de clases concretas.

#### Scenario: Sustitución por un doble

- **WHEN** una prueba inyecta un objeto que satisface el protocolo público
- **THEN** el consumidor funciona sin depender de la implementación productiva

### Requirement: Errores públicos estables

El paquete DEBE definir una jerarquía de excepciones propia para configuración,
transporte, autenticación, criptografía, proveedor y ciclo de vida, preservando
la causa interna sin exponer datos sensibles en el mensaje público.

#### Scenario: Falla de una dependencia

- **WHEN** una dependencia externa produce un error
- **THEN** PythonForge lo traduce a la excepción pública correspondiente
- **AND** conserva la causa para diagnóstico seguro
