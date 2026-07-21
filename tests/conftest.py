from __future__ import annotations

import contextvars
from collections.abc import Iterator
from typing import Any

import pytest

from pythonforge import context as context_module


@pytest.fixture(autouse=True)
def _isolated_request_context() -> Iterator[None]:
    """Reset every request-scoped contextvar before/after each test.

    Without this, a test that sets context state directly (rather than
    through the auto-resetting ``RequestContext.bind``) would leak into
    whichever test happens to run next in the same process.
    """
    tokens: list[tuple[contextvars.ContextVar[Any], contextvars.Token[Any]]] = [
        (context_module._request_id, context_module._request_id.set(None)),
        (context_module._trace_context, context_module._trace_context.set(None)),
        (context_module._claims, context_module._claims.set(None)),
        (context_module._deadline, context_module._deadline.set(None)),
        (context_module._attributes, context_module._attributes.set(None)),
        (context_module._downstream_processes, context_module._downstream_processes.set(())),
    ]
    yield
    for var, token in reversed(tokens):
        var.reset(token)
