from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

import pytest

from good_agent.core.event_router.context import EventContext
from good_agent.core.event_router.core import EventRouter
from good_agent.core.event_router.decorators import emit, on, typed_on

T_Handler = TypeVar("T_Handler", bound=Callable[..., Any])
EmitDecorator = Callable[[T_Handler], T_Handler]
emit_default = cast(EmitDecorator, emit)


class _HandlerWithConfig(Protocol):
    _event_handler_config: dict[str, Any]


def test_on_and_typed_on_store_metadata():
    @on("demo:event", priority=50)
    def handler(ctx):
        return ctx

    @typed_on("demo:event")
    def typed_handler(ctx):
        return ctx

    handler_config = cast(_HandlerWithConfig, handler)
    typed_handler_config = cast(_HandlerWithConfig, typed_handler)

    assert handler_config._event_handler_config["events"] == ("demo:event",)
    assert typed_handler_config._event_handler_config["events"] == ("demo:event",)
    assert handler_config._event_handler_config["priority"] == 50


class _DummyRouter(EventRouter):
    def __init__(self):
        super().__init__(enable_signal_handling=False)
        self.sync_calls: list[tuple[str, dict]] = []
        self.async_calls: list[tuple[str, dict]] = []

    def apply_sync(self, event, **kwargs):  # type: ignore[override]
        self.sync_calls.append((event, kwargs))
        return EventContext(parameters=kwargs, event=event)

    async def apply_async(self, event, **kwargs):  # type: ignore[override]
        self.async_calls.append((event, kwargs))
        return EventContext(parameters=kwargs, event=event)

    @emit_default
    def sync_method(self, value: int) -> int:
        return value * 2

    @emit("custom", phases=emit.BEFORE | emit.AFTER | emit.ERROR)
    async def async_method(self, value: int) -> int:
        if value < 0:
            raise ValueError("boom")
        return value + 1


def test_emit_decorator_invokes_lifecycle_sync():
    router = _DummyRouter()
    result = router.sync_method(10)
    assert result == 20
    assert router.sync_calls[0][0] == "sync_method:before"
    assert router.sync_calls[1][0] == "sync_method:after"
    assert router.sync_calls[1][1]["result"] == 20


@pytest.mark.asyncio
async def test_emit_decorator_invokes_async_lifecycle_and_error_phase():
    router = _DummyRouter()
    await router.async_method(5)
    assert router.async_calls[0][0] == "custom:before"
    assert router.async_calls[1][0] == "custom:after"

    with pytest.raises(ValueError):
        await router.async_method(-1)
    # Last async call captures error phase
    assert router.async_calls[-1][0] == "custom:error"
    assert "error" in router.async_calls[-1][1]
