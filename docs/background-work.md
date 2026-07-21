# Background work and the CLI

*Lee esto en español: [background-work.es.md](background-work.es.md)*

## Jobs

`JobScheduler` owns every job task, which is what guarantees nothing
outlives the process that started it.

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

Job bodies may be sync or async. A failing job never kills the scheduler:
the error is logged and counted in `job.stats` (`runs`, `failures`,
`last_run`, `last_error`), and the schedule continues.

`job.pause()` / `job.resume()` / `scheduler.stop()` control execution;
`job.state` is `STOPPED`, `RUNNING` or `PAUSED`.

### Cron expressions

A deliberately small 5-field matcher: `minute hour day month weekday`,
supporting `*`, fixed values, comma lists and `*/step`. Ranges and month or
day *names* are out of scope — anything more elaborate belongs in a
dedicated scheduler, not in a service library. Weekday follows cron
convention (Sunday is 0), not Python's.

### Test mode

`JobScheduler(test_mode=True)` creates no background tasks at all. Drive the
schedule by hand with `await scheduler.tick(moment)`, so job behaviour is
tested deterministically instead of with `asyncio.sleep` in the suite:

```python
scheduler = JobScheduler(test_mode=True)
scheduler.add_cron_job("nightly", run_report, expression="0 3 * * *")
await scheduler.start()

await scheduler.tick(datetime(2026, 7, 21, 3, 0, tzinfo=UTC))   # fires
await scheduler.tick(datetime(2026, 7, 21, 10, 0, tzinfo=UTC))  # does not
```

## Workers

`WorkerPool` runs N workers over a **bounded** queue. The bound is the
point: an unbounded queue does not remove backpressure, it just moves the
failure from "producer waits" to "process runs out of memory".

```python
from pythonforge.tools import WorkerPool

async def handle(item: Job) -> None:
    ...

pool: WorkerPool[Job] = WorkerPool(handle, concurrency=4, max_queue_size=100)
await pool.start()

await pool.submit(item)        # waits for room -- this is the backpressure
accepted = pool.try_submit(item)   # False if the queue is full, never blocks

await pool.stop()              # drains queued work, then cancels the workers
```

- `stop()` stops accepting work, drains what is queued (bounded by
  `drain_timeout`), then cancels the workers — so a shutdown doesn't discard
  already-accepted items.
- A failing handler is logged and counted in `pool.stats` (`processed`,
  `failed`, `rejected`); it never takes the pool down.
- `pool.pending` reports queue depth; `await pool.drain(timeout=...)`
  returns `False` if it didn't finish in time.
- Submitting to a stopped pool raises `LifecycleError`.
- `async with pool:` starts and stops around a block.

## `qpython` CLI

Requires the `cli` extra (`pip install "pythonforge[cli]"`).

```bash
qpython new fastapi my-service          # HTTP only
qpython new grpc my-service             # gRPC only
qpython new hybrid my-service           # both, in one process
qpython new fastapi my-service --dir ./services/my-service
```

Each scaffold writes `application.yaml` (YAML is the documented default
format), a runnable `main.py`, and a `README.md`. The generated service
works as-is — the hybrid one serves HTTP and gRPC from a single process.

The CLI **never installs anything**: it prints the venv and install commands
and leaves the decision to you. It also refuses to scaffold into a non-empty
directory.

### Development certificates

```bash
qpython certs --dir certs --cn localhost --with-ca
```

Writes `cert.pem`/`key.pem` (and `ca.pem`/`ca-key.pem` with `--with-ca`,
which is what mTLS needs for `ca_file`). Private keys are written `0600`.
These are self-signed and for local development only.

Point the config at them:

```yaml
server:
  http:
    tls_enabled: true
    cert_file: certs/cert.pem
    key_file: certs/key.pem
    ca_file: certs/ca.pem
    mtls_required: true
```
