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
from enum import Enum, IntEnum, auto
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypeVar


if TYPE_CHECKING:
    from good_agent.agent.core import Agent
    from good_agent.messages import AssistantMessage

P = ParamSpec("P")
T = TypeVar("T")

MODE_HANDLER_SKIP_KWARG = "__good_agent_internal_skip_mode_handler__"

# Type for new-style agent-centric handler functions
AgentModeHandler = Callable[["Agent"], Awaitable[Any]]


class IsolationLevel(IntEnum):
    """Isolation level for mode execution.

    Levels are ordered from least to most restrictive. Child modes cannot
    have a lower isolation level than their parent.

    Values:
        NONE (0): Default. Shared state, messages, and config.
        CONFIG (1): Config/tools isolated, messages shared.
        THREAD (2): Messages are a temp view (original + new kept), config shared.
        FORK (3): Complete isolation - nothing persists back to parent.
    """

    NONE = 0
    CONFIG = 1
    THREAD = 2
    FORK = 3


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


class HandlerType(Enum):
    """Type of mode handler function."""

    SIMPLE = "simple"  # Regular async function (no cleanup)
    GENERATOR = "generator"  # Async generator with yield (setup/cleanup)


def _detect_handler_type(handler: Callable[..., Any]) -> HandlerType:
    """Detect if handler is a simple async function or async generator.

    Args:
        handler: The mode handler function

    Returns:
        HandlerType indicating the handler's type

    Raises:
        TypeError: If handler is not an async function or async generator
    """
    if inspect.isasyncgenfunction(handler):
        return HandlerType.GENERATOR
    elif inspect.iscoroutinefunction(handler):
        return HandlerType.SIMPLE
    else:
        raise TypeError(
            f"Mode handler must be async function or async generator, "
            f"got {type(handler).__name__}"
        )


@dataclass(slots=True)
class ModeTransition:
    """Instruction returned from a mode handler to change mode state."""

    transition_type: Literal["switch", "exit", "push"]
    target_mode: str | None = None
    parameters: dict[str, Any] | None = None


@dataclass
class IsolationSnapshot:
    """Snapshot of agent state for isolation restore.

    Captures the state needed to restore an agent to pre-mode entry state
    based on the isolation level.
    """

    isolation_level: IsolationLevel
    mode_name: str
    # Message isolation (for THREAD and FORK)
    message_version_ids: list[Any] | None = None
    message_count: int = 0
    # Config isolation (for CONFIG and FORK)
    tool_state: dict[str, Any] | None = None


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


@dataclass
@dataclass
class ActiveModeGenerator:
    """Tracks a paused mode generator awaiting cleanup."""

    mode_name: str
    generator: Any  # AsyncGenerator[Agent, None] - using Any to avoid import issues
    started_at: datetime


@dataclass
class ModeStackEntry:
    """Entry in the mode stack with all mode-specific data."""

    name: str
    state: dict[str, Any]
    isolation: IsolationLevel
    isolation_snapshot: IsolationSnapshot | None = None
    active_generator: ActiveModeGenerator | None = None
    entered_at: datetime | None = None


class ModeStack:
    """Manages mode stack with scoped state inheritance and isolation tracking."""

    def __init__(self):
        """Initialize empty mode stack."""
        self._stack: list[ModeStackEntry] = []

    def push(
        self,
        mode_name: str,
        state: dict[str, Any] | None = None,
        isolation: IsolationLevel = IsolationLevel.NONE,
        isolation_snapshot: IsolationSnapshot | None = None,
        active_generator: ActiveModeGenerator | None = None,
        entered_at: datetime | None = None,
    ) -> None:
        """Push new mode onto stack.

        Args:
            mode_name: Name of mode to push
            state: Initial state for mode (defaults to empty dict)
            isolation: Isolation level for this mode
            isolation_snapshot: Snapshot for restore on exit
            active_generator: Generator tracking for cleanup
            entered_at: Timestamp when mode was entered
        """
        entry = ModeStackEntry(
            name=mode_name,
            state=state or {},
            isolation=isolation,
            isolation_snapshot=isolation_snapshot,
            active_generator=active_generator,
            entered_at=entered_at or datetime.now(),
        )
        self._stack.append(entry)

    def pop(self) -> ModeStackEntry | None:
        """Pop mode from stack.

        Returns:
            ModeStackEntry or None if stack is empty
        """
        if self._stack:
            return self._stack.pop()
        return None

    @property
    def current(self) -> str | None:
        """Get current mode name (top of stack)."""
        if self._stack:
            return self._stack[-1].name
        return None

    @property
    def current_entry(self) -> ModeStackEntry | None:
        """Get current mode entry (top of stack)."""
        if self._stack:
            return self._stack[-1]
        return None

    @property
    def current_isolation(self) -> IsolationLevel:
        """Get current isolation level (from top of stack, or NONE if empty)."""
        if self._stack:
            return self._stack[-1].isolation
        return IsolationLevel.NONE

    @property
    def stack(self) -> list[str]:
        """Get list of mode names in stack (bottom to top)."""
        return [entry.name for entry in self._stack]

    def in_mode(self, mode_name: str) -> bool:
        """Check if mode is anywhere in stack.

        Args:
            mode_name: Mode name to check

        Returns:
            True if mode is in stack
        """
        return any(entry.name == mode_name for entry in self._stack)

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state with scoped lookup (inner to outer).

        Args:
            key: State key to look up
            default: Default value if key not found

        Returns:
            State value or default
        """
        # Search from innermost to outermost (right to left)
        for entry in reversed(self._stack):
            if key in entry.state:
                return entry.state[key]
        return default

    def set_state(self, key: str, value: Any) -> None:
        """Set state in current scope (innermost mode).

        Args:
            key: State key
            value: State value
        """
        if self._stack:
            self._stack[-1].state[key] = value

    def get_all_state(self) -> dict[str, Any]:
        """Get merged state with inner values shadowing outer.

        Returns:
            Merged state dictionary
        """
        result: dict[str, Any] = {}
        # Start from outermost, let inner values overwrite
        for entry in self._stack:
            result.update(entry.state)
        return result

    def delete_state(self, key: str) -> bool:
        """Delete state value from the first (inner-most) scope containing it."""

        for entry in reversed(self._stack):
            if key in entry.state:
                del entry.state[key]
                return True
        return False


# Type for mode handler functions (supports both legacy ModeContext and v2 Agent styles)
ModeHandler = (
    Callable[[ModeContext], Awaitable[Any]] | Callable[["Agent"], Awaitable[Any]]
)


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

    def __init__(
        self,
        name: str,
        handler: ModeHandler,
        description: str | None = None,
        isolation: IsolationLevel = IsolationLevel.NONE,
        invokable: bool = False,
        tool_name: str | None = None,
    ):
        """Initialize mode info.

        Args:
            name: Mode name
            handler: Mode handler function
            description: Mode description (from docstring)
            isolation: Isolation level for this mode
            invokable: If True, generate a tool for agent to enter this mode
            tool_name: Custom tool name (default: 'enter_{name}_mode')
        """
        self.name = name
        self.handler = handler
        self.description = description or handler.__doc__
        self.style = _detect_handler_style(handler)
        self.isolation = isolation
        self.invokable = invokable
        self.tool_name = tool_name or f"enter_{name}_mode"

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
            "isolation": self.isolation.name,
            "invokable": self.invokable,
            "tool_name": self.tool_name if self.invokable else None,
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

    def __call__(
        self,
        name: str,
        *,
        isolation: IsolationLevel | str = IsolationLevel.NONE,
        invokable: bool = False,
        tool_name: str | None = None,
    ) -> Callable[[ModeHandler], ModeHandler]:
        """Decorator for registering a mode handler.

        Args:
            name: Name of the mode
            isolation: Isolation level for this mode. Can be IsolationLevel enum
                or string ('none', 'config', 'thread', 'fork'). Default is 'none'.
            invokable: If True, generates a tool that allows the agent to enter
                this mode. The tool schedules a mode switch for the next call.
            tool_name: Custom name for the generated tool. Default is
                'enter_{name}_mode'.

        Returns:
            Decorator function

        Example:
            @agent.modes('research')
            async def research_mode(agent: Agent):
                agent.prompt.append("You are in research mode")
                return await agent.call()

            @agent.modes('sandbox', isolation='fork')
            async def sandbox_mode(agent: Agent):
                # Complete isolation - changes don't persist
                return await agent.call()

            @agent.modes('planning', invokable=True)
            async def planning_mode(agent: Agent):
                '''Enter planning mode for strategic thinking.'''
                agent.prompt.append("Focus on planning and strategy.")
                # Agent can call 'enter_planning_mode' tool to switch here
        """
        # Convert string to IsolationLevel if needed
        if isinstance(isolation, str):
            try:
                isolation_level = IsolationLevel[isolation.upper()]
            except KeyError:
                valid = ", ".join(level.name.lower() for level in IsolationLevel)
                raise ValueError(
                    f"Invalid isolation level '{isolation}'. Must be one of: {valid}"
                ) from None
        else:
            isolation_level = isolation

        def decorator(func: ModeHandler) -> ModeHandler:
            # Extract description from docstring
            description = func.__doc__

            # Register mode with isolation level and invokable settings
            mode_info = ModeInfo(
                name,
                func,
                description,
                isolation=isolation_level,
                invokable=invokable,
                tool_name=tool_name,
            )
            self._registry[name] = mode_info

            # Generate and register tool if invokable
            if invokable:
                self._register_invokable_tool(mode_info)

            return func

        return decorator

    def _register_invokable_tool(self, mode_info: ModeInfo) -> None:
        """Generate and register a tool for agent-invoked mode switching.

        Args:
            mode_info: Mode metadata containing name, description, tool_name
        """
        from good_agent.tools import ToolManager, tool

        mode_name = mode_info.name
        generated_tool_name = mode_info.tool_name

        # Build tool description from mode docstring
        if mode_info.description:
            # Use first line of docstring as tool description
            first_line = mode_info.description.strip().split("\n")[0]
            tool_description = f"{first_line}"
        else:
            tool_description = f"Enter {mode_name} mode."

        # Capture mode_name and manager in closure
        manager = self

        @tool(name=generated_tool_name, description=tool_description)
        def mode_switch_tool() -> str:
            """Generated tool to schedule mode switch."""
            manager.schedule_mode_switch(mode_name)
            return f"Will enter {mode_name} mode."

        # Register tool with agent's ToolManager using __setitem__
        tool_manager = self._agent[ToolManager]
        tool_manager[generated_tool_name] = mode_switch_tool

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
            # Type ignore: handler is typed as ModeHandler union but runtime dispatch
            # ensures it actually accepts ModeContext for LEGACY style
            return await handler(ctx)  # type: ignore[arg-type]

    async def _run_handler_setup(
        self, mode_name: str, info: ModeInfo, entry: ModeStackEntry
    ) -> None:
        """Run handler setup phase (until yield for generators).

        For simple handlers, does nothing (they run via execute_handler during execute()).
        For generator handlers, runs until the first yield and stores
        the generator for later cleanup.

        Args:
            mode_name: Name of the mode
            info: Mode metadata
            entry: Stack entry to store generator in
        """
        handler = info.handler
        handler_type = _detect_handler_type(handler)

        if handler_type == HandlerType.SIMPLE:
            # Simple handlers are NOT run at entry - they run via execute_handler()
            # during the execute() loop for backward compatibility
            entry.active_generator = None
            return

        if handler_type == HandlerType.GENERATOR:
            # Generator - run until first yield
            if info.style == HandlerStyle.AGENT_CENTRIC:
                gen = handler(self._agent)  # type: ignore[arg-type]
            else:
                warnings.warn(
                    f"Mode handler '{mode_name}' uses deprecated ModeContext signature. "
                    "Update to use 'agent: Agent' parameter instead.",
                    DeprecationWarning,
                    stacklevel=4,
                )
                ctx = self.create_context()
                gen = handler(ctx)  # type: ignore[arg-type]

            # Run setup phase (until yield)
            # gen is actually AsyncGenerator at this point due to handler_type check
            try:
                await gen.__anext__()  # type: ignore[attr-defined]
            except StopAsyncIteration:
                # Generator returned without yielding - treat as simple
                entry.active_generator = None
                return

            # Generator yielded - store it for later cleanup
            entry.active_generator = ActiveModeGenerator(
                mode_name=mode_name,
                generator=gen,
                started_at=datetime.now(),
            )

    async def _run_handler_cleanup(self, entry: ModeStackEntry) -> None:
        """Run handler cleanup phase (after yield).

        Resumes the generator from yield and handles completion.

        Args:
            entry: Stack entry with active generator
        """
        if entry.active_generator is None:
            return

        gen = entry.active_generator.generator

        try:
            # Resume generator for cleanup
            try:
                await gen.__anext__()
                # If generator yields again, that's an error
                raise RuntimeError(
                    f"Mode handler '{entry.name}' yielded more than once"
                )
            except StopAsyncIteration:
                # Generator completed normally
                pass
        finally:
            # Ensure generator is closed
            await gen.aclose()

    def _create_isolation_snapshot(
        self, mode_name: str, isolation: IsolationLevel
    ) -> IsolationSnapshot | None:
        """Create isolation snapshot based on isolation level.

        Args:
            mode_name: Name of mode being entered
            isolation: Isolation level for the mode

        Returns:
            IsolationSnapshot if isolation requires it, None otherwise
        """
        if isolation == IsolationLevel.NONE:
            return None

        snapshot = IsolationSnapshot(
            isolation_level=isolation,
            mode_name=mode_name,
        )

        # Snapshot messages for THREAD and FORK isolation
        if isolation in (IsolationLevel.THREAD, IsolationLevel.FORK):
            if hasattr(self._agent, "_version_manager"):
                snapshot.message_version_ids = (
                    self._agent._version_manager.current_version.copy()
                )
            snapshot.message_count = len(self._agent.messages)

        # Snapshot tool state for CONFIG and FORK isolation
        if isolation in (IsolationLevel.CONFIG, IsolationLevel.FORK):
            from good_agent.tools import ToolManager

            tool_manager = self._agent[ToolManager]
            snapshot.tool_state = tool_manager._export_state()

        return snapshot

    def _restore_from_isolation_snapshot(
        self, snapshot: IsolationSnapshot | None
    ) -> None:
        """Restore agent state from isolation snapshot.

        Args:
            snapshot: The isolation snapshot to restore from
        """
        if snapshot is None:
            return

        isolation = snapshot.isolation_level

        # Restore messages based on isolation level
        if isolation == IsolationLevel.THREAD:
            # Thread: restore original messages but keep new ones added during mode
            if (
                hasattr(self._agent, "_version_manager")
                and snapshot.message_version_ids
            ):
                current_version = self._agent._version_manager.current_version
                # New messages are those beyond original count
                new_message_ids = current_version[snapshot.message_count :]
                # Restore: original + new
                restored_ids = snapshot.message_version_ids + new_message_ids
                self._agent._version_manager.add_version(restored_ids)
                self._agent._messages._sync_from_version()

        elif isolation == IsolationLevel.FORK:
            # Fork: complete restore - discard all changes
            if (
                hasattr(self._agent, "_version_manager")
                and snapshot.message_version_ids
            ):
                self._agent._version_manager.add_version(snapshot.message_version_ids)
                self._agent._messages._sync_from_version()

        # Restore tool state for CONFIG and FORK
        if isolation in (IsolationLevel.CONFIG, IsolationLevel.FORK):
            if snapshot.tool_state:
                from good_agent.tools import ToolManager

                tool_manager = self._agent[ToolManager]
                tool_manager._import_state(snapshot.tool_state)

    async def _enter_mode(self, mode_name: str, **params: Any) -> None:
        """Enter a mode (internal).

        Args:
            mode_name: Mode to enter
            **params: Parameters to pass to mode handler

        Raises:
            KeyError: If mode is not registered
            ValueError: If isolation level is less restrictive than parent
        """
        if mode_name not in self._registry:
            raise KeyError(f"Mode '{mode_name}' is not registered")

        # Check if already in this mode (idempotent)
        if self._mode_stack.current == mode_name:
            return

        mode_info = self._registry[mode_name]
        new_isolation = mode_info.isolation
        current_isolation = self._mode_stack.current_isolation

        # Validate isolation hierarchy: child cannot be less isolated than parent
        if new_isolation < current_isolation:
            raise ValueError(
                f"Mode '{mode_name}' has isolation level '{new_isolation.name}' "
                f"which is less restrictive than parent isolation '{current_isolation.name}'. "
                f"Child modes cannot reduce isolation level."
            )

        # Take snapshot of system prompt state for restore on exit
        self._agent._system_prompt_manager.take_snapshot()

        # Create isolation snapshot if needed
        isolation_snapshot = self._create_isolation_snapshot(mode_name, new_isolation)

        # Push mode onto stack with isolation info
        self._mode_stack.push(
            mode_name,
            dict(params),
            isolation=new_isolation,
            isolation_snapshot=isolation_snapshot,
            entered_at=datetime.now(),
        )

        # Run handler setup phase (runs until yield for generators)
        entry = self._mode_stack.current_entry
        assert entry is not None  # Just pushed, so entry exists
        try:
            await self._run_handler_setup(mode_name, mode_info, entry)
        except Exception:
            # Setup failed - pop the mode and restore state
            self._mode_stack.pop()
            self._agent._system_prompt_manager.restore_snapshot()
            self._restore_from_isolation_snapshot(isolation_snapshot)
            raise

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

        # Get current mode entry before popping
        entry = self._mode_stack.current_entry
        if entry is None:
            return

        mode_name = entry.name
        isolation_snapshot = entry.isolation_snapshot
        entered_at = entry.entered_at or datetime.now()

        # Run cleanup for generator handlers
        try:
            await self._run_handler_cleanup(entry)
        finally:
            # Always restore state even if cleanup fails
            # Pop mode from stack
            self._mode_stack.pop()

            # Restore system prompt state to pre-mode snapshot
            self._agent._system_prompt_manager.restore_snapshot()

            # Restore from isolation snapshot
            self._restore_from_isolation_snapshot(isolation_snapshot)

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

    def register(
        self,
        mode_or_handler: StandaloneMode | ModeHandler,
        name: str | None = None,
    ) -> None:
        """Register a standalone mode or handler function with this agent.

        Args:
            mode_or_handler: Either a StandaloneMode created by @mode() decorator
                or a raw handler function
            name: Mode name (required if passing a raw handler, optional for StandaloneMode)

        Raises:
            ValueError: If name is required but not provided
            TypeError: If mode_or_handler is not a valid type

        Example:
            # Register a standalone mode
            @mode('research')
            async def research_mode(agent: Agent):
                agent.prompt.append("Research mode active")

            agent.modes.register(research_mode)

            # Register with custom name
            agent.modes.register(some_handler, name='custom')
        """
        if isinstance(mode_or_handler, StandaloneMode):
            standalone = mode_or_handler
            mode_name = name or standalone.name
            handler = standalone.handler
            isolation = standalone.isolation
            invokable = standalone.invokable
            tool_name = standalone.tool_name
        elif callable(mode_or_handler):
            if name is None:
                raise ValueError(
                    "name is required when registering a raw handler function. "
                    "Use @mode('name') decorator or pass name='...' parameter."
                )
            mode_name = name
            handler = mode_or_handler
            isolation = IsolationLevel.NONE
            invokable = False
            tool_name = None
        else:
            raise TypeError(
                f"Expected StandaloneMode or callable, got {type(mode_or_handler).__name__}"
            )

        # Extract description from docstring
        description = handler.__doc__

        # Create and register ModeInfo
        mode_info = ModeInfo(
            mode_name,
            handler,
            description,
            isolation=isolation,
            invokable=invokable,
            tool_name=tool_name,
        )
        self._registry[mode_name] = mode_info

        # Generate and register tool if invokable
        if invokable:
            self._register_invokable_tool(mode_info)


@dataclass
class StandaloneMode:
    """A mode definition created by the @mode() decorator.

    This allows defining modes outside of an agent class and registering
    them later via agent.modes.register() or Agent(modes=[...]).
    """

    name: str
    handler: ModeHandler
    isolation: IsolationLevel = IsolationLevel.NONE
    invokable: bool = False
    tool_name: str | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow calling the underlying handler directly (for testing)."""
        return self.handler(*args, **kwargs)


def mode(
    name: str,
    *,
    isolation: IsolationLevel | str = IsolationLevel.NONE,
    invokable: bool = False,
    tool_name: str | None = None,
) -> Callable[[ModeHandler], StandaloneMode]:
    """Decorator for defining standalone modes outside of an agent.

    Creates a StandaloneMode that can be registered with an agent later
    via agent.modes.register() or passed to Agent(modes=[...]).

    Args:
        name: Name of the mode
        isolation: Isolation level ('none', 'config', 'thread', 'fork')
        invokable: If True, generates a tool for agent to enter this mode
        tool_name: Custom name for generated tool (default: 'enter_{name}_mode')

    Returns:
        Decorator that wraps handler in StandaloneMode

    Example:
        @mode('research', invokable=True)
        async def research_mode(agent: Agent):
            '''Enter research mode for investigation.'''
            agent.prompt.append("Focus on thorough research.")

        # Later, register with an agent
        agent.modes.register(research_mode)

        # Or pass to constructor
        agent = Agent("System prompt", modes=[research_mode])
    """
    # Convert string to IsolationLevel if needed
    if isinstance(isolation, str):
        try:
            isolation_level = IsolationLevel[isolation.upper()]
        except KeyError:
            valid = ", ".join(level.name.lower() for level in IsolationLevel)
            raise ValueError(
                f"Invalid isolation level '{isolation}'. Must be one of: {valid}"
            ) from None
    else:
        isolation_level = isolation

    def decorator(func: ModeHandler) -> StandaloneMode:
        return StandaloneMode(
            name=name,
            handler=func,
            isolation=isolation_level,
            invokable=invokable,
            tool_name=tool_name,
        )

    return decorator
