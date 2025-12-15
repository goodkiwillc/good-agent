"""Optional helpers that sit on top of EventRouter (e.g. TypedApply).

See ``examples/event_router/async_sync_bridge.py`` for scenarios that benefit
from typed helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic

from good_agent.core.event_router.context import EventContext
from good_agent.core.event_router.protocols import EventName, T_Parameters, T_Return

if TYPE_CHECKING:
    from good_agent.core.event_router.core import EventRouter


class TypedApply(Generic[T_Parameters, T_Return]):
    """Lightweight wrapper around ``EventRouter.apply_typed``/``apply_typed_sync``.

    Stores the parameter/return type hints once so repeated calls stay concise and
    type checkers retain context.
    """

    def __init__(
        self,
        router: EventRouter,
        params_type: type[T_Parameters] | None = None,
        return_type: type[T_Return] | None = None,
    ):
        """Initialize TypedApply with router and type hints.

        Args:
            router: EventRouter instance to delegate to
            params_type: Type hint for parameters (optional, for type checkers)
            return_type: Type hint for return value (optional, for type checkers)
        """
        self.router = router
        self.params_type = params_type
        self.return_type = return_type

    async def apply(self, event: EventName, **kwargs: Any) -> EventContext[T_Parameters, T_Return]:
        """Apply the event asynchronously with type safety.

        This method delegates to EventRouter.apply_typed() with the stored
        type parameters, providing a cleaner syntax for repeated typed calls.

        Args:
            event: Event name to dispatch
            **kwargs: Event parameters (must match params_type if specified)

        Returns:
            EventContext with typed parameters and return value

        Example:
            ```python
            typed_apply = router.typed(ProcessParams, ProcessResult)
            ctx = await typed_apply.apply("process", data={"x": 1})
            result: ProcessResult | None = ctx.return_value
            ```
        """
        return await self.router.apply_typed(event, self.params_type, self.return_type, **kwargs)

    def apply_sync(self, event: EventName, **kwargs: Any) -> EventContext[T_Parameters, T_Return]:
        """Apply the event synchronously with type safety.

        This method delegates to EventRouter.apply_typed_sync() with the stored
        type parameters, providing a cleaner syntax for repeated typed calls.

        Args:
            event: Event name to dispatch
            **kwargs: Event parameters (must match params_type if specified)

        Returns:
            EventContext with typed parameters and return value

        Example:
            ```python
            typed_apply = router.typed(ProcessParams, ProcessResult)
            ctx = typed_apply.apply_sync("process", data={"x": 1})
            result: ProcessResult | None = ctx.return_value
            ```
        """
        return self.router.apply_typed_sync(event, self.params_type, self.return_type, **kwargs)
