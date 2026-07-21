# Trabajo en segundo plano y la CLI

*Read this in English: [background-work.md](background-work.md)*

## Jobs

`JobScheduler` es dueño de cada tarea de job, y eso es lo que garantiza que
nada sobreviva al proceso que lo arrancó.

```python
from pythonforge.tools import JobScheduler

scheduler = JobScheduler()
scheduler.add_interval_job("refresh", refresh_cache, seconds=30, run_on_start=True)
scheduler.add_cron_job("nightly", run_report, expression="0 3 * * *")

app = create_app(
    config,
    on_startup=[lambda app: scheduler.start()],
    on_shutdown=[lambda app: scheduler.stop()],
)
```

Los cuerpos de los jobs pueden ser sync o async. Un job que falla nunca mata
al scheduler: el error se registra y se cuenta en `job.stats` (`runs`,
`failures`, `last_run`, `last_error`), y la programación continúa.

`job.pause()` / `job.resume()` / `scheduler.stop()` controlan la ejecución;
`job.state` es `STOPPED`, `RUNNING` o `PAUSED`.

### Expresiones cron

Un matcher deliberadamente pequeño de 5 campos: `minuto hora día mes
día-de-semana`, con soporte para `*`, valores fijos, listas por comas y
`*/paso`. Los rangos y los *nombres* de mes o día quedan fuera de alcance —
cualquier cosa más elaborada pertenece a un scheduler dedicado, no a una
librería de servicios. El día de la semana sigue la convención de cron
(domingo es 0), no la de Python.

### Modo test

`JobScheduler(test_mode=True)` no crea ninguna tarea en segundo plano.
Maneja la programación a mano con `await scheduler.tick(momento)`, para que
el comportamiento de los jobs se pruebe de forma determinista en vez de con
`asyncio.sleep` en la suite:

```python
scheduler = JobScheduler(test_mode=True)
scheduler.add_cron_job("nightly", run_report, expression="0 3 * * *")
await scheduler.start()

await scheduler.tick(datetime(2026, 7, 21, 3, 0, tzinfo=UTC))   # dispara
await scheduler.tick(datetime(2026, 7, 21, 10, 0, tzinfo=UTC))  # no dispara
```

## Workers

`WorkerPool` corre N workers sobre una cola **acotada**. La cota es el
punto: una cola sin límite no elimina el backpressure, sólo mueve el fallo
de "el productor espera" a "el proceso se queda sin memoria".

```python
from pythonforge.tools import WorkerPool

async def handle(item: Job) -> None:
    ...

pool: WorkerPool[Job] = WorkerPool(handle, concurrency=4, max_queue_size=100)
await pool.start()

await pool.submit(item)        # espera lugar -- esto es el backpressure
accepted = pool.try_submit(item)   # False si la cola está llena, nunca bloquea

await pool.stop()              # drena el trabajo encolado, luego cancela los workers
```

- `stop()` deja de aceptar trabajo, drena lo encolado (acotado por
  `drain_timeout`), y luego cancela los workers — así un apagado no descarta
  ítems ya aceptados.
- Un handler que falla se registra y se cuenta en `pool.stats`
  (`processed`, `failed`, `rejected`); nunca tumba el pool.
- `pool.pending` informa la profundidad de la cola; `await
  pool.drain(timeout=...)` devuelve `False` si no terminó a tiempo.
- Enviar a un pool detenido lanza `LifecycleError`.
- `async with pool:` arranca y detiene alrededor de un bloque.

## CLI `qpython`

Requiere el extra `cli` (`pip install "pythonforge[cli]"`).

```bash
qpython new fastapi my-service          # sólo HTTP
qpython new grpc my-service             # sólo gRPC
qpython new hybrid my-service           # ambos, en un proceso
qpython new fastapi my-service --dir ./services/my-service
```

Cada scaffold escribe `application.yaml` (YAML es el formato por defecto
documentado), un `main.py` ejecutable, y un `README.md`. El servicio
generado funciona tal cual — el híbrido sirve HTTP y gRPC desde un solo
proceso.

La CLI **nunca instala nada**: imprime los comandos de venv e instalación y
te deja la decisión. También se niega a hacer scaffold en un directorio no
vacío.

### Certificados de desarrollo

```bash
qpython certs --dir certs --cn localhost --with-ca
```

Escribe `cert.pem`/`key.pem` (y `ca.pem`/`ca-key.pem` con `--with-ca`, que
es lo que mTLS necesita para `ca_file`). Las llaves privadas se escriben con
permisos `0600`. Son autofirmados y sólo para desarrollo local.

Apunta la configuración a ellos:

```yaml
server:
  http:
    tls_enabled: true
    cert_file: certs/cert.pem
    key_file: certs/key.pem
    ca_file: certs/ca.pem
    mtls_required: true
```
