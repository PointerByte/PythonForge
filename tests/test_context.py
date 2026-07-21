from __future__ import annotations

import asyncio

import pytest

from pythonforge.context import DownstreamCall, RequestContext, TraceContext


def test_trace_context_roundtrip() -> None:
    trace = TraceContext(trace_id="a" * 32, parent_id="b" * 16, trace_flags="01")
    parsed = TraceContext.from_traceparent(trace.to_traceparent())
    assert parsed == trace


def test_trace_context_rejects_all_zero_trace_id() -> None:
    with pytest.raises(ValueError, match="trace-id"):
        TraceContext(trace_id="0" * 32)


def test_trace_context_rejects_all_zero_parent_id() -> None:
    with pytest.raises(ValueError, match="parent-id"):
        TraceContext(trace_id="a" * 32, parent_id="0" * 16)


def test_trace_context_rejects_bad_flags() -> None:
    with pytest.raises(ValueError, match="trace-flags"):
        TraceContext(trace_id="a" * 32, trace_flags="zz")


def test_to_tracestate_serializes_members() -> None:
    trace = TraceContext(trace_id="a" * 32, tracestate={"vendor1": "x", "vendor2": "y"})
    assert trace.to_tracestate() == "vendor1=x,vendor2=y"


@pytest.mark.parametrize(
    "value",
    [
        "not-a-traceparent",
        "00-tooshort-" + "b" * 16 + "-00",
        "ff-" + "a" * 32 + "-" + "b" * 16 + "-00",
        "zz-" + "a" * 32 + "-" + "b" * 16 + "-00",
        "00-" + "0" * 32 + "-" + "b" * 16 + "-00",
    ],
)
def test_from_traceparent_returns_none_for_malformed_input(value: str) -> None:
    assert TraceContext.from_traceparent(value) is None


def test_new_generates_a_valid_trace() -> None:
    trace = TraceContext.new()
    assert TraceContext.from_traceparent(trace.to_traceparent()) == trace


def test_parse_tracestate_drops_malformed_members() -> None:
    assert TraceContext.parse_tracestate("a=1,malformed,b=2, c = 3 ") == {
        "a": "1",
        "b": "2",
        "c": "3",
    }


def test_request_context_defaults_are_empty() -> None:
    ctx = RequestContext()
    assert ctx.request_id is None
    assert ctx.trace_context is None
    assert ctx.claims is None
    assert ctx.deadline is None
    assert ctx.attributes == {}
    assert ctx.downstream_processes == ()


def test_bind_sets_values_and_resets_on_exit() -> None:
    ctx = RequestContext()
    with ctx.bind(request_id="abc", deadline=123.0):
        assert ctx.request_id == "abc"
        assert ctx.deadline == 123.0
    assert ctx.request_id is None
    assert ctx.deadline is None


def test_bind_restores_previous_value_when_nested() -> None:
    ctx = RequestContext()
    with ctx.bind(request_id="outer"):
        with ctx.bind(request_id="inner"):
            assert ctx.request_id == "inner"
        assert ctx.request_id == "outer"


def test_direct_property_setters() -> None:
    ctx = RequestContext()
    ctx.request_id = "direct-id"
    ctx.trace_context = TraceContext.new()
    ctx.deadline = 42.0
    assert ctx.request_id == "direct-id"
    assert ctx.trace_context is not None
    assert ctx.deadline == 42.0


def test_merge_attributes_accumulates() -> None:
    ctx = RequestContext()
    ctx.merge_attributes(a=1)
    ctx.merge_attributes(b=2)
    assert ctx.attributes == {"a": 1, "b": 2}


def test_bind_claims_and_attributes() -> None:
    ctx = RequestContext()
    with ctx.bind(claims={"sub": "user-1"}, attributes={"tenant": "acme"}):
        assert ctx.claims == {"sub": "user-1"}
        assert ctx.attributes == {"tenant": "acme"}
    assert ctx.claims is None
    assert ctx.attributes == {}


def test_claims_getter_returns_a_copy() -> None:
    ctx = RequestContext()
    ctx.claims = {"sub": "user-1"}
    claims = ctx.claims
    assert claims is not None
    claims["sub"] = "tampered"
    assert ctx.claims == {"sub": "user-1"}


def test_add_downstream_call_appends_immutably() -> None:
    ctx = RequestContext()
    call = DownstreamCall(
        system="http", process="p", method="GET", destination="/x", status="200", latency_ms=1.0
    )
    ctx.add_downstream_call(call)
    assert ctx.downstream_processes == (call,)


async def test_downstream_calls_are_isolated_across_concurrent_tasks() -> None:
    """Regression test: a mutable-list ContextVar default is shared by every
    task that never explicitly sets it, so concurrent requests would leak
    each other's downstream calls."""

    async def worker(destination: str) -> tuple[DownstreamCall, ...]:
        ctx = RequestContext()
        ctx.add_downstream_call(
            DownstreamCall(
                system="http",
                process="p",
                method="GET",
                destination=destination,
                status="200",
                latency_ms=1.0,
            )
        )
        await asyncio.sleep(0.01)
        return ctx.downstream_processes

    result_a, result_b = await asyncio.gather(worker("/a"), worker("/b"))
    assert [call.destination for call in result_a] == ["/a"]
    assert [call.destination for call in result_b] == ["/b"]


async def test_bound_context_is_isolated_across_concurrent_tasks() -> None:
    async def worker(request_id: str) -> str | None:
        ctx = RequestContext()
        with ctx.bind(request_id=request_id):
            await asyncio.sleep(0.01)
            return ctx.request_id

    results = await asyncio.gather(worker("a"), worker("b"), worker("c"))
    assert results == ["a", "b", "c"]
