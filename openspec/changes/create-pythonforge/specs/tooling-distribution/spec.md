## ADDED Requirements

### Requirement: CLI de scaffolding

El extra `cli` DEBE instalar `qpython` con comandos `new fastapi`, `new grpc` y
`new hybrid`, utilizables de forma interactiva y no interactiva.

#### Scenario: Crear scaffold híbrido

- **WHEN** se ejecuta `qpython new hybrid` con nombre, paquete y directorio válidos
- **THEN** se crea un proyecto FastAPI+gRPC ejecutable con configuración YAML
- **AND** no se sobrescribe un directorio existente

### Requirement: Scaffolds reproducibles

Cada scaffold DEBE generar `pyproject.toml`, paquete bajo `src/`, tests,
`application.yaml`, `.gitignore`, README y los protos/stubs requeridos para gRPC.

#### Scenario: Instalar un scaffold

- **WHEN** el usuario crea `.venv` e instala el scaffold
- **THEN** sus tests y entry point funcionan con los comandos documentados

### Requirement: Utilidad de certificados

El proyecto DEBE ofrecer una CLI para generar y leer llaves/certificados PEM,
incluyendo material adecuado para TLS, mTLS y algoritmos JWT soportados, sin
imprimir secretos por defecto.

#### Scenario: Generar un certificado mTLS

- **WHEN** se solicitan CA, certificado y llave cliente
- **THEN** los archivos se crean con permisos restrictivos cuando el SO lo permite
- **AND** la salida no muestra el contenido de la llave privada

### Requirement: Toolchain dentro de entorno virtual

La documentación y los comandos del proyecto DEBEN crear y activar `.venv` antes
de instalar dependencias o herramientas Python. No se documentarán instalaciones
globales como flujo normal.

#### Scenario: Preparar desarrollo

- **WHEN** un contribuidor sigue el plan desde un checkout limpio
- **THEN** todas las instalaciones quedan contenidas en `.venv`

### Requirement: Puertas de calidad

Antes de publicar, el proyecto DEBE aprobar formato y lint con Ruff, tipado con
mypy, pytest con al menos 85 % de cobertura, Bandit y auditoría de dependencias.

#### Scenario: Falla una puerta

- **WHEN** cualquiera de las comprobaciones termina con error
- **THEN** el pipeline bloquea la construcción/publicación de release

### Requirement: Artefactos de distribución

El release DEBE generar wheel y sdist desde un árbol limpio, validar ambos con
Twine e instalar el wheel en un entorno virtual nuevo antes de publicar.

#### Scenario: Artefacto inconsistente

- **WHEN** el wheel no se instala o su versión difiere del tag previsto
- **THEN** la publicación se detiene antes de subir a PyPI

### Requirement: Publicación segura

CI DEBE usar PyPI Trusted Publishing cuando esté disponible. El flujo manual
DEBE aceptar tokens sólo desde el entorno o configuración local ignorada, nunca
desde archivos versionados ni argumentos persistidos.

#### Scenario: Release aprobado

- **WHEN** TestPyPI, smoke tests y todas las puertas están aprobados
- **THEN** se publica la misma versión y los mismos artefactos en PyPI
- **AND** se crea un tag anotado que apunta al commit publicado

### Requirement: Documentación bilingüe

El paquete DEBE documentar en español e inglés instalación base/extras,
configuración, FastAPI, gRPC, runtime híbrido, seguridad, criptografía, jobs,
workers, CLI, pruebas y release.

#### Scenario: Consumidor gRPC

- **WHEN** un usuario consulta cualquiera de los README principales
- **THEN** encuentra cómo instalar el extra gRPC y ejecutar un ejemplo mínimo
