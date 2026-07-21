from __future__ import annotations

import asyncio

import pytest

from pythonforge.errors import ConfigurationError, LifecycleError
from pythonforge.tools import WorkerPool


async def test_items_are_processed() -> None:
    processed: list[int] = []

    async def handler(item: int) -> None:
        processed.append(item)

    async with WorkerPool(handler, concurrency=2) as pool:
        for value in range(5):
            await pool.submit(value)
        await pool.drain()

    assert sorted(processed) == [0, 1, 2, 3, 4]
    assert pool.stats.processed == 5


async def test_concurrency_is_bounded() -> None:
    """No more than `concurrency` handlers may run at the same time."""
    in_flight = 0
    peak = 0

    async def handler(item: int) -> None:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1

    async with WorkerPool(handler, concurrency=3, max_queue_size=50) as pool:
        for value in range(20):
            await pool.submit(value)
        await pool.drain()

    assert peak <= 3


async def test_try_submit_rejects_when_the_queue_is_full() -> None:
    """Backpressure: a full queue must say no rather than grow without bound."""
    release = asyncio.Event()

    async def handler(item: int) -> None:
        await release.wait()

    pool: WorkerPool[int] = WorkerPool(handler, concurrency=1, max_queue_size=2)
    await pool.start()
    try:
        accepted = [pool.try_submit(value) for value in range(10)]
        assert not all(accepted), "a bounded queue accepted an unbounded number of items"
        assert pool.stats.rejected > 0
    finally:
        release.set()
        await pool.stop()


async def test_submit_waits_for_room() -> None:
    release = asyncio.Event()
    started = asyncio.Event()

    async def handler(item: int) -> None:
        started.set()
        await release.wait()

    pool: WorkerPool[int] = WorkerPool(handler, concurrency=1, max_queue_size=1)
    await pool.start()
    try:
        await pool.submit(1)
        await started.wait()
        await pool.submit(2)

        # The third submit must block until the queue drains.
        pending = asyncio.create_task(pool.submit(3))
        await asyncio.sleep(0.02)
        assert not pending.done()

        release.set()
        await asyncio.wait_for(pending, timeout=1)
    finally:
        release.set()
        await pool.stop()


async def test_failing_handler_does_not_kill_the_pool() -> None:
    processed: list[int] = []

    async def handler(item: int) -> None:
        if item == 2:
            raise RuntimeError("bad item")
        processed.append(item)

    async with WorkerPool(handler, concurrency=1) as pool:
        for value in range(5):
            await pool.submit(value)
        await pool.drain()

    assert processed == [0, 1, 3, 4]
    assert pool.stats.failed == 1
    assert pool.stats.processed == 4


async def test_stop_drains_queued_work() -> None:
    processed: list[int] = []

    async def handler(item: int) -> None:
        await asyncio.sleep(0.005)
        processed.append(item)

    pool: WorkerPool[int] = WorkerPool(handler, concurrency=2, max_queue_size=50)
    await pool.start()
    for value in range(10):
        await pool.submit(value)
    await pool.stop()

    assert len(processed) == 10, "stop() must drain in-flight work before cancelling"


async def test_submitting_to_a_stopped_pool_is_rejected() -> None:
    async def handler(item: int) -> None:
        return None

    pool: WorkerPool[int] = WorkerPool(handler)
    with pytest.raises(LifecycleError):
        await pool.submit(1)
    with pytest.raises(LifecycleError):
        pool.try_submit(1)


async def test_drain_reports_timeout() -> None:
    release = asyncio.Event()

    async def handler(item: int) -> None:
        await release.wait()

    pool: WorkerPool[int] = WorkerPool(handler, concurrency=1)
    await pool.start()
    try:
        await pool.submit(1)
        assert await pool.drain(timeout=0.05) is False
    finally:
        release.set()
        await pool.stop()


async def test_pending_reports_queue_depth() -> None:
    release = asyncio.Event()

    async def handler(item: int) -> None:
        await release.wait()

    pool: WorkerPool[int] = WorkerPool(handler, concurrency=1, max_queue_size=10)
    await pool.start()
    try:
        for value in range(4):
            await pool.submit(value)
        await asyncio.sleep(0.01)
        assert pool.pending >= 1
    finally:
        release.set()
        await pool.stop()


async def test_start_is_idempotent() -> None:
    async def handler(item: int) -> None:
        return None

    pool: WorkerPool[int] = WorkerPool(handler, concurrency=2)
    await pool.start()
    await pool.start()
    assert pool.running
    await pool.stop()
    assert not pool.running


async def test_stop_is_safe_when_never_started() -> None:
    async def handler(item: int) -> None:
        return None

    await WorkerPool(handler).stop()


@pytest.mark.parametrize(
    ("concurrency", "max_queue_size"), [(0, 10), (-1, 10), (1, 0), (1, -5)]
)
def test_invalid_configuration_is_rejected(concurrency: int, max_queue_size: int) -> None:
    async def handler(item: int) -> None:
        return None

    with pytest.raises(ConfigurationError):
        WorkerPool(handler, concurrency=concurrency, max_queue_size=max_queue_size)
