"""Event facade exposing advanced :class:`EventRouter` helpers for :class:`Agent`."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from good_agent.core.event_router import (
    EventContext,
    EventName,
    EventRouter,
    TypedApply,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .core import Agent


class AgentEventsFacade:
    """Thin wrapper around :class:`~good_agent.core.event_router.EventRouter` APIs."""

    def __init__(self, agent: "Agent") -> None:
        self._agent = agent

    async def apply(self, *args: Any, **kwargs: Any) -> EventContext[Any, Any]:
        """Delegate to :meth:`EventRouter.apply_async` without hitting Agent shim."""

        return await EventRouter.apply_async(self._agent, *args, **kwargs)

    async def apply_async(self, event: EventName, **kwargs: Any) -> EventContext[Any, Any]:
        """Delegate to :meth:`EventRouter.apply_async`."""

        return await EventRouter.apply_async(self._agent, event, **kwargs)

    def apply_sync(self, event: EventName, **kwargs: Any) -> EventContext[Any, Any]:
        """Delegate to :meth:`EventRouter.apply_sync`."""

        return EventRouter.apply_sync(self._agent, event, **kwargs)

    async def apply_typed(
        self,
        event: EventName,
        params_type: type[Any] | None = None,
        return_type: type[Any] | None = None,
        **kwargs: Any,
    ) -> EventContext[Any, Any]:
        """Delegate to :meth:`EventRouter.apply_typed`."""

        return await EventRouter.apply_typed(
            self._agent,
            event,
            params_type,
            return_type,
            **kwargs,
        )

    def apply_typed_sync(
        self,
        event: EventName,
        params_type: type[Any] | None = None,
        return_type: type[Any] | None = None,
        **kwargs: Any,
    ) -> EventContext[Any, Any]:
        """Delegate to :meth:`EventRouter.apply_typed_sync`."""

        return EventRouter.apply_typed_sync(
            self._agent,
            event,
            params_type,
            return_type,
            **kwargs,
        )

    def typed(
        self,
        params_type: type[Any] | None = None,
        return_type: type[Any] | None = None,
    ) -> TypedApply[Any, Any]:
        """Delegate to :meth:`EventRouter.typed`."""

        return EventRouter.typed(self._agent, params_type, return_type)

    def broadcast_to(self, router: EventRouter) -> int:
        """Delegate to :meth:`EventRouter.broadcast_to`."""

        return EventRouter.broadcast_to(self._agent, router)

    def consume_from(self, router: EventRouter) -> None:
        """Delegate to :meth:`EventRouter.consume_from`."""

        EventRouter.consume_from(self._agent, router)

    def set_event_trace(
        self,
        enabled: bool,
        *,
        verbosity: int = 1,
        use_rich: bool = True,
    ) -> None:
        """Delegate to :meth:`EventRouter.set_event_trace`."""

        EventRouter.set_event_trace(self._agent, enabled, verbosity, use_rich)

    @property
    def event_trace_enabled(self) -> bool:
        """Expose :attr:`EventRouter.event_trace_enabled`."""

        return EventRouter.event_trace_enabled.__get__(self._agent, type(self._agent))

    @property
    def ctx(self) -> EventContext[Any, Any]:
        """Expose :attr:`EventRouter.ctx`."""

        return EventRouter.ctx.__get__(self._agent, type(self._agent))

    def join(self, timeout: float = 5.0) -> None:
        """Delegate to :meth:`EventRouter.join`."""

        EventRouter.join(self._agent, timeout=timeout)

    async def join_async(self, timeout: float = 5.0) -> None:
        """Delegate to :meth:`EventRouter.join_async`."""

        await EventRouter.join_async(self._agent, timeout=timeout)

    def close(self) -> None:
        """Delegate to :meth:`EventRouter.close`."""

        EventRouter.close(self._agent)

    async def async_close(self) -> None:
        """Delegate to :meth:`EventRouter.async_close`."""

        await EventRouter.async_close(self._agent)


__all__ = ["AgentEventsFacade"]
