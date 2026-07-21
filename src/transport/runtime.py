"""Runs FastAPI and gRPC in one process with coordinated start and shutdown.

Lives outside ``transport/grpc/`` on purpose: importing it must not require
the ``grpc`` extra, so a runtime with only an HTTP transport still works.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from ..config import FullConfig
from ..errors import LifecycleError
from ..logger import get_logger

logger = get_logger("pythonforge.runtime")

Starter = Callable[[], Awaitable[None]]
Stopper = Callable[[], Awaitable[None]]


class ServiceRuntime:
    """Starts a set of transports atomically and drains them on shutdown.

    Atomic start: if any transport fails to come up, the ones already
    started are torn down before the error propagates, so a failed boot
    never leaves a half-open process behind.

    Graceful stop: transports stop accepting new work, in-flight
    requests/RPCs drain, then resources close -- all bounded by
    ``shutdown_timeout``.
    """

    def __init__(self, config: FullConfig, *, shutdown_timeout: float = 30.0) -> None:
        self._config = config
        self._shutdown_timeout = shutdown_timeout
        self._components: list[tuple[str, Starter, Stopper]] = []
        self._started: list[tuple[str, Stopper]] = []
        self._stopped = asyncio.Event()

    def add_component(self, name: str, start: Starter, stop: Stopper) -> None:
        """Register a transport or resource, started in registration order."""
        self._components.append((name, start, stop))

    def add_grpc_server(self, server: Any, *, name: str = "grpc") -> None:
        """Register a ``grpc.aio.Server`` created by ``create_grpc_server``."""

        async def start() -> None:
            await server.start()

        async def stop() -> None:
            # grace lets in-flight RPCs finish before the socket closes.
            await server.stop(grace=self._shutdown_timeout)

        self.add_component(name, start, stop)

    def add_uvicorn_server(self, server: Any, *, name: str = "http") -> None:
        """Register a preconfigured ``uvicorn.Server``.

        uvicorn's ``serve()`` blocks, so it runs as a task; ``should_exit``
        is how uvicorn is asked to drain and return.
        """
        task: dict[str, asyncio.Task[None]] = {}

        async def start() -> None:
            task["task"] = asyncio.create_task(server.serve(), name=f"pythonforge-{name}")
            # Give uvicorn a chance to bind before we report success, so a
            # port conflict surfaces as a start failure, not a late crash.
            while not getattr(server, "started", False):
                if task["task"].done():
                    await task["task"]  # re-raises the bind error
                    return
                await asyncio.sleep(0.01)

        async def stop() -> None:
            server.should_exit = True
            running = task.get("task")
            if running is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.wait_for(running, timeout=self._shutdown_timeout)

        self.add_component(name, start, stop)

    async def start(self) -> None:
        for name, start, stop in self._components:
            try:
                await start()
            except Exception as exc:
                logger.error("transport %s failed to start; rolling back", name)
                await self._stop_started()
                raise LifecycleError(f"transport {name!r} failed to start: {exc}") from exc
            self._started.append((name, stop))
            logger.info("transport %s started", name)

    async def stop(self) -> None:
        await self._stop_started()
        self._stopped.set()

    async def _stop_started(self) -> None:
        # Reverse order: the most recently started transport shuts down first.
        while self._started:
            name, stop = self._started.pop()
            try:
                await asyncio.wait_for(stop(), timeout=self._shutdown_timeout)
                logger.info("transport %s stopped", name)
            except TimeoutError:
                # One slow transport must not block the rest of the shutdown.
                logger.error("transport %s did not stop within the timeout", name)
            except Exception:
                logger.exception("transport %s raised while stopping", name)

    async def serve_forever(self, *, handle_signals: bool = True) -> None:
        """Start everything, then block until a termination signal or :meth:`stop`."""
        await self.start()
        loop = asyncio.get_running_loop()
        installed: list[signal.Signals] = []
        if handle_signals:
            for sig in (signal.SIGINT, signal.SIGTERM):
                with contextlib.suppress(NotImplementedError):
                    loop.add_signal_handler(sig, self._stopped.set)
                    installed.append(sig)
        try:
            await self._stopped.wait()
        finally:
            for sig in installed:
                with contextlib.suppress(NotImplementedError):
                    loop.remove_signal_handler(sig)
            await self._stop_started()

    async def __aenter__(self) -> ServiceRuntime:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()
