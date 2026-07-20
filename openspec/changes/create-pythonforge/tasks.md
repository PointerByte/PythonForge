# Tareas: crear PythonForge

## 1. Fundación

- [ ] 1.1 Crear `pyproject.toml`, layout `src/`, metadata Apache-2.0 y API raíz.
- [ ] 1.2 Declarar Python >=3.12, dependencias base y extras sin duplicidades.
- [ ] 1.3 Ignorar `.venv`, artefactos de build y caches; crear `.venv` antes de instalar cualquier dependencia y documentar su activación.
- [ ] 1.4 Configurar Ruff, mypy, pytest, cobertura, Bandit y pip-audit.

## 2. Configuración y contexto

- [ ] 2.1 Implementar settings tipados y precedencia YAML/JSON, env files, entorno y overrides.
- [ ] 2.2 Implementar `RequestContext` con `contextvars`, request ID y W3C Trace Context.
- [ ] 2.3 Probar validación, secretos, precedencia y aislamiento concurrente.

## 3. FastAPI

- [ ] 3.1 Implementar `create_app` con lifespan, health configurable y apagado ordenado.
- [ ] 3.2 Agregar middleware de contexto, errores, seguridad, logging, rate limit y CORS.
- [ ] 3.3 Implementar cliente HTTPX async con timeouts, TLS/mTLS y trazas.
- [ ] 3.4 Crear ejemplo y pruebas de integración HTTP.

## 4. gRPC

- [ ] 4.1 Definir protos de ejemplo/health y generación reproducible de stubs.
- [ ] 4.2 Implementar servidor y cliente `grpc.aio`, TLS/mTLS y graceful shutdown.
- [ ] 4.3 Agregar interceptores unary/stream para contexto, JWT, logging y tracing.
- [ ] 4.4 Probar llamadas unary, client/server/bidi streaming, metadata, deadlines y cancelación.
- [ ] 4.5 Implementar y probar el runtime híbrido FastAPI + gRPC.

## 5. Observabilidad

- [ ] 5.1 Implementar niveles, formatos JSON/texto, sinks y rotación.
- [ ] 5.2 Implementar sanitización de headers, atributos y estructuras anidadas.
- [ ] 5.3 Integrar OpenTelemetry para FastAPI, HTTPX y gRPC, con exportadores opcionales.
- [ ] 5.4 Verificar paridad del esquema de logs entre HTTP y gRPC.

## 6. Seguridad y criptografía

- [ ] 6.1 Implementar JWT HS256, RS256, PS256 y EdDSA con validadores y claims tipados.
- [ ] 6.2 Agregar bearer/cookie para FastAPI e interceptores bearer para gRPC.
- [ ] 6.3 Agregar headers HTTP de seguridad y defaults fail-closed.
- [ ] 6.4 Implementar AES-GCM, HMAC/SHA-256/BLAKE3, RSA-OAEP, ECDH y firmas.
- [ ] 6.5 Implementar protocolos KMS y adaptadores opcionales AWS, Azure y GCP.
- [ ] 6.6 Probar round-trips, inputs inválidos y KMS mediante dobles inyectados.

## 7. Jobs, workers y CLI

- [ ] 7.1 Implementar jobs interval/cron con pause, resume, stop y modo test.
- [ ] 7.2 Implementar cola de workers acotada con backpressure y apagado ordenado.
- [ ] 7.3 Crear `qpython new fastapi|grpc|hybrid` con YAML por defecto.
- [ ] 7.4 Crear utilidad de claves/certificados y ejemplos ejecutables.

## 8. Documentación y distribución

- [ ] 8.1 Escribir README en español e inglés, referencia de configuración y ejemplos.
- [ ] 8.2 Alcanzar >=85 % de cobertura y aprobar lint, tipado y análisis de seguridad.
- [ ] 8.3 Construir wheel/sdist y probar el wheel en una `.venv` limpia.
- [ ] 8.4 Configurar CI y publicación PyPI con Trusted Publishing.
- [ ] 8.5 Ejecutar el checklist de `push.txt`, etiquetar y publicar `0.1.0`.
