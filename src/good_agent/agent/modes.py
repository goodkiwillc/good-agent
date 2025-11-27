"""Agent modes system for managing distinct behavioral states.

Enables agents to operate in different modes with specialized tools, context
transformations, and capabilities. Modes are optional, stackable, and composable.
"""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypeVar


if TYPE_CHECKING:
    from good_agent.agent.core import Agent
    from good_agent.messages import AssistantMessage

P = ParamSpec("P")
T = TypeVar("T")

MODE_HANDLER_SKIP_KWARG = "__good_agent_internal_skip_mode_handler__"

# Type for new-style agent-centric handler functions
AgentModeHandler = Callable[["Agent"], Awaitable[Any]]


class HandlerStyle(Enum):
    """Indicates the signature style of a mode handler."""

    LEGACY = auto()  # Handler takes ModeContext as first param
    AGENT_CENTRIC = auto()  # Handler takes Agent as first param


def _detect_handler_style(handler: Callable[..., Any]) -> HandlerStyle:
    """Detect if handler uses legacy ModeContext or new Agent-centric style.

    Args:
        handler: The mode handler function

    Returns:
        HandlerStyle indicating the handler's signature style
    """
    sig = inspect.signature(handler)
    params = list(sig.parameters.values())

    if not params:
        # No parameters - treat as legacy for safety
        return HandlerStyle.LEGACY

    first_param = params[0]
    annotation = first_param.annotation

    # Check if annotation is Agent or "Agent" (string annotation)
    if annotation is inspect.Parameter.empty:
        # No annotation - check parameter name as fallback
        if first_param.name == "agent":
            return HandlerStyle.AGENT_CENTRIC
        return HandlerStyle.LEGACY

    # Handle string annotations
    if isinstance(annotation, str):
        if annotation == "Agent":
            return HandlerStyle.AGENT_CENTRIC
        return HandlerStyle.LEGACY

    # Handle actual type annotations
    type_name = getattr(annotation, "__name__", str(annotation))
    if type_name == "Agent":
        return HandlerStyle.AGENT_CENTRIC

    return HandlerStyle.LEGACY


@dataclass(slots=True)
class ModeTransition:
    """Instruction returned from a mode handler to change mode state."""

    transition_type: Literal["switch", "exit", "push"]
    target_mode: str | None = None
    parameters: dict[str, Any] | None = None


class ModeStateView(MutableMapping[str, Any]):
    """Mutable mapping facade that proxies state operations to ModeManager."""

    def __init__(self, manager: ModeManager):
        self._manager = manager

    def __getitem__(self, key: str) -> Any:
        sentinel = object()
        value = self._manager.get_state(key, sentinel)
        if value is sentinel:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._manager.set_state(key, value)

    def __delitem__(self, key: str) -> None:
        if not self._manager.delete_state(key):
            raise KeyError(key)

    def __iter__(self):
        return iter(self._manager.get_all_state())

    def __len__(self) -> int:
        return len(self._manager.get_all_state())

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ModeStateView({self._manager.get_all_state()!r})"


class ModeAccessor:
    """Provides access to current mode information via agent.mode property.

    This is the new agent-centric API for accessing mode state from within
    mode handlers. Instead of receiving a ModeContext, handlers now receive
    the Agent directly and access mode info via agent.mode.

    Example:
        @agent.modes('research')
        async def research_mode(agent: Agent):
            # Access mode info via agent.mode
            agent.mode.state['topic'] = 'quantum'
            print(f"In mode: {agent.mode.name}")
            print(f"Stack: {agent.mode.stack}")
    """

    def __init__(self, manager: ModeManager):
        """Initialize mode accessor.

        Args:
            manager: The ModeManager instance to proxy
        """
        self._manager = manager
        self._entered_at: datetime | None = None

    @property
    def name(self) -> str | None:
        """Get current mode name (top of stack), or None if not in a mode."""
        return self._manager.current_mode

    @property
    def stack(self) -> list[str]:
        """Get list of active modes (bottom to top)."""
        return self._manager.mode_stack

    @property
    def state(self) -> ModeStateView:
        """Get mutable state view for current mode scope."""
        return ModeStateView(self._manager)

    @property
    def duration(self) -> timedelta:
        """Get duration in current mode."""
        if self._entered_at is None:
            return timedelta(0)
        return datetime.now() - self._entered_at

    def in_mode(self, mode_name: str) -> bool:
        """Check if mode is active (anywhere in stack).

        Args:
            mode_name: Mode name to check

        Returns:
            True if mode is in stack
        """
        return self._manager.in_mode(mode_name)

    def switch(self, mode_name: str, **parameters: Any) -> ModeTransition:
        """Request switching to another mode.

        Args:
            mode_name: Target mode name
            **parameters: Parameters to pass to new mode

        Returns:
            ModeTransition instruction
        """
        return ModeTransition(
            transition_type="switch",
            target_mode=mode_name,
            parameters=parameters or None,
        )

    def push(self, mode_name: str, **parameters: Any) -> ModeTransition:
        """Request pushing a new mode on top of current.

        Args:
            mode_name: Mode to push
            **parameters: Parameters to pass to new mode

        Returns:
            ModeTransition instruction
        """
        return ModeTransition(
            transition_type="push",
            target_mode=mode_name,
            parameters=parameters or None,
        )

    def exit(self) -> ModeTransition:
        """Request exiting the current mode.

        Returns:
            ModeTransition instruction
        """
        return ModeTransition(transition_type="exit")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ModeAccessor(name={self.name!r}, stack={self.stack!r})"


class ModeContext:
    """Context object passed to mode handlers with mode-specific operations.

    .. deprecated::
        Use agent-centric handlers with `agent: Agent` parameter instead.
        Access mode state via `agent.mode.state` instead of `ctx.state`.

    Provides access to agent, mode state, and methods for context transformations.
    """

    def __init__(
        self,
        agent: Agent,
        mode_name: str,
        mode_stack: list[str],
        state: MutableMapping[str, Any] | None = None,
        manager: ModeManager | None = None,
    ):
        """Initialize mode context.

        Args:
            agent: The agent instance
            mode_name: Name of the current mode
            mode_stack: Current mode stack (bottom to top)
            state: Scoped state mapping (defaults to proxy view)
        """
        self.agent = agent
        self.mode_name = mode_name
        self.mode_stack = mode_stack
        self._manager = manager
        if state is not None:
            self.state = state
        elif manager is not None:
            self.state = ModeStateView(manager)
        else:
            self.state = {}
        self._entered_at = datetime.now()

    async def call(self, *content_parts: Any, **kwargs: Any) -> AssistantMessage:
        """Make an LLM call within the mode context.

        Args:
            *content_parts: Content to send to LLM
            **kwargs: Additional arguments for the call

        Returns:
            Assistant response message
        """
        call_kwargs = {**kwargs, MODE_HANDLER_SKIP_KWARG: True}
        return await self.agent.call(*content_parts, **call_kwargs)

    def add_system_message(self, content: str) -> None:
        """Add a system message to the conversation.

        Args:
            content: System message content
        """
        self.agent.append(content, role="system")

    def switch_mode(self, mode_name: str, **parameters: Any) -> ModeTransition:
        """Request switching to another mode before continuing the call."""

        return ModeTransition(
            transition_type="switch",
            target_mode=mode_name,
            parameters=parameters or None,
        )

    def push_mode(self, mode_name: str, **parameters: Any) -> ModeTransition:
        """Request pushing an additional mode on top of the current stack."""

        return ModeTransition(
            transition_type="push",
            target_mode=mode_name,
            parameters=parameters or None,
        )

    def exit_mode(self) -> ModeTransition:
        """Request exiting the current mode before continuing the call."""

        return ModeTransition(transition_type="exit")

    @property
    def duration(self) -> timedelta:
        """Get duration in current mode."""
        return datetime.now() - self._entered_at


class ModeStack:
    """Manages mode stack with scoped state inheritance."""

    def __init__(self):
        """Initialize empty mode stack."""
        self._stack: list[tuple[str, dict[str, Any]]] = []

    def push(self, mode_name: str, state: dict[str, Any] | None = None) -> None:
        """Push new mode onto stack.

        Args:
            mode_name: Name of mode to push
            state: Initial state for mode (defaults to empty dict)
        """
        self._stack.append((mode_name, state or {}))

    def pop(self) -> tuple[str, dict[str, Any]] | None:
        """Pop mode from stack.

        Returns:
            Tuple of (mode_name, state) or None if stack is empty
        """
        if self._stack:
            return self._stack.pop()
        return None

    @property
    def current(self) -> str | None:
        """Get current mode name (top of stack)."""
        if self._stack:
            return self._stack[-1][0]
        return None

    @property
    def stack(self) -> list[str]:
        """Get list of mode names in stack (bottom to top)."""
        return [name for name, _ in self._stack]

    def in_mode(self, mode_name: str) -> bool:
        """Check if mode is anywhere in stack.

        Args:
            mode_name: Mode name to check

        Returns:
            True if mode is in stack
        """
        return any(name == mode_name for name, _ in self._stack)

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state with scoped lookup (inner to outer).

        Args:
            key: State key to look up
            default: Default value if key not found

        Returns:
            State value or default
        """
        # Search from innermost to outermost (right to left)
        for _, state in reversed(self._stack):
            if key in state:
                return state[key]
        return default

    def set_state(self, key: str, value: Any) -> None:
        """Set state in current scope (innermost mode).

        Args:
            key: State key
            value: State value
        """
        if self._stack:
            _, state = self._stack[-1]
            state[key] = value

    def get_all_state(self) -> dict[str, Any]:
        """Get merged state with inner values shadowing outer.

        Returns:
            Merged state dictionary
        """
        result: dict[str, Any] = {}
        # Start from outermost, let inner values overwrite
        for _, state in self._stack:
            result.update(state)
        return result

    def delete_state(self, key: str) -> bool:
        """Delete state value from the first (inner-most) scope containing it."""

        for _, state in reversed(self._stack):
            if key in state:
                del state[key]
                return True
        return False


# Type for mode handler functions
ModeHandler = Callable[[ModeContext], Awaitable[Any]]


class ModeContextManager:
    """Context manager for entering/exiting a mode."""

    def __init__(self, manager: ModeManager, mode_name: str):
        """Initialize mode context manager.

        Args:
            manager: Parent mode manager
            mode_name: Name of mode to enter
        """
        self._manager = manager
        self._mode_name = mode_name

    async def __aenter__(self) -> Agent:
        """Enter the mode.

        Returns:
            The agent instance (for convenience)
        """
        await self._manager._enter_mode(self._mode_name)
        return self._manager._agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the mode."""
        await self._manager._exit_mode()
        return False


class ModeInfo:
    """Metadata about a registered mode."""

    def __init__(self, name: str, handler: ModeHandler, description: str | None = None):
        """Initialize mode info.

        Args:
            name: Mode name
            handler: Mode handler function
            description: Mode description (from docstring)
        """
        self.name = name
        self.handler = handler
        self.description = description or handler.__doc__
        self.style = _detect_handler_style(handler)

    def info(self) -> dict[str, Any]:
        """Get mode metadata as dictionary.

        Returns:
            Dictionary with mode metadata
        """
        return {
            "name": self.name,
            "description": self.description,
            "handler": self.handler,
            "style": self.style.name,
        }


class ModeManager:
    """Manages mode registration, entry/exit, and discovery.

    Provides decorator for mode registration and subscript access for mode entry.
    """

    def __init__(self, agent: Agent):
        """Initialize mode manager.

        Args:
            agent: The agent instance this manager belongs to
        """
        self._agent = agent
        self._registry: dict[str, ModeInfo] = {}
        self._mode_stack = ModeStack()
        self._pending_mode_switch: tuple[str, dict[str, Any]] | None = None
        self._pending_mode_exit = False

    def __call__(self, name: str) -> Callable[[ModeHandler], ModeHandler]:
        """Decorator for registering a mode handler.

        Args:
            name: Name of the mode

        Returns:
            Decorator function

        Example:
            @agent.modes('research')
            async def research_mode(ctx: ModeContext):
                ctx.add_system_message("You are in research mode")
                return await ctx.call()
        """

        def decorator(func: ModeHandler) -> ModeHandler:
            # Extract description from docstring
            description = func.__doc__

            # Register mode
            self._registry[name] = ModeInfo(name, func, description)

            return func

        return decorator

    def __getitem__(self, name: str) -> ModeContextManager:
        """Get mode context manager for entering a mode.

        Args:
            name: Mode name

        Returns:
            Context manager for entering the mode

        Raises:
            KeyError: If mode is not registered

        Example:
            async with agent.modes['research']:
                await agent.call("Research quantum computing")
        """
        if name not in self._registry:
            raise KeyError(f"Mode '{name}' is not registered")

        return ModeContextManager(self, name)

    def list_modes(self) -> list[str]:
        """List all registered mode names.

        Returns:
            List of mode names
        """
        return list(self._registry.keys())

    def get_info(self, name: str) -> dict[str, Any]:
        """Get metadata for a mode.

        Args:
            name: Mode name

        Returns:
            Mode metadata dictionary

        Raises:
            KeyError: If mode is not registered
        """
        if name not in self._registry:
            raise KeyError(f"Mode '{name}' is not registered")

        return self._registry[name].info()

    @property
    def current_mode(self) -> str | None:
        """Get current mode name (top of stack)."""
        return self._mode_stack.current

    @property
    def mode_stack(self) -> list[str]:
        """Get list of active modes (bottom to top)."""
        return self._mode_stack.stack

    def in_mode(self, mode_name: str) -> bool:
        """Check if mode is active (anywhere in stack).

        Args:
            mode_name: Mode name to check

        Returns:
            True if mode is in stack
        """
        return self._mode_stack.in_mode(mode_name)

    def get_handler(self, mode_name: str) -> ModeHandler | None:
        """Get the handler for a mode, if registered."""

        info = self._registry.get(mode_name)
        if info is None:
            return None
        return info.handler

    async def execute_handler(self, mode_name: str) -> Any:
        """Execute the handler for a mode with proper DI based on handler style.

        This method detects whether the handler uses the legacy ModeContext
        signature or the new agent-centric signature and calls it appropriately.

        Args:
            mode_name: Name of the mode whose handler to execute

        Returns:
            The result from the handler (ModeTransition, AssistantMessage, or None)

        Raises:
            KeyError: If mode is not registered
        """
        info = self._registry.get(mode_name)
        if info is None:
            raise KeyError(f"Mode '{mode_name}' is not registered")

        handler = info.handler

        if info.style == HandlerStyle.AGENT_CENTRIC:
            # New-style handler: inject Agent directly
            # Type ignore: handler is typed as ModeHandler but runtime dispatch
            # ensures it actually accepts Agent for AGENT_CENTRIC style
            return await handler(self._agent)  # type: ignore[arg-type]
        else:
            # Legacy handler: create ModeContext (with deprecation warning)
            warnings.warn(
                f"Mode handler '{mode_name}' uses deprecated ModeContext signature. "
                "Update to use 'agent: Agent' parameter instead. "
                "Access mode state via agent.mode.state instead of ctx.state.",
                DeprecationWarning,
                stacklevel=3,
            )
            ctx = self.create_context()
            return await handler(ctx)

    async def _enter_mode(self, mode_name: str, **params: Any) -> None:
        """Enter a mode (internal).

        Args:
            mode_name: Mode to enter
            **params: Parameters to pass to mode handler
        """
        if mode_name not in self._registry:
            raise KeyError(f"Mode '{mode_name}' is not registered")

        # Check if already in this mode (idempotent)
        if self._mode_stack.current == mode_name:
            return

        # Take snapshot of system prompt state for restore on exit
        self._agent._system_prompt_manager.take_snapshot()

        # Push mode onto stack
        self._mode_stack.push(mode_name, dict(params))

        # Emit mode:entered event
        from good_agent.events.agent import AgentEvents

        self._agent.do(
            AgentEvents.MODE_ENTERED,
            agent=self._agent,
            mode_name=mode_name,
            mode_stack=self.mode_stack,
            parameters=params,
            timestamp=datetime.now(),
        )

    async def _exit_mode(self) -> None:
        """Exit current mode (internal)."""
        if not self._mode_stack.current:
            return

        # Get current mode info before popping
        mode_name = self._mode_stack.current
        entered_at = datetime.now()  # TODO: Track this properly

        # Pop mode from stack
        self._mode_stack.pop()

        # Restore system prompt state to pre-mode snapshot
        self._agent._system_prompt_manager.restore_snapshot()

        # Emit mode:exited event
        from good_agent.events.agent import AgentEvents

        self._agent.do(
            AgentEvents.MODE_EXITED,
            agent=self._agent,
            mode_name=mode_name,
            mode_stack=self.mode_stack,
            duration=datetime.now() - entered_at,
            timestamp=datetime.now(),
        )

    async def enter_mode(self, mode_name: str, **params: Any) -> None:
        """Enter a mode directly (non-context-manager).

        Args:
            mode_name: Mode to enter
            **params: Parameters to pass to mode handler
        """
        await self._enter_mode(mode_name, **params)

    async def exit_mode(self) -> None:
        """Exit current mode directly (non-context-manager)."""
        await self._exit_mode()

    def schedule_mode_switch(self, mode_name: str, **params: Any) -> None:
        """Schedule switching to another mode before the next agent call."""

        if mode_name not in self._registry:
            raise KeyError(f"Mode '{mode_name}' is not registered")
        self._ensure_no_pending_mode_change()
        self._pending_mode_switch = (mode_name, dict(params))

    def schedule_mode_exit(self) -> None:
        """Schedule exiting the current mode before the next agent call."""

        if not self.current_mode:
            raise RuntimeError("Cannot schedule a mode exit when no mode is active")
        self._ensure_no_pending_mode_change()
        self._pending_mode_exit = True

    async def apply_scheduled_mode_changes(self) -> None:
        """Apply any pending scheduled mode exits or switches."""

        if self._pending_mode_exit:
            self._pending_mode_exit = False
            await self._exit_mode()

        if self._pending_mode_switch:
            mode_name, params = self._pending_mode_switch
            self._pending_mode_switch = None
            if self.current_mode:
                await self._exit_mode()
            await self._enter_mode(mode_name, **params)

    def create_context(self) -> ModeContext:
        """Create a ModeContext for the current active mode."""

        current_mode = self.current_mode
        if current_mode is None:
            raise RuntimeError("Cannot create mode context without an active mode")
        return ModeContext(
            agent=self._agent,
            mode_name=current_mode,
            mode_stack=self.mode_stack.copy(),
            manager=self,
        )

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get mode state value.

        Args:
            key: State key
            default: Default value if not found

        Returns:
            State value or default
        """
        return self._mode_stack.get_state(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set mode state value.

        Args:
            key: State key
            value: State value
        """
        self._mode_stack.set_state(key, value)

    def get_all_state(self) -> dict[str, Any]:
        """Get all mode state as merged dictionary.

        Returns:
            Merged state from all mode stack levels
        """
        return self._mode_stack.get_all_state()

    def delete_state(self, key: str) -> bool:
        """Delete a state value from the stack.

        Args:
            key: State key to delete

        Returns:
            True if the key was removed from any scope
        """

        return self._mode_stack.delete_state(key)

    def _ensure_no_pending_mode_change(self) -> None:
        if self._pending_mode_switch or self._pending_mode_exit:
            raise RuntimeError(
                "A mode change is already scheduled for the next call; "
                "wait for it to complete before scheduling another."
            )
