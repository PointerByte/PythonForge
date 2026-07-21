"""A bounded worker pool with real backpressure.

The queue has a maximum size on purpose: an unbounded queue does not remove
backpressure, it just moves the failure from "producer waits" to "process
runs out of memory". Producers either wait ({meth}`WorkerPool.submit`) or
are told no ({meth}`WorkerPool.try_submit`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from ..errors import ConfigurationError, LifecycleError
from ..logger import get_logger, log_event

logger = get_logger("pythonforge.workers")

T = TypeVar("T")
Handler = Callable[[T], Awaitable[None]]


@dataclass
class WorkerStats:
    processed: int = 0
    failed: int = 0
    rejected: int = 0


class WorkerPool(Generic[T]):
    """Runs ``concurrency`` workers over a bounded queue of items."""

    def __init__(
        self,
        handler: Handler[T],
        *,
        concurrency: int = 4,
        max_queue_size: int = 100,
        name: str = "workers",
    ) -> None:
        if concurrency < 1:
            raise ConfigurationError("worker concurrency must be at least 1")
        if max_queue_size < 1:
            raise ConfigurationError("max_queue_size must be at least 1")

        self._handler = handler
        self._concurrency = concurrency
        self._name = name
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=max_queue_size)
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self.stats = WorkerStats()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    async def submit(self, item: T) -> None:
        """Enqueue an item, waiting for room -- this is the backpressure."""
        if not self._running:
            raise LifecycleError(f"worker pool {self._name!r} is not running")
        await self._queue.put(item)

    def try_submit(self, item: T) -> bool:
        """Enqueue without waiting; ``False`` means the queue was full."""
        if not self._running:
            raise LifecycleError(f"worker pool {self._name!r} is not running")
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self.stats.rejected += 1
            return False
        return True

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(index), name=f"pythonforge-{self._name}-{index}")
            for index in range(self._concurrency)
        ]

    async def _worker(self, index: int) -> None:
        while True:
            item = await self._queue.get()
            try:
                await self._handler(item)
                self.stats.processed += 1
            except asyncio.CancelledError:
                # Put the item back so a drain-then-stop does not lose it.
                self._queue.task_done()
                raise
            except Exception as exc:
                self.stats.failed += 1
                logger.exception("worker %s-%d failed", self._name, index)
                log_event(
                    logger,
                    logging.ERROR,
                    "worker item failed",
                    process="workers",
                    method=self._name,
                    details={"error": type(exc).__name__},
                )
                self._queue.task_done()
            else:
                self._queue.task_done()

    async def drain(self, *, timeout: float | None = None) -> bool:
        """Wait until the queue empties. ``False`` if ``timeout`` hit first."""
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except TimeoutError:
            return False
        return True

    async def stop(self, *, drain_timeout: float = 10.0) -> None:
        """Stop accepting work, drain what is queued, then cancel the workers."""
        if not self._running:
            return
        self._running = False

        if not await self.drain(timeout=drain_timeout):
            logger.warning("worker pool %s did not drain within the timeout", self._name)

        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        self._workers.clear()

    async def __aenter__(self) -> WorkerPool[T]:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.stop()
