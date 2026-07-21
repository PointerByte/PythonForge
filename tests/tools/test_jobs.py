from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from pythonforge.errors import ConfigurationError
from pythonforge.tools import CronSchedule, JobScheduler, JobState


# --- CronSchedule ------------------------------------------------------


def test_cron_matches_every_minute() -> None:
    assert CronSchedule("* * * * *").matches(datetime(2026, 7, 21, 10, 30, tzinfo=UTC))


def test_cron_matches_specific_time() -> None:
    schedule = CronSchedule("30 10 * * *")
    assert schedule.matches(datetime(2026, 7, 21, 10, 30, tzinfo=UTC))
    assert not schedule.matches(datetime(2026, 7, 21, 10, 31, tzinfo=UTC))


def test_cron_supports_step_values() -> None:
    schedule = CronSchedule("*/15 * * * *")
    assert schedule.matches(datetime(2026, 7, 21, 10, 0, tzinfo=UTC))
    assert schedule.matches(datetime(2026, 7, 21, 10, 30, tzinfo=UTC))
    assert not schedule.matches(datetime(2026, 7, 21, 10, 7, tzinfo=UTC))


def test_cron_supports_lists() -> None:
    schedule = CronSchedule("0,30 * * * *")
    assert schedule.matches(datetime(2026, 7, 21, 10, 0, tzinfo=UTC))
    assert schedule.matches(datetime(2026, 7, 21, 10, 30, tzinfo=UTC))
    assert not schedule.matches(datetime(2026, 7, 21, 10, 15, tzinfo=UTC))


def test_cron_weekday_uses_sunday_as_zero() -> None:
    """cron numbers Sunday as 0; datetime numbers Monday as 0."""
    sunday = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    assert sunday.weekday() == 6
    assert CronSchedule("* * * * 0").matches(sunday)
    assert not CronSchedule("* * * * 1").matches(sunday)


@pytest.mark.parametrize(
    "expression", ["* * * *", "not-a-cron", "99 * * * *", "*/0 * * * *", "*/x * * * *"]
)
def test_invalid_cron_expressions_are_rejected(expression: str) -> None:
    with pytest.raises(ConfigurationError):
        CronSchedule(expression)


# --- Scheduling --------------------------------------------------------


async def test_interval_job_runs_in_test_mode() -> None:
    runs: list[int] = []
    scheduler = JobScheduler(test_mode=True)
    scheduler.add_interval_job("counter", lambda: runs.append(1), seconds=60)

    await scheduler.start()
    await scheduler.tick()
    await scheduler.tick()

    assert len(runs) == 2


async def test_async_job_body_is_awaited() -> None:
    runs: list[int] = []

    async def work() -> None:
        await asyncio.sleep(0)
        runs.append(1)

    scheduler = JobScheduler(test_mode=True)
    scheduler.add_interval_job("async-job", work, seconds=60)
    await scheduler.start()
    await scheduler.tick()

    assert runs == [1]


async def test_cron_job_only_fires_on_matching_moment() -> None:
    runs: list[int] = []
    scheduler = JobScheduler(test_mode=True)
    scheduler.add_cron_job("nightly", lambda: runs.append(1), expression="0 3 * * *")
    await scheduler.start()

    await scheduler.tick(datetime(2026, 7, 21, 10, 0, tzinfo=UTC))
    assert runs == []

    await scheduler.tick(datetime(2026, 7, 21, 3, 0, tzinfo=UTC))
    assert runs == [1]


async def test_pause_and_resume() -> None:
    runs: list[int] = []
    scheduler = JobScheduler(test_mode=True)
    job = scheduler.add_interval_job("pausable", lambda: runs.append(1), seconds=60)
    await scheduler.start()

    await scheduler.tick()
    job.pause()
    assert job.state is JobState.PAUSED
    await scheduler.tick()
    assert len(runs) == 1

    job.resume()
    assert job.state is JobState.RUNNING
    await scheduler.tick()
    assert len(runs) == 2


async def test_failing_job_is_recorded_but_does_not_stop_the_scheduler() -> None:
    scheduler = JobScheduler(test_mode=True)

    def boom() -> None:
        raise RuntimeError("job body failed")

    job = scheduler.add_interval_job("flaky", boom, seconds=60)
    await scheduler.start()
    await scheduler.tick()
    await scheduler.tick()

    assert job.stats.runs == 2
    assert job.stats.failures == 2
    assert job.stats.last_error == "RuntimeError"


async def test_stats_track_successful_runs() -> None:
    scheduler = JobScheduler(test_mode=True)
    job = scheduler.add_interval_job("ok", lambda: None, seconds=60)
    await scheduler.start()
    await scheduler.tick()

    assert job.stats.runs == 1
    assert job.stats.failures == 0
    assert job.stats.last_run is not None


def test_job_requires_exactly_one_schedule() -> None:
    from pythonforge.tools.jobs import Job

    with pytest.raises(ConfigurationError, match="exactly one"):
        Job(name="no-schedule", func=lambda: None)

    with pytest.raises(ConfigurationError, match="exactly one"):
        Job(name="both", func=lambda: None, interval_seconds=1, cron=CronSchedule("* * * * *"))


def test_job_rejects_non_positive_interval() -> None:
    from pythonforge.tools.jobs import Job

    with pytest.raises(ConfigurationError, match="positive"):
        Job(name="bad", func=lambda: None, interval_seconds=0)


def test_duplicate_job_names_are_rejected() -> None:
    scheduler = JobScheduler(test_mode=True)
    scheduler.add_interval_job("dup", lambda: None, seconds=60)
    with pytest.raises(ConfigurationError, match="duplicate"):
        scheduler.add_interval_job("dup", lambda: None, seconds=60)


def test_unknown_job_lookup_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="unknown job"):
        JobScheduler(test_mode=True).get("nope")


# --- Real scheduling / lifecycle ---------------------------------------


async def test_real_interval_job_runs_and_stops_cleanly() -> None:
    runs: list[int] = []
    scheduler = JobScheduler()
    scheduler.add_interval_job("fast", lambda: runs.append(1), seconds=0.01, run_on_start=True)

    async with scheduler:
        await asyncio.sleep(0.05)

    assert runs, "the job never ran"
    # Nothing may outlive the scheduler.
    assert all(job._task is None for job in scheduler.jobs.values())
    assert all(job.state is JobState.STOPPED for job in scheduler.jobs.values())


async def test_stop_is_safe_when_never_started() -> None:
    scheduler = JobScheduler()
    scheduler.add_interval_job("idle", lambda: None, seconds=60)
    await scheduler.stop()
