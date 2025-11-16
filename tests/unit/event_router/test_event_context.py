from __future__ import annotations

import pytest

from good_agent.core.event_router import ApplyInterrupt, EventContext, EventRouter
from good_agent.core.event_router.context import event_ctx


def test_stop_with_output_sets_flags_and_raises() -> None:
    ctx: EventContext[dict[str, int], dict[str, int]] = EventContext(parameters={"a": 1})

    with pytest.raises(ApplyInterrupt):
        ctx.stop_with_output({"sum": 3})

    assert ctx.output == {"sum": 3}
    assert ctx.should_stop is True


def test_stop_with_exception_sets_flag_without_interrupt() -> None:
    ctx: EventContext[dict[str, int], None] = EventContext(parameters={"a": 1})
    error = RuntimeError("boom")

    ctx.stop_with_exception(error)

    assert ctx.exception is error
    assert ctx.should_stop is True


def test_event_ctx_contextvar_matches_active_context() -> None:
    router = EventRouter()
    captured: list[EventContext] = []

    @router.on("ctx:var")
    def handler(ctx: EventContext) -> None:
        current = event_ctx.get()
        assert current is not None
        assert current is ctx
        captured.append(current)

    router.apply_sync("ctx:var")

    assert len(captured) == 1
