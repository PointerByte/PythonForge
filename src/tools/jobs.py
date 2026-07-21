"""Interval and cron-style background jobs tied to the service lifecycle.

Every job is owned by a :class:`JobScheduler`, which is what guarantees no
task outlives the process that started it. ``test_mode`` replaces real
sleeping with manual ticks so schedules can be tested deterministically
instead of with ``asyncio.sleep`` in the test suite.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..errors import ConfigurationError
from ..logger import get_logger, log_event

logger = get_logger("pythonforge.jobs")

JobCallable = Callable[[], Awaitable[None] | None]


class JobState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class JobStats:
    runs: int = 0
    failures: int = 0
    last_run: datetime | None = None
    last_error: str | None = None


class CronSchedule:
    """A deliberately small 5-field cron matcher (minute hour day month weekday).

    Supports ``*``, fixed values, comma lists and ``*/step``. Ranges and
    names are intentionally out of scope -- anything more elaborate belongs
    in a dedicated scheduler, not in a service library.
    """

    __slots__ = ("_fields", "expression")

    def __init__(self, expression: str) -> None:
        parts = expression.split()
        if len(parts) != 5:
            raise ConfigurationError(
                f"cron expression must have 5 fields (minute hour day month weekday): {expression!r}"
            )
        self.expression = expression
        bounds = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
        self._fields = [
            self._parse(field, low, high) for field, (low, high) in zip(parts, bounds, strict=True)
        ]

    @staticmethod
    def _parse(field: str, low: int, high: int) -> set[int]:
        allowed: set[int] = set()
        for chunk in field.split(","):
            if chunk == "*":
                allowed.update(range(low, high + 1))
            elif chunk.startswith("*/"):
                try:
                    step = int(chunk[2:])
                except ValueError as exc:
                    raise ConfigurationError(f"invalid cron step: {chunk!r}") from exc
                if step <= 0:
                    raise ConfigurationError(f"cron step must be positive: {chunk!r}")
                allowed.update(range(low, high + 1, step))
            else:
                try:
                    value = int(chunk)
                except ValueError as exc:
                    raise ConfigurationError(f"invalid cron field: {chunk!r}") from exc
                if not low <= value <= high:
                    raise ConfigurationError(f"cron value {value} out of range for {low}-{high}")
                allowed.add(value)
        return allowed

    def matches(self, moment: datetime) -> bool:
        minute, hour, day, month, weekday = self._fields
        return (
            moment.minute in minute
            and moment.hour in hour
            and moment.day in day
            and moment.month in month
            # datetime: Monday==0; cron: Sunday==0.
            and ((moment.weekday() + 1) % 7) in weekday
        )


@dataclass
class Job:
    """A single scheduled unit of work."""

    name: str
    func: JobCallable
    interval_seconds: float | None = None
    cron: CronSchedule | None = None
    run_on_start: bool = False
    state: JobState = JobState.STOPPED
    stats: JobStats = field(default_factory=JobStats)
    _task: asyncio.Task[None] | None = field(default=None, repr=False)
    _resumed: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def __post_init__(self) -> None:
        if (self.interval_seconds is None) == (self.cron is None):
            raise ConfigurationError(f"job {self.name!r}: set exactly one of interval_seconds/cron")
        if self.interval_seconds is not None and self.interval_seconds <= 0:
            raise ConfigurationError(f"job {self.name!r}: interval_seconds must be positive")
        self._resumed.set()

    def pause(self) -> None:
        if self.state is JobState.RUNNING:
            self.state = JobState.PAUSED
            self._resumed.clear()

    def resume(self) -> None:
        if self.state is JobState.PAUSED:
            self.state = JobState.RUNNING
            self._resumed.set()

    async def run_once(self) -> None:
        """Execute the job body once, recording the outcome.

        A failing job never kills the scheduler: the error is logged and
        counted, and the schedule continues.
        """
        await self._resumed.wait()
        self.stats.runs += 1
        self.stats.last_run = datetime.now(tz=UTC)
        try:
            result = self.func()
            if result is not None:
                await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.stats.failures += 1
            self.stats.last_error = type(exc).__name__
            logger.exception("job %s failed", self.name)
            log_event(
                logger,
                logging.ERROR,
                "job failed",
                process="jobs",
                method=self.name,
                details={"error": type(exc).__name__},
            )


class JobScheduler:
    """Owns every job task, so shutdown leaves nothing orphaned.

    In ``test_mode`` no background tasks are created at all: call
    :meth:`tick` to drive the schedule by hand.
    """

    def __init__(self, *, test_mode: bool = False) -> None:
        self.test_mode = test_mode
        self._jobs: dict[str, Job] = {}

    @property
    def jobs(self) -> dict[str, Job]:
        return dict(self._jobs)

    def add_interval_job(
        self, name: str, func: JobCallable, *, seconds: float, run_on_start: bool = False
    ) -> Job:
        return self._add(
            Job(name=name, func=func, interval_seconds=seconds, run_on_start=run_on_start)
        )

    def add_cron_job(self, name: str, func: JobCallable, *, expression: str) -> Job:
        return self._add(Job(name=name, func=func, cron=CronSchedule(expression)))

    def _add(self, job: Job) -> Job:
        if job.name in self._jobs:
            raise ConfigurationError(f"duplicate job name: {job.name!r}")
        self._jobs[job.name] = job
        return job

    def get(self, name: str) -> Job:
        try:
            return self._jobs[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown job: {name!r}") from exc

    async def tick(self, moment: datetime | None = None) -> list[str]:
        """Run every job whose schedule matches ``moment``; returns their names.

        Only meaningful in test mode -- it is how a suite advances time
        without waiting for it.
        """
        moment = moment or datetime.now(tz=UTC)
        fired: list[str] = []
        for job in self._jobs.values():
            if job.state is JobState.PAUSED:
                continue
            if job.cron is not None and job.cron.matches(moment):
                await job.run_once()
                fired.append(job.name)
            elif job.interval_seconds is not None:
                await job.run_once()
                fired.append(job.name)
        return fired

    async def start(self) -> None:
        if self.test_mode:
            for job in self._jobs.values():
                job.state = JobState.RUNNING
            return
        for job in self._jobs.values():
            job.state = JobState.RUNNING
            job._task = asyncio.create_task(self._run_job(job), name=f"pythonforge-job-{job.name}")
            logger.debug("job %s scheduled", job.name)

    async def _run_job(self, job: Job) -> None:
        if job.run_on_start:
            await job.run_once()
        while True:
            if job.interval_seconds is not None:
                await asyncio.sleep(job.interval_seconds)
                await job.run_once()
            else:
                # Cron resolution is one minute; wake up every second so
                # pause/stop stay responsive without busy-waiting.
                await asyncio.sleep(1)
                now = datetime.now(tz=UTC)
                if job.cron is not None and job.cron.matches(now) and now.second == 0:
                    await job.run_once()

    async def stop(self, *, timeout: float = 10.0) -> None:
        """Cancel every job task and wait for it, bounded by ``timeout``."""
        tasks = [job._task for job in self._jobs.values() if job._task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(task, timeout=timeout)
        for job in self._jobs.values():
            job.state = JobState.STOPPED
            job._task = None

    async def __aenter__(self) -> JobScheduler:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.stop()
