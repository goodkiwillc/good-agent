"""Agent modes system for managing distinct behavioral states.

Enables agents to operate in different modes with specialized tools, context
transformations, and capabilities. Modes are optional, stackable, and composable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar


if TYPE_CHECKING:
    from good_agent.agent.core import Agent
    from good_agent.messages import AssistantMessage

P = ParamSpec("P")
T = TypeVar("T")


class ModeContext:
    """Context object passed to mode handlers with mode-specific operations.

    Provides access to agent, mode state, and methods for context transformations.
    """

    def __init__(
        self,
        agent: Agent,
        mode_name: str,
        mode_stack: list[str],
        state: dict[str, Any],
    ):
        """Initialize mode context.

        Args:
            agent: The agent instance
            mode_name: Name of the current mode
            mode_stack: Current mode stack (bottom to top)
            state: Scoped state dictionary
        """
        self.agent = agent
        self.mode_name = mode_name
        self.mode_stack = mode_stack
        self.state = state
        self._entered_at = datetime.now()

    async def call(self, *content_parts: Any, **kwargs: Any) -> AssistantMessage:
        """Make an LLM call within the mode context.

        Args:
            *content_parts: Content to send to LLM
            **kwargs: Additional arguments for the call

        Returns:
            Assistant response message
        """
        return await self.agent.call(*content_parts, **kwargs)

    def add_system_message(self, content: str) -> None:
        """Add a system message to the conversation.

        Args:
            content: System message content
        """
        self.agent.append(content, role="system")

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

    def info(self) -> dict[str, Any]:
        """Get mode metadata as dictionary.

        Returns:
            Dictionary with mode metadata
        """
        return {
            "name": self.name,
            "description": self.description,
            "handler": self.handler,
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

        # Push mode onto stack
        self._mode_stack.push(mode_name, params)

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
