from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import warnings
import weakref
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Iterator,
    Sequence,
)
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    ParamSpec,
    Self,
    TypeAlias,
    TypedDict,
    TypeGuard,
    TypeVar,
    Unpack,
    cast,
    overload,
)

import orjson
from ulid import ULID

from good_agent.agent.components import ComponentRegistry
from good_agent.agent.context import ContextManager
from good_agent.agent.llm import LLMCoordinator
from good_agent.agent.messages import MessageManager
from good_agent.agent.modes import (
    MODE_HANDLER_SKIP_KWARG,
    ModeAccessor,
    ModeHandler,
    ModeManager,
    ModeTransition,
    StandaloneMode,
)
from good_agent.agent.state import AgentState, AgentStateMachine
from good_agent.agent.system_prompt import SystemPromptManager
from good_agent.agent.tasks import AgentTaskManager
from good_agent.agent.tools import ToolExecutor
from good_agent.agent.versioning import AgentVersioningManager
from good_agent.core.event_router import (
    EventContext,
    EventRouter,
    on,
)
from good_agent.core.types import URL
from good_agent.core.ulid_monotonic import (
    create_monotonic_ulid,
)

if TYPE_CHECKING:
    from litellm.types.utils import Choices

    from good_agent.mock import AgentMockInterface

from good_agent.agent.config import (
    AGENT_CONFIG_KEYS,
    AgentConfigManager,
    AgentContext,
    AgentOnlyConfig,
    LLMCommonConfig,
)
from good_agent.agent.pool import AgentPool
from good_agent.content import FileContentPart, ImageContentPart
from good_agent.core.components import AgentComponent
from good_agent.events import (  # Import typed event parameters
    AgentEvents,
    AgentInitializeParams,
)
from good_agent.extensions.template_manager import (
    Template,
    TemplateManager,
)
from good_agent.messages import (
    AnnotationLike,
    AssistantMessage,
    AssistantMessageStructuredOutput,
    FilteredMessageList,
    ImageDetail,
    Message,
    MessageContent,
    MessageList,
    MessageRole,
    SystemMessage,
    T_Output,
    ToolMessage,
    UserMessage,
)
from good_agent.messages.store import put_message
from good_agent.messages.validation import MessageSequenceValidator, ValidationMode
from good_agent.model.llm import LanguageModel
from good_agent.tools import (
    BoundTool,
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolManager,
    ToolResponse,
    ToolSignature,
)
from good_agent.tools.tools import ToolLike
from good_agent.utilities import print_message
from good_agent.utilities.console import AgentConsole

if TYPE_CHECKING:
    from good_agent.agent.conversation import Conversation
    from good_agent.agent.thread_context import ForkContext, ThreadContext

logger = logging.getLogger(__name__)

FilterPattern: TypeAlias = str

P_Message = TypeVar("P_Message", bound=Message)


class AgentConfigParameters(LLMCommonConfig, AgentOnlyConfig, TypedDict, total=False):
    # Merge of LLM parameters and agent-only configuration
    # temperature and max_tokens inherited from LLMCommonConfig
    max_retries: int
    fallback_models: list[str]
    tools: Sequence[str | Callable[..., Any] | Tool | Agent]
    # extensions: NotRequired[list[AgentComponent | type[AgentComponent]]]


T_AgentComponent = TypeVar("T_AgentComponent", bound=AgentComponent)

ToolFuncParams = ParamSpec("ToolFuncParams")
T_FuncResp = TypeVar("T_FuncResp")


def _is_choices_instance(obj: Any) -> TypeGuard[Choices]:
    """Type guard to check if an object is a Choices instance for type narrowing.

    This allows us to keep Choices behind TYPE_CHECKING while still
    providing proper type narrowing at runtime.
    """
    # At runtime, check the class name since we can't import Choices directly
    return obj.__class__.__name__ == "Choices"


# Legacy TypedDict kept for backward compatibility
# New code should use AgentInitializeParams from event_types
class AgentInitialize(TypedDict):
    agent: Agent
    tools: list[str | Callable[..., Any] | ToolCallFunction]


# Type variables for decorator
T = TypeVar("T")
P = ParamSpec("P")


# Overload for async generators (methods that yield) - direct decoration
@overload
def ensure_ready(
    func: Callable[P, AsyncIterator[T]],
) -> Callable[P, AsyncIterator[T]]: ...


# Overload for regular async functions (methods that return) - direct decoration
@overload
def ensure_ready(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...


# Overload for factory usage with arguments
@overload
def ensure_ready(
    *,
    wait_for_tasks: bool = False,
    wait_for_events: bool = False,
    timeout: float | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]: ...


def ensure_ready(
    func: Callable[P, Any] | None = None,
    *,
    wait_for_tasks: bool = False,
    wait_for_events: bool = False,
    timeout: float | None = None,
) -> Callable[P, Any] | Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    Decorator that ensures the agent is ready before executing the async method.

    Can be used as `@ensure_ready` or `@ensure_ready(wait_for_tasks=True)`.

    Args:
        func: The function to decorate (when used without parens)
        wait_for_tasks: If True, wait for managed tasks to complete
        wait_for_events: If True, wait for pending events to complete
        timeout: Timeout for waiting operations

    This decorator automatically calls await self.initialize() before executing
    the decorated method. Optionally, it can also wait for tasks and events.

    The decorator preserves the original function's metadata through functools.wraps.
    """
    import inspect

    def decorator(f: Callable[P, Any]) -> Callable[P, Any]:
        # Check if the function is an async generator
        if inspect.isasyncgenfunction(f):
            # Create wrapper for async generators
            @functools.wraps(f)
            async def async_gen_wrapper(
                self: Agent, *args: Any, **kwargs: Any
            ) -> AsyncIterator[Any]:
                # Ensure agent is ready before proceeding
                await self.initialize()

                # Optional waits
                if wait_for_tasks:
                    await self.wait_for_tasks(timeout=timeout)

                if wait_for_events:
                    await self.join(timeout=timeout or 5.0)

                # Yield from the generator
                # Use getattr to bypass type checker's argument analysis
                method = getattr(f, "__call__", f)  # noqa: B004
                async for item in method(self, *args, **kwargs):  # type: ignore[misc, arg-type]
                    yield item

            return async_gen_wrapper  # type: ignore[return-value]
        else:
            # Create wrapper for regular async functions
            @functools.wraps(f)
            async def async_wrapper(self: Agent, *args: Any, **kwargs: Any) -> Any:
                # Ensure agent is ready before proceeding
                await self.initialize()

                # Optional waits
                if wait_for_tasks:
                    await self.wait_for_tasks(timeout=timeout)

                if wait_for_events:
                    await self.join(timeout=timeout or 5.0)

                # Await and return the result
                # Use getattr to bypass type checker's argument analysis
                method = getattr(f, "__call__", f)  # noqa: B004
                return await method(self, *args, **kwargs)  # type: ignore[misc, arg-type]

            return async_wrapper  # type: ignore[return-value]

    if func is None:
        return decorator
    else:
        return decorator(func)


class Agent(EventRouter):
    """AI conversational agent with tool integration and message management.

    Orchestrates LLM interactions with structured message handling, tool execution,
    and extensible event-driven architecture.

    Example:
        >>> async with Agent(model="gpt-4", tools=[search]) as agent:
        ...     response = await agent.call("Hello!")

    Note:
        Not thread-safe. Use separate Agent instances (e.g. via AgentPool) for
        concurrent workloads.
    """

    __registry__: ClassVar[dict[ULID, weakref.ref[Agent]]] = {}

    @classmethod
    def get(cls, agent_id: ULID) -> Agent | None:
        """Retrieve an agent instance by its ID"""
        ref = cls.__registry__.get(agent_id)
        if ref:
            agent = ref()
            if agent:
                return agent
            else:
                # Reference is dead, remove from registry
                del cls.__registry__[agent_id]
        return None

    @classmethod
    def get_by_name(cls, name: str) -> Agent | None:
        """Retrieve an agent instance by its name (first match)"""
        for ref in cls.__registry__.values():
            agent = ref()
            if agent and agent.name == name:
                return agent
        return None

    # Convenience aliases

    EVENTS: ClassVar[type[AgentEvents]] = AgentEvents

    _MAX_MODE_TRANSITIONS_PER_CALL: ClassVar[int] = 8

    _init_task: asyncio.Task | None = None
    _conversation: Conversation | None = None
    _id: ULID
    _session_id: ULID
    _name: str | None = None
    _extensions: dict[type[AgentComponent], AgentComponent]
    _extension_names: dict[str, AgentComponent]
    _agent_ref: weakref.ref[Agent | None] | None = None
    _messages: MessageList[Message]
    _context: AgentContext
    _config_manager: AgentConfigManager
    _language_model: LanguageModel
    _tool_manager: ToolManager
    _template_manager: TemplateManager
    _mock: AgentMockInterface
    _pool: AgentPool | None = None
    _state_machine: AgentStateMachine
    _mode_manager: ModeManager

    @staticmethod
    def context_providers(name: str):
        """Register a global context provider.

        .. deprecated::
            Use ``ContextManager.context_providers()`` for global providers
            or ``agent.context_provider()`` for instance-specific providers.
        """
        warnings.warn(
            "Agent.context_providers() is deprecated. "
            "Use ContextManager.context_providers() for global providers "
            "or agent.context_provider() for instance-specific providers.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ContextManager.context_providers(name)

    def as_tool(
        self,
        name: str | None = None,
        description: str | None = None,
        multi_turn: bool = True,
    ) -> Tool:
        """
        Convert the agent into a Tool that can be used by other agents.

        Args:
            name: Optional name for the tool (defaults to agent's name)
            description: Optional description for the tool
            multi_turn: Whether to support multi-turn sessions (default: True)

        Returns:
            A Tool instance wrapping this agent
        """
        from good_agent.tools.agent_tool import AgentAsTool

        return AgentAsTool(
            agent=self,
            name=name,
            description=description,
            multi_turn=multi_turn,
        ).as_tool()

    def print(self, message: int | Message | None = None, mode: str | None = None) -> None:
        """
        Pretty print a message using rich.

        Args:
            message: Message to print (defaults to last message)
            mode: Render mode ('display', 'llm', 'raw'). If None, uses config.print_messages_mode
        """
        from good_agent.content import RenderMode

        # Determine which message to print
        if message is None:
            msg = self[-1]
        elif isinstance(message, int):
            msg = self.messages[message]
        elif isinstance(message, Message):
            msg = message
        else:
            raise TypeError(f"Expected int or Message, got {type(message).__name__}")

        # Determine render mode
        render_mode_str = mode or self.config.print_messages_mode

        # Map string to RenderMode enum
        render_mode_map = {
            "display": RenderMode.DISPLAY,
            "llm": RenderMode.LLM,
            "raw": RenderMode.RAW,
        }
        render_mode = render_mode_map.get(render_mode_str, RenderMode.DISPLAY)

        # Print with specified render mode and markdown preference
        print_message(
            msg,
            render_mode=render_mode,
            force_markdown=self.config.print_messages_markdown,
        )

    def __init__(
        self,
        *system_prompt_parts: MessageContent,
        config_manager: AgentConfigManager | None = None,
        language_model: LanguageModel | None = None,
        tool_manager: ToolManager | None = None,
        agent_context: AgentContext | None = None,
        template_manager: TemplateManager | None = None,
        mock: AgentMockInterface | None = None,
        extensions: list[AgentComponent] | None = None,
        modes: list[StandaloneMode | ModeHandler] | None = None,
        _event_trace: bool | None = None,
        **config: Unpack[AgentConfigParameters],
    ):
        """Initialize agent with model, tools, and configuration.

        Creates agent instance with components and configuration. Call await agent.initialize()
        or use async context manager for complete initialization.

        Args:
            *system_prompt_parts: Content for initial system message
            config_manager: Configuration manager (creates default if None)
            language_model: LLM instance (creates default if None)
            tool_manager: Tool manager (creates default if None)
            agent_context: Template context system (creates default if None)
            template_manager: Template processor (creates default if None)
            mock: Mock interface for testing (creates default if None)
            extensions: List of AgentComponent instances
            modes: List of StandaloneMode or handler functions to register
            _event_trace: Enable event tracing for debugging
            **config: Configuration parameters (model, temperature, tools, etc.)

        Example:
            >>> agent = Agent("You are helpful", model="gpt-4", tools=[search])
            >>> async with agent:
            ...     response = await agent.call("Hello")
        """
        extensions = extensions or []
        self.config = config_manager or AgentConfigManager(**config)
        self.config._set_agent(self)  # Set agent reference for version updates
        self._context = agent_context or AgentContext()
        self._context._set_agent_config(self.config)

        tools: Sequence[str | Callable[..., Any] | Tool | ToolCallFunction | Agent] = (
            config.pop("tools", []) or []
        )

        # Initialize message list
        self._messages = MessageList[Message]()
        self._messages._set_agent(self)

        # Initialize identifiers
        self._id = create_monotonic_ulid()
        self._session_id = self._id  # Session ID starts as agent ID, but can be overridden
        self._name = self.config.get("name")

        # Initialize versioning infrastructure
        from good_agent.messages.versioning import MessageRegistry

        self._message_registry = MessageRegistry()

        # Initialize AgentVersioningManager
        self._versioning_manager = AgentVersioningManager(self)

        # Enable versioning for messages
        self._messages._init_versioning(
            self._message_registry, self._versioning_manager._version_manager, self
        )

        # Initialize MessageManager
        self._message_manager = MessageManager(self)

        # Initialize state management
        self._state_machine = AgentStateMachine(self)

        # Initialize ToolExecutor
        self._tool_executor = ToolExecutor(self)

        # Initialize LLMCoordinator
        self._llm_coordinator = LLMCoordinator(self)

        # Initialize ComponentRegistry
        self._component_registry = ComponentRegistry(self)

        # Initialize ContextManager
        self._context_manager = ContextManager(self)

        # Initialize task management
        self._task_manager = AgentTaskManager(self)
        # Back-compat: legacy code inspects _managed_tasks directly
        self._managed_tasks = self._task_manager._managed_tasks

        # Initialize mode manager and accessor
        self._mode_manager = ModeManager(self)
        self._mode_accessor = ModeAccessor(self._mode_manager)

        # Initialize console for rich CLI output
        self._console = AgentConsole(agent=self)

        # Store modes for registration after extensions are ready
        self._pending_modes = modes

        # Initialize system prompt manager
        self._system_prompt_manager = SystemPromptManager(self)

        # Initialize message sequence validator
        validation_mode = config.get("message_validation_mode", "warn")
        self._sequence_validator = MessageSequenceValidator(mode=ValidationMode(validation_mode))

        # Initialize EventRouter with signal handling disabled by default
        # Signal handling should be opt-in via GOODINTEL_ENABLE_SIGNAL_HANDLING env var
        # or explicit configuration to avoid interfering with test runners, notebooks, etc.
        import os

        enable_signals = cast(
            bool,
            config.pop("enable_signal_handling", False)  # type: ignore[assignment]
            or os.environ.get("GOODINTEL_ENABLE_SIGNAL_HANDLING", "").lower()
            in ("1", "true", "yes"),
        )

        super().__init__(
            enable_signal_handling=enable_signals,
            _event_trace=_event_trace or False,
        )

        # Get sandbox config, defaulting to True for security
        use_sandbox = config.get("use_template_sandbox", True)

        # Import AgentMockInterface locally to avoid circular import
        from good_agent.mock import AgentMockInterface

        extensions.extend(
            [
                language_model or LanguageModel(),
                mock or AgentMockInterface(),
                tool_manager or ToolManager(),
                template_manager or TemplateManager(use_sandbox=use_sandbox),
            ]
        )

        # Register extensions after EventRouter initialization
        for extension in extensions:
            self._component_registry.register_extension(extension)

        # Validate component dependencies after all are registered
        self._component_registry.validate_component_dependencies()

        # Register any modes passed to constructor (after ToolManager is available)
        if self._pending_modes:
            for mode_def in self._pending_modes:
                if isinstance(mode_def, StandaloneMode):
                    self._mode_manager.register(mode_def)
                elif callable(mode_def):
                    # Raw handler - need to extract name from function
                    name = getattr(mode_def, "__name__", None)
                    if name:
                        self._mode_manager.register(mode_def, name=name)
                    else:
                        raise ValueError(
                            f"Cannot determine name for mode handler {mode_def}. "
                            "Use @mode('name') decorator or pass a StandaloneMode."
                        )
            self._pending_modes = None  # Clear after registration

        if system_prompt_parts:
            self.set_system_message(*system_prompt_parts)

        # Store tools for async initialization
        self._pending_tools = tools

        # Track the component installation task
        self._component_install_task: asyncio.Task[None] | None = None
        # Mirror legacy attribute for tests/back-compat
        self._component_tasks = self._component_registry._component_tasks

        # Fire the initialization event (this triggers async component installation)
        self.do(AgentEvents.AGENT_INIT_AFTER, agent=self, tools=tools)

        # Synchronously register tools if they are provided
        # This is needed because tests often expect tools to be available immediately
        # without awaiting initialize()
        if tools:
            for tool in tools:
                # Resolve name if possible
                name = None
                if isinstance(tool, str):
                    # Skip strings, they are loaded during init
                    continue

                # Check for Agent instances and use their name
                from good_agent.agent.core import Agent

                if isinstance(tool, Agent):
                    name = tool.name

                # Use cast to satisfy mypy
                tool_arg = cast(ToolLike, tool)

                try:
                    loop = asyncio.get_running_loop()
                    # We are in a loop, verify it's running
                    if loop.is_running():
                        # Schedule registration in background
                        loop.create_task(
                            self.tools.register_tool(
                                name=str(name or getattr(tool, "name", str(tool))),
                                tool=tool_arg,
                            )
                        )
                    else:
                        # Loop exists but not running? Unusual but use sync.
                        self.tools.register_tool_sync(
                            name=str(name or getattr(tool, "name", str(tool))),
                            tool=tool_arg,
                        )
                except RuntimeError:
                    # No running loop, safe to use sync version
                    self.tools.register_tool_sync(
                        name=str(name or getattr(tool, "name", str(tool))),
                        tool=tool_arg,
                    )

        self.__registry__[self._id] = weakref.ref(self)

    @property
    def state(self) -> AgentState:
        """Current state of the agent"""
        return self._state_machine.state

    @property
    def model(self) -> LanguageModel:
        return self[LanguageModel]

    @property
    def mock(self) -> AgentMockInterface:
        """Access the mock interface"""
        from good_agent.mock import AgentMockInterface

        return self[AgentMockInterface]

    @property
    def template(self) -> TemplateManager:
        """Access the template manager"""
        return self[TemplateManager]

    @property
    def tools(self) -> ToolManager:
        """Access the tool manager"""
        return self[ToolManager]

    @property
    def tool_calls(self) -> ToolExecutor:
        """Access the tool executor (deprecated).

        .. deprecated::
            Use direct Agent methods like ``agent.invoke()``, ``agent.record_invocation()``,
            or ``agent.record_invocations()`` instead.
        """
        warnings.warn(
            "agent.tool_calls is deprecated. Use agent.invoke(), agent.record_invocation(), "
            "or agent.record_invocations() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._tool_executor

    @property
    def context_manager(self) -> ContextManager:
        """Access the context manager (deprecated).

        .. deprecated::
            Use direct Agent methods like ``agent.fork()``, ``agent.fork_context()``,
            ``agent.thread_context()``, or ``agent.context_provider()`` instead.
        """
        warnings.warn(
            "agent.context_manager is deprecated. Use agent.fork(), agent.fork_context(), "
            "agent.thread_context(), or agent.context_provider() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._context_manager

    @property
    def events(self) -> Self:
        """Backwards-compatible alias returning self.

        Agent inherits from EventRouter, so all event methods are available
        directly on the Agent instance. This property exists for code that
        uses ``agent.events.apply(...)`` - it now just returns ``self``.
        """
        return self

    @property
    def versioning(self) -> AgentVersioningManager:
        """Access the versioning manager."""
        return self._versioning_manager

    @property
    def modes(self) -> ModeManager:
        """Mode management facade (``agent.modes``).

        Use ``@agent.modes('name')`` to register modes and
        ``async with agent.modes['name']:`` to enter them.
        """
        return self._mode_manager

    @property
    def mode(self) -> ModeAccessor:
        """Access current mode information (``agent.mode``).

        Provides access to mode state and info from within mode handlers.
        This is the preferred way to access mode state in agent-centric handlers.

        Example:
            @agent.modes('research')
            async def research_mode(agent: Agent):
                agent.mode.state['topic'] = 'quantum'
                print(f"In mode: {agent.mode.name}")

        Returns:
            ModeAccessor providing access to current mode state
        """
        return self._mode_accessor

    @property
    def console(self) -> AgentConsole:
        """Rich console output for CLI and telemetry (``agent.console``).

        Provides a unified interface for outputting structured information
        during agent execution, supporting multiple backends.

        Example:
            agent.console.info("Processing request")
            agent.console.tool_call("search", {"query": "test"})
            agent.console.success("Task complete!")

            with agent.console.spinner("Working..."):
                # long operation
                pass

        Returns:
            AgentConsole for structured output
        """
        return self._console

    @property
    def prompt(self) -> SystemPromptManager:
        """System prompt management (``agent.prompt``).

        Provides dynamic system prompt composition with mode-scoped changes
        and auto-restore on mode exit.

        Example:
            @agent.modes('research')
            async def research_mode(agent: Agent):
                # These changes are restored when mode exits
                agent.prompt.append("Focus on citations.")
                agent.prompt.sections['mode'] = "RESEARCH MODE"

                # This change persists after mode exit
                agent.prompt.append("Always be thorough.", persist=True)

        Returns:
            SystemPromptManager for dynamic prompt composition
        """
        return self._system_prompt_manager

    @property
    def current_mode(self) -> str | None:
        """Get the current active mode name (top of stack)."""
        return self._mode_manager.current_mode

    @property
    def mode_stack(self) -> list[str]:
        """Get list of active modes (bottom to top)."""
        return self._mode_manager.mode_stack

    def in_mode(self, mode_name: str) -> bool:
        """Check if mode is active (anywhere in stack).

        Args:
            mode_name: Mode name to check

        Returns:
            True if mode is in stack
        """
        return self._mode_manager.in_mode(mode_name)

    async def enter_mode(self, mode_name: str, **params: Any) -> None:
        """Enter a mode directly without using the context manager helper."""

        await self._mode_manager.enter_mode(mode_name, **params)

    async def exit_mode(self) -> None:
        """Exit the current mode directly."""

        await self._mode_manager.exit_mode()

    def schedule_mode_switch(self, mode_name: str, **params: Any) -> None:
        """Schedule switching to a different mode before the next call."""

        self._mode_manager.schedule_mode_switch(mode_name, **params)

    def schedule_mode_exit(self) -> None:
        """Schedule exiting the current mode before the next call."""

        self._mode_manager.schedule_mode_exit()

    @property
    def tasks(self) -> AgentTaskManager:
        """Task orchestration facade (``agent.tasks``).

        Supports ``agent.tasks.create(...)``, ``await agent.tasks.join()`` and
        exposes ``task_count``; :mod:`examples.pool.agent_pool` shows practical usage.
        """
        return self._task_manager

    @property
    def id(self) -> ULID:
        """Agent's unique identifier"""
        return self._id

    @property
    def version_id(self) -> ULID:
        """Agent's version identifier (changes with modifications)"""
        return self._versioning_manager.version_id

    @property
    def name(self) -> str | None:
        """Agent's optional name"""
        return self._name

    @property
    def session_id(self) -> ULID:
        """The agent's session identifier - remains constant throughout lifetime"""
        return self._session_id

    @property
    def messages(self) -> MessageList[Message]:
        """All messages in the agent's conversation"""
        return self._message_manager.messages

    @property
    def user(self) -> FilteredMessageList[UserMessage]:
        """Filter messages to only user messages"""
        return self._message_manager.user

    @property
    def assistant(self) -> FilteredMessageList[AssistantMessage]:
        """Filter messages to only assistant messages"""
        return self._message_manager.assistant

    @property
    def tool(self) -> FilteredMessageList[ToolMessage]:
        """Filter messages to only tool messages"""
        return self._message_manager.tool

    @property
    def system(self) -> FilteredMessageList[SystemMessage]:
        """Filter messages to only system messages"""
        return self._message_manager.system

    @property
    def is_ready(self) -> bool:
        """Whether initialization completed."""
        return self._state_machine.is_ready

    @property
    def task_count(self) -> int:
        """Number of active managed tasks."""
        return self.tasks.count

    @property
    def extensions(self) -> dict[str, AgentComponent]:
        """Access extensions by name"""
        return self._component_registry.extensions

    @property
    def current_version(self) -> list[ULID]:
        """Get the current version's message IDs.

        Returns:
            List of message IDs in the current version
        """
        return self._versioning_manager.current_version

    @property
    def _version_manager(self):
        """Backward compatibility: access to the underlying version manager."""
        return self._versioning_manager._version_manager

    @property
    def _version_id(self):
        """Backward compatibility: access to version ID."""
        return self._versioning_manager._version_id

    @property
    def _versions(self):
        """Backward compatibility: access to version history."""
        return self._versioning_manager._versions

    def revert_to_version(self, version_index: int) -> None:
        """Revert the agent's messages to a specific version.

        This is non-destructive - it creates a new version with the content
        of the target version rather than deleting newer versions.

        Args:
            version_index: The version index to revert to
        """
        self.versioning.revert_to_version(version_index)

    @property
    def vars(self) -> AgentContext:
        """Runtime variables for templates.

        A key-value store for template variables and runtime context.

        Example:
            agent.vars['user_name'] = 'Alice'
            agent.vars['session_id'] = '12345'

        Returns:
            AgentContext instance for storing template variables
        """
        return self._context

    @property
    def context(self) -> AgentContext:
        """Runtime context store for agent variables.

        .. deprecated::
            Use ``agent.vars`` instead.

        Returns:
            AgentContext instance for storing template variables
        """
        warnings.warn(
            "agent.context is deprecated, use agent.vars instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._context

    def isolated(self, truncate_at: int | None = None, **fork_kwargs) -> ForkContext:
        """Create an isolated session where all changes are discarded on exit.

        Creates a complete fork of the agent for isolated operations.
        When the context exits, the forked agent is discarded - no changes
        persist to the original agent.

        Args:
            truncate_at: Optional index to truncate messages at
            **fork_kwargs: Additional arguments to pass to fork()

        Returns:
            ForkContext instance to use with async with

        Example:
            async with agent.isolated() as sandbox:
                await sandbox.call("Try something risky")
                # All changes discarded when exiting
        """
        return self._context_manager.fork_context(truncate_at, **fork_kwargs)

    def branch(self, truncate_at: int | None = None) -> ThreadContext:
        """Create a conversation branch where new messages are preserved.

        Allows temporary modifications to the conversation (like truncation)
        while preserving any new messages added during the context.
        On exit, original messages are restored but new additions are kept.

        Args:
            truncate_at: Optional index to truncate messages at

        Returns:
            ThreadContext instance to use with async with

        Example:
            async with agent.branch(truncate_at=5) as branched:
                response = await branched.call("Summarize the above")
                # After exit: original messages + new response preserved
        """
        return self._context_manager.thread_context(truncate_at)

    def fork_context(self, truncate_at: int | None = None, **fork_kwargs) -> ForkContext:
        """Create a fork context for isolated operations.

        .. deprecated::
            Use ``agent.isolated()`` instead.

        Args:
            truncate_at: Optional index to truncate messages at
            **fork_kwargs: Additional arguments to pass to fork()

        Returns:
            ForkContext instance to use with async with
        """
        warnings.warn(
            "agent.fork_context() is deprecated, use agent.isolated() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._context_manager.fork_context(truncate_at, **fork_kwargs)

    def thread_context(self, truncate_at: int | None = None) -> ThreadContext:
        """Create a thread context for temporary modifications.

        .. deprecated::
            Use ``agent.branch()`` instead.

        Args:
            truncate_at: Optional index to truncate messages at

        Returns:
            ThreadContext instance to use with async with
        """
        warnings.warn(
            "agent.thread_context() is deprecated, use agent.branch() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._context_manager.thread_context(truncate_at)

    async def initialize(self) -> None:
        """Perform initialization and wait until the agent is ready."""
        # If already ready, return immediately
        if self._state_machine.is_ready:
            return

        # Track if we did any initialization
        did_initialization = False

        # First, ensure component installation completes
        if hasattr(self, "_component_install_task") and self._component_install_task:
            await self._component_install_task
            did_initialization = True
        elif hasattr(self, "_install_components"):
            # If no task was created (no event loop in __init__), install now
            await self._install_components()
            did_initialization = True

        # Load MCP servers if configured (do this regardless of tools)
        mcp_servers = self.config.mcp_servers
        if mcp_servers:
            try:
                # Add timeout to prevent hanging on MCP server loading
                await asyncio.wait_for(
                    self[ToolManager].load_mcp_servers(mcp_servers),
                    timeout=5.0,  # 5 second timeout
                )
                did_initialization = True
            except TimeoutError:
                logger.warning("Timeout loading MCP servers after 5 seconds")
            except Exception as e:
                logger.warning(f"Failed to load MCP servers: {e}")

        # If we have pending tools, initialize them now
        if hasattr(self, "_pending_tools") and self._pending_tools:
            tools = self._pending_tools
            self._pending_tools = ()  # Clear to avoid re-initialization
            did_initialization = True

            # Process tools directly (same logic as _agent_init handler)
            tool_patterns = []
            direct_tools = []

            for tool in tools:
                if isinstance(tool, str):
                    tool_patterns.append(tool)
                else:
                    direct_tools.append(tool)

            # Load pattern-based tools from registry
            if tool_patterns:
                try:
                    await asyncio.wait_for(
                        self[ToolManager].load_tools_from_patterns(tool_patterns),
                        timeout=5.0,  # 5 second timeout
                    )
                except TimeoutError:
                    logger.warning("Timeout loading tools from patterns after 5 seconds")

            # Register direct tools
            for direct_tool in direct_tools:
                if hasattr(direct_tool, "_tool_metadata"):
                    # It's already a Tool instance
                    await self[ToolManager].register_tool(direct_tool)  # type: ignore[arg-type]
                elif callable(direct_tool):
                    from good_agent.agent.tools import Tool

                    tool_instance = Tool(direct_tool)  # type: ignore[arg-type]
                    await self[ToolManager].register_tool(tool_instance)

        # Wait for all component initialization tasks to complete
        if self._component_registry._component_tasks:
            try:
                # Wait for all tasks with a reasonable timeout
                await asyncio.wait_for(
                    asyncio.gather(
                        *self._component_registry._component_tasks,
                        return_exceptions=True,
                    ),
                    timeout=10.0,
                )
                did_initialization = True
            except TimeoutError:
                logger.warning(
                    "Timeout waiting for component initialization tasks after 10 seconds"
                )
            except Exception as e:
                logger.warning(f"Error waiting for component tasks: {e}")
            finally:
                # Clear tasks list after awaiting
                self._component_registry._component_tasks.clear()

        # Now we're ready if we got here from initialization
        if not self._state_machine.is_ready and did_initialization:
            self._state_machine.update_state(AgentState.READY)
            return

        # Otherwise wait for ready event (shouldn't happen with new logic)
        try:
            await self._state_machine.wait_for_ready(timeout=10.0)
        except TimeoutError as e:
            raise TimeoutError(
                f"Agent did not become ready within 10 seconds. "
                f"Current state: {self._state_machine.state}"
            ) from e

        # Wait for managed tasks with wait_on_ready=True
        ready_tasks = self.tasks.waitable_tasks()
        if ready_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*ready_tasks, return_exceptions=True), timeout=10.0
                )
            except TimeoutError:
                logger.warning(f"Timeout waiting for {len(ready_tasks)} managed tasks to complete")
                # Don't fail initialize() due to task timeouts, just warn

        # Final check
        if not self._state_machine.is_ready:
            raise RuntimeError(
                f"Agent ready event was set but state is still {self._state_machine.state}"
            )

    async def ready(self) -> None:
        """Deprecated shim for :meth:`Agent.initialize`."""
        await self.initialize()

    @on(AgentEvents.AGENT_INIT_AFTER)
    async def _agent_init(self, ctx: EventContext[AgentInitializeParams, None]) -> None:
        """Handle agent initialization event.

        The EventContext is strongly typed:
        - ctx.parameters has type AgentInitializeParams (TypedDict)
        - ctx.output should be None (no return value expected)
        """
        # Track this task so initialize() can wait for it
        try:
            loop = asyncio.get_running_loop()
            self._component_install_task = loop.create_task(self._install_components())
        except RuntimeError:
            # No event loop, will be called from initialize() instead
            pass

        # Skip if tools will be handled by initialize()
        # This happens when tools are provided directly in constructor
        if hasattr(self, "_pending_tools") and self._pending_tools:
            return

        # Extract parameters from context with proper typing
        # Type checker knows these fields exist from AgentInitializeParams TypedDict
        ctx.parameters["agent"]
        tools = ctx.parameters["tools"]

        # If no tools, nothing to do (already marked ready in constructor)
        if not tools:
            return

        # Process tools if provided (this path is for components that add tools after construction)
        tool_patterns = []
        direct_tools = []

        for tool in tools:
            if isinstance(tool, str):
                # String patterns like "weather:*" or "tool_name"
                tool_patterns.append(tool)
            else:
                # Direct tool instances or functions
                direct_tools.append(tool)

        # Load MCP servers if configured
        mcp_servers = self.config.mcp_servers
        if mcp_servers:
            try:
                await self[ToolManager].load_mcp_servers(mcp_servers)
            except Exception as e:
                logger.warning(f"Failed to load MCP servers: {e}")

        # Load pattern-based tools from registry
        if tool_patterns:
            await self[ToolManager].load_tools_from_patterns(tool_patterns)

        # Register direct tools
        for direct_tool in direct_tools:
            if hasattr(direct_tool, "_tool_metadata"):
                # It's already a Tool instance
                await self[ToolManager].register_tool(direct_tool, replace=True)
            elif callable(direct_tool):
                # It's a function - convert to Tool
                tool_instance = Tool(direct_tool)
                await self[ToolManager].register_tool(tool_instance, replace=True)

        self.update_state(AgentState.READY)

    async def _install_components(self) -> None:
        """Install all registered components asynchronously.

        This is called during AGENT_INIT_AFTER event, after all components
        have been registered and dependencies validated.
        """
        await self._component_registry.install_components()

    def _validate_component_dependencies(self) -> None:
        """Validate that all component dependencies are satisfied.

        Raises:
            ValueError: If any component's dependencies are not met
        """
        self._component_registry.validate_component_dependencies()

    def update_state(
        self,
        state: AgentState,
    ):
        """
        Update the agent's state.

        Args:
            state: New state to set
        """
        self._state_machine.update_state(state)

    def validate_message_sequence(self, allow_pending_tools: bool = False) -> list[str]:
        """Validate the current message sequence.

        Args:
            allow_pending_tools: Whether to allow unresolved tool calls

        Returns:
            List of validation issues found (empty if valid)
        """
        return self._sequence_validator.validate_partial_sequence(
            self.messages, allow_pending_tools=allow_pending_tools
        )

    def create_task(
        self,
        coro: Coroutine[Any, Any, T],
        *,
        name: str | None = None,
        component: AgentComponent | str | None = None,
        wait_on_ready: bool = True,
        cleanup_callback: Callable[[asyncio.Task], None] | None = None,
    ) -> asyncio.Task[T]:
        """Create and track an asyncio task tied to this agent."""

        return self.tasks.create(
            coro,
            name=name,
            component=component,
            wait_on_ready=wait_on_ready,
            cleanup_callback=cleanup_callback,
        )

    def get_task_count(self) -> int:
        """Number of active managed tasks."""

        return self.task_count

    def get_task_stats(self) -> dict[str, Any]:
        """Return task statistics with component breakdowns."""

        return self.tasks.stats()

    async def wait_for_tasks(self, timeout: float | None = None) -> None:
        """Wait for all managed tasks to complete.

        Args:
            timeout: Optional timeout in seconds

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        await self.tasks.wait_for_all(timeout=timeout)

    def _append_message(self, message: Message) -> None:
        """
        Internal method to append a message to the agent's message list.

        This centralized method ensures:
        - Proper agent reference is set
        - Message is stored in global store
        - Version is updated
        - Consistent event firing

        Args:
            message: Message to append
        """
        self._message_manager._append_message(message)

    def _register_extension(self, extension: AgentComponent) -> None:
        """Register an extension component (without installing it)."""
        self._component_registry.register_extension(extension)

    def _clone_extensions_for_config(
        self, target_config: dict[str, Any], skip: set[str] | None = None
    ) -> None:
        """Clone extensions for a forked agent configuration.

        Args:
            target_config: Configuration dict to populate with cloned extensions
            skip: Optional set of extension keys to skip cloning
        """
        self._component_registry.clone_extensions_for_config(target_config, skip)

    def _track_component_task(self, component: AgentComponent, task: asyncio.Task) -> None:
        """Track a component initialization task.

        Args:
            component: Component that owns the task
            task: Async task to track
        """
        self._component_registry.track_component_task(component, task)

    async def _fork_with_messages(self, messages: list[Message]) -> Agent:
        """Helper method to fork with specific messages"""
        # Get current config
        config = self.config.as_dict()

        # Filter config to only include valid AgentConfigParameters
        valid_params = AGENT_CONFIG_KEYS
        filtered_config = {k: v for k, v in config.items() if k in valid_params}

        # Add cloned extensions
        self._clone_extensions_for_config(filtered_config)

        # Create new agent using the constructor
        new_agent = Agent(**filtered_config)

        # Copy specified messages
        for msg in messages:
            # Create new message with same content but new ID
            # We need to create a new instance to get a new ID
            msg_data = msg.model_dump(exclude={"id"})

            # Also preserve content (stored as private attr)
            msg_data["content"] = msg.content

            # Create new message of the same type
            new_msg: Message
            match msg:
                case SystemMessage():
                    new_msg = new_agent.model.create_message(**msg_data)
                case UserMessage():
                    new_msg = new_agent.model.create_message(**msg_data)
                case AssistantMessage():
                    new_msg = new_agent.model.create_message(**msg_data)
                case ToolMessage():
                    new_msg = new_agent.model.create_message(**msg_data)
                case _:
                    raise ValueError(f"Unknown message type: {type(msg).__name__}")

            # Use direct append for forking (skip event firing)
            new_msg._set_agent(new_agent)
            new_agent._messages.append(new_msg)
            put_message(new_msg)  # Store in global store

        # Set version to match source (until modified)
        new_agent._versioning_manager._version_id = self._versioning_manager._version_id
        # Forked agents get their own session_id (already set to new_agent._id)

        # Initialize version history with current state
        if new_agent._messages:
            new_agent._versioning_manager._versions = [[msg.id for msg in new_agent._messages]]

        return new_agent

    def replace_message(self, index: int, new_message: Message) -> None:
        """
        Replace a message at the given index with a new message.

        This maintains message immutability - the old message still exists
        in previous versions, but the current thread uses the new message.

        Args:
            index: Index of message to replace
            new_message: New message to insert
        """
        self._message_manager.replace_message(index, new_message)

    def set_system_message(
        self,
        *content: MessageContent,
        message: SystemMessage | None = None,
    ) -> None:
        """Set or update the system message"""
        self._message_manager.set_system_message(*content, message=message)

    @overload
    def append(self, content: Message) -> None: ...

    @overload
    def append(
        self,
        *content_parts: MessageContent,
        role: Literal["assistant"],
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        tool_calls: list[ToolCall] | None = None,
        reasoning: str | None = None,
        refusal: str | None = None,
        annotations: list[AnnotationLike] | None = None,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def append(
        self,
        *content_parts: MessageContent,
        role: Literal["tool"],
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        tool_call_id: str,
        tool_name: str | None = None,
        tool_response: ToolResponse | None = None,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def append(
        self,
        *content_parts: MessageContent,
        role: MessageRole = "user",
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> None: ...

    # @validate_call
    def append(
        self,
        *content_parts: MessageContent,
        role: MessageRole = "user",
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Append a message to the conversation

        Supports multiple content parts that will be concatenated with newlines:
        agent.append("First line", "Second line", "Third line")

        Args:
            *content_parts: Content to add to the message
            role: Message role (user, assistant, system, tool)
            context: Additional context for the message
            citations: List of citation URLs that correspond to [1], [2], etc. in content
            **kwargs: Additional message attributes
        """
        self._message_manager.append(
            *content_parts, role=role, context=context, citations=citations, **kwargs
        )

    def attach_image(
        self,
        image: ImageContentPart | str | bytes,
        *,
        text: MessageContent | None = None,
        detail: ImageDetail = "auto",
        mime_type: str | None = None,
        role: MessageRole = "user",
        **kwargs: Any,
    ) -> None:
        """Append a user-facing message that includes an image content part."""

        if isinstance(image, ImageContentPart):
            part = image
        elif isinstance(image, bytes):
            part = ImageContentPart.from_bytes(image, detail=detail, mime_type=mime_type)
        elif isinstance(image, str):
            image_str = image.strip()
            if image_str.startswith("data:"):
                part = ImageContentPart.from_base64(image_str, detail=detail, mime_type=mime_type)
            elif image_str.startswith("http://") or image_str.startswith("https://"):
                part = ImageContentPart.from_url(image_str, detail=detail)
            else:
                part = ImageContentPart.from_base64(image_str, detail=detail, mime_type=mime_type)
        else:
            raise TypeError("image must be bytes, str, or ImageContentPart instance")

        content: list[MessageContent] = []
        if text is not None:
            content.append(text)
        content.append(part)
        self.append(*content, role=role, **kwargs)

    def attach_file(
        self,
        file: FileContentPart | str,
        *,
        text: MessageContent | None = None,
        mime_type: str | None = None,
        file_name: str | None = None,
        inline: bool = False,
        role: MessageRole = "user",
        **kwargs: Any,
    ) -> None:
        """Append a user-facing message that includes a file attachment."""

        if isinstance(file, FileContentPart):
            part = file
        elif inline:
            if not isinstance(file, str):
                raise TypeError("inline file content must be provided as a string")
            part = FileContentPart.from_content(file, mime_type=mime_type, file_name=file_name)
        elif isinstance(file, str):
            part = FileContentPart.from_file_id(file, mime_type=mime_type, file_name=file_name)
        else:
            raise TypeError("file must be a str or FileContentPart instance")

        content: list[MessageContent] = []
        if text is not None:
            content.append(text)
        content.append(part)
        self.append(*content, role=role, **kwargs)

    def add_tool_response(
        self,
        content: str,
        tool_call_id: str,
        tool_name: str | None = None,
        **kwargs,
    ) -> None:
        """Add a tool response message to the conversation.

        .. deprecated:: 0.3.0
            Use ``append(content, role="tool", tool_call_id=...)`` instead.
            This method will be removed in version 1.0.0.

        Args:
            content: Tool response content
            tool_call_id: ID of the tool call this responds to
            tool_name: Optional name of the tool
            **kwargs: Additional message attributes

        Example:
            .. code-block:: python

                # Deprecated
                agent.add_tool_response("result", tool_call_id="123")

                # Use instead
                agent.append("result", role="tool", tool_call_id="123")
        """
        self.append(
            content,
            role="tool",
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            **kwargs,
        )

    async def _get_tool_definitions(self) -> list[ToolSignature] | None:
        """Get tool definitions for the LLM call.

        Returns:
            List of tool signatures or None if no tools available
        """
        return await self._llm_coordinator.get_tool_definitions()

    async def _llm_call(
        self,
        response_model: type[T_Output] | None = None,
        **kwargs: Any,
    ) -> AssistantMessage | AssistantMessageStructuredOutput:
        """Make a single LLM call without tool execution.

        Args:
            response_model: Optional structured output model
            **kwargs: Additional model parameters

        Returns:
            Assistant message response (may contain tool calls)
        """
        return await self._llm_coordinator.llm_call(response_model=response_model, **kwargs)

    @overload
    async def call(
        self,
        *content_parts: MessageContent,
        role: Literal["user", "assistant", "system", "tool"] = "user",
        response_model: None = None,
        context: dict | None = None,
        auto_execute_tools: bool = True,
        **kwargs: Any,
    ) -> AssistantMessage: ...

    @overload
    async def call(
        self,
        *content_parts: MessageContent,
        role: Literal["user", "assistant", "system", "tool"] = "user",
        response_model: type[T_Output],
        context: dict | None = None,
        auto_execute_tools: bool = True,
        **kwargs: Any,
    ) -> AssistantMessageStructuredOutput[T_Output]: ...

    @ensure_ready
    async def call(
        self,
        *content_parts: MessageContent,
        role: Literal["user", "assistant", "system", "tool"] = "user",
        response_model: type[T_Output] | None = None,
        context: dict | None = None,
        auto_execute_tools: bool = True,
        **kwargs: Any,
    ) -> AssistantMessage | AssistantMessageStructuredOutput:
        """Run a single request/response cycle and optionally loop through tools.

        Adds the provided message (if any), performs one LLM call, and optionally
        iterates execute() internally until tools finish. For streaming or manual
        control use ``execute`` instead. ``examples/agent/basic_chat.py`` shows both
        entry points side-by-side.
        """
        # Strategy: Delegate to execute() if standard tool execution is requested.
        # If manual control is needed (single call or structured output), handle setup manually.

        if auto_execute_tools and not response_model:
            # Delegate fully to execute()
            # It handles message appending, mode scheduling, and mode handlers
            final_message = None
            last_assistant_message = None

            async for message in self.execute(*content_parts, role=role, context=context, **kwargs):
                match message:
                    case AssistantMessage() | AssistantMessageStructuredOutput():
                        last_assistant_message = message

                final_message = message

            # If the last message is a tool message (e.g., max_iterations hit during tool execution),
            # return the last assistant message instead
            if not isinstance(final_message, (AssistantMessage, AssistantMessageStructuredOutput)):
                if last_assistant_message is not None:
                    return last_assistant_message
                # If we don't have any assistant message, something went wrong
                raise RuntimeError(
                    f"No assistant response received (last message type: {type(final_message)})"
                )

            # Return the final assistant message
            if final_message is None:
                raise RuntimeError("No response received from execute()")

            return final_message

        else:
            # Manual setup for single call or structured output
            skip_mode_handler = kwargs.pop(MODE_HANDLER_SKIP_KWARG, False)

            if not skip_mode_handler:
                await self._mode_manager.apply_scheduled_mode_changes()

            # Append input message if provided
            if content_parts:
                self.append(*content_parts, role=role, context=context)

            return await self._llm_call(response_model=response_model, **kwargs)

    def _is_conversation_pending(self) -> bool:
        """Check if the conversation needs another LLM response.

        Used by ModeExitBehavior.AUTO to determine whether to call the LLM
        after a mode exits.

        Returns:
            True if conversation needs LLM response, False otherwise
        """
        if not self.messages:
            return False

        last_msg = self.messages[-1]

        # Pending if last message is from user or tool (needs LLM to respond)
        if last_msg.role in ("user", "tool"):
            return True

        # Pending if assistant message has tool calls (waiting for tool results)
        if last_msg.role == "assistant":
            assistant_msg = cast(AssistantMessage, last_msg)
            if assistant_msg.tool_calls:
                return True

        return False

    async def _handle_mode_transition(self, transition: ModeTransition) -> None:
        """Apply a transition instruction returned from a mode handler."""

        params = dict(transition.parameters or {})

        if transition.transition_type == "exit":
            await self._mode_manager.exit_mode()
            return

        if transition.transition_type in {"switch", "push"}:
            if not transition.target_mode:
                raise ValueError(
                    f"Mode transition '{transition.transition_type}' requires a target mode"
                )

            if transition.transition_type == "switch":
                await self._mode_manager.exit_mode()

            await self._mode_manager.enter_mode(transition.target_mode, **params)
            return

        raise ValueError(f"Unknown mode transition type: {transition.transition_type}")

    @ensure_ready
    async def execute(
        self,
        *content_parts: MessageContent,
        role: Literal["user", "assistant", "system", "tool"] = "user",
        context: dict | None = None,
        streaming: bool = False,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> AsyncIterator[Message]:
        """Yield each Assistant/Tool message while the agent runs.

        Enables streaming UIs, custom tool approval, and iteration control; call
        ``agent.call`` for the one-shot variant. Demonstrated in
        ``examples/agent/basic_chat.py``.
        """
        if streaming:
            raise NotImplementedError("Streaming mode is not yet implemented.")

        skip_mode_handler = kwargs.pop(MODE_HANDLER_SKIP_KWARG, False)

        if not skip_mode_handler:
            await self._mode_manager.apply_scheduled_mode_changes()

        # Append input message if provided
        if content_parts:
            self.append(*content_parts, role=role, context=context)

        # Emit execute:start event
        self.do(AgentEvents.EXECUTE_BEFORE, agent=self, max_iterations=max_iterations)

        iterations = 0

        # Check and resolve any pending tool calls first

        message_index = 0
        pending_tool_calls = self._tool_executor.get_pending_tool_calls()
        if pending_tool_calls:
            logger.debug(f"Resolving {len(pending_tool_calls)} pending tool calls before execution")
            async for tool_message in self._tool_executor.resolve_pending_tool_calls():
                # Create and yield tool message for each resolved call
                tool_message._i = message_index
                message_index += 1
                yield tool_message

        while iterations < max_iterations:
            # Emit execute:iteration event
            self.do(
                AgentEvents.EXECUTE_ITERATION_BEFORE,
                agent=self,
                iteration=iterations,
                messages_count=len(self.messages),
            )

            # Call the LLM to get next response (without auto-executing tools)
            response = await self._llm_call(**kwargs)
            iterations += 1

            # Set iteration index
            response._i = message_index
            message_index += 1

            # Yield the response
            yield response

            # Check if the response has tool calls that need to be executed
            if response.tool_calls:
                # Resolve the tool calls that were just added
                async for tool_message in self._tool_executor.resolve_pending_tool_calls():
                    tool_message._i = message_index
                    message_index += 1
                    # Yield each tool response message
                    yield tool_message

                # Check for mode transitions triggered by tool calls
                if self._mode_manager.has_pending_transition():
                    from good_agent.agent.modes import ModeExitBehavior

                    exit_behavior = await self._mode_manager.apply_scheduled_mode_changes()

                    # Handle exit behavior if a mode exited
                    if exit_behavior is not None:
                        if exit_behavior == ModeExitBehavior.STOP:
                            # Don't call LLM again, end execution
                            break
                        elif (
                            exit_behavior == ModeExitBehavior.AUTO
                            and not self._is_conversation_pending()
                        ):
                            # Only continue if conversation is pending
                            break
                        # CONTINUE: fall through to next iteration

                # Continue to next iteration for another LLM call
            else:
                # No tool calls in response, execution complete
                break

        # Emit execute:complete event
        final_message = self.messages[-1] if self.messages else None
        self.do(
            AgentEvents.EXECUTE_AFTER,
            agent=self,
            iterations=iterations,
            final_message=final_message,
        )

    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    def _handle_message_append(self, ctx: EventContext[Any, Message], **_kwargs):
        message = ctx.return_value
        if message is None:
            return
        if self.config.print_messages and message.role in (
            self.config.print_messages_role or [message.role]
        ):
            self.print(message, mode=self.config.print_messages_mode)

    def copy(self, include_messages: bool = True, **config):
        return self._context_manager.copy(include_messages=include_messages, **config)

    @ensure_ready
    async def chat(
        self,
        content: MessageContent,
        display_from: int | None = None,
        prevent_double_submission: bool = True,
        context: dict[str, Any] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError("@TODO: Implement chat method for Agent class")

    def fork(
        self,
        include_messages: bool = True,
        **kwargs: Any,
    ) -> Agent:
        """
        Fork the agent into a new agent with the same configuration (or modified).

        Creates a new agent with:
        - New session_id (different from parent)
        - Same version_id (until modified)
        - Optionally copied messages (with new IDs)
        - Same or modified configuration

        Args:
            include_messages: Whether to copy messages to the forked agent
            **kwargs: Configuration overrides for the new agent
        """
        return self._context_manager.fork(include_messages, **kwargs)

    @ensure_ready
    async def spawn(
        self,
        n: int | None = None,
        prompts: list[str] | None = None,
        **configuration: Any,
    ) -> AgentPool:
        """
        Spawn multiple forks as an agent pool.

        Args:
            n: Number of agents to spawn (if prompts not provided)
            prompts: List of prompts to append to each spawned agent
            **configuration: Configuration overrides for spawned agents

        Returns:
            AgentPool containing spawned agents
        """
        return await self._context_manager.spawn(n=n, prompts=prompts, **configuration)

    def context_provider(self, name: str):
        """Register an instance-specific context provider"""
        return self._context_manager.context_provider(name)

    @ensure_ready
    async def merge(
        self,
        *agents: Self,
        method: Literal["tool_call", "interleaved"] = "tool_call",
        **kwargs: Any,
    ) -> None:
        """
        Merge multiple sub-agents into main agent thread.

        Args:
            *agents: Source agents to merge from
            method: Merge strategy:
                - "tool_call": Convert last assistant message from each agent into tool calls
                - "interleaved": Interleave all messages from source agents (not implemented)
            **kwargs: Additional merge options
        """
        await self._context_manager.merge(*agents, method=method, **kwargs)

    def get_rendering_context(
        self, additional_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Build complete context for template rendering.

        Merges all context sources in priority order and resolves
        context providers synchronously.

        Args:
            additional_context: Template-specific context to merge (highest priority)

        Returns:
            Complete resolved context dictionary
        """
        # 1. Start with config context (lowest priority)
        context = {}

        # 2. Add agent context (includes config via ChainMap)
        if self._context:
            context.update(self._context.as_dict())

        # 3. Add the agent instance itself
        context["agent"] = self

        # 4. Add additional context (highest priority - can override agent if needed)
        if additional_context:
            context.update(additional_context)

        # 5. Resolve context providers synchronously
        if self.template and hasattr(self.template, "resolve_context_sync"):
            context = self.template.resolve_context_sync(context)
        elif self.template and hasattr(self.template, "_resolve_context_sync"):
            # Fallback for private method name
            context = self.template._resolve_context_sync(context)

        return context

    async def get_rendering_context_async(
        self, additional_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Build complete context for template rendering (async version).

        Merges all context sources in priority order and resolves
        context providers asynchronously.

        Args:
            additional_context: Template-specific context to merge (highest priority)

        Returns:
            Complete resolved context dictionary
        """
        # 1. Start with config context (lowest priority)
        context = {}

        # 2. Add agent context (includes config via ChainMap)
        if self._context:
            context.update(self._context.as_dict())

        # 3. Add the agent instance itself
        context["agent"] = self

        # 4. Add additional context (highest priority - can override agent if needed)
        if additional_context:
            context.update(additional_context)

        # 5. Resolve context providers asynchronously
        if self.template and hasattr(self.template, "resolve_context"):
            context = await self.template.resolve_context(context)

        return context

    async def _render_template_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Render any Template parameters in the parameters dict.

        Args:
            parameters: Dictionary of parameters that may contain Template instances

        Returns:
            Dictionary with Template instances replaced by rendered strings
        """
        # Get full context with providers resolved using centralized method
        context = await self.get_rendering_context_async()

        # Process parameters
        rendered = {}
        for key, value in parameters.items():
            if isinstance(value, Template):
                # Render the template with resolved context
                rendered[key] = value.render(context)
            else:
                # Keep non-template values as-is
                rendered[key] = value

        return rendered

    def _coerce_tool_parameters(self, tool: Any, parameters: dict[str, Any]) -> dict[str, Any]:
        """Coerce JSON-like string values into dict/list for object/array params.

        This runs before tool execution so that Pydantic validation in the tool
        wrapper does not fail when the LLM returns JSON-encoded strings for
        object/array parameters (e.g., attributes).

        Args:
            tool: Tool instance, bound invoke function, callable, or tool name
            parameters: The parameters to coerce

        Returns:
            New parameters dict with JSON-like strings parsed where appropriate.
        """

        def _resolve_tool_for_schema(t: Any) -> Any:
            # Try to resolve to a Tool-like object that has a .model with JSON schema
            try:
                from good_agent.agent.tools import (
                    Tool as _ToolClass,
                )  # Avoid circular at top-level
            except Exception:
                _ToolClass = None  # type: ignore

            # Tool instance
            if _ToolClass is not None and isinstance(t, _ToolClass):
                return t

            # Bound invoke function created by invoke_func()
            bound_tool = getattr(t, "_bound_tool", None)
            if bound_tool is not None:
                # String name -> look up on manager
                if isinstance(bound_tool, str):
                    try:
                        return self.tools[bound_tool]
                    except Exception:
                        return None
                # Already a Tool instance
                if _ToolClass is not None and isinstance(bound_tool, _ToolClass):
                    return bound_tool
                # Callable -> wrap temporarily to inspect schema
                if callable(bound_tool) and _ToolClass is not None:
                    try:
                        return _ToolClass(bound_tool)
                    except Exception:
                        return None
                return None

            # Tool name string
            if isinstance(t, str):
                try:
                    return self.tools[t]
                except Exception:
                    return None

            # Callable (not bound-invoke)
            if callable(t) and _ToolClass is not None:
                try:
                    return _ToolClass(t)
                except Exception:
                    return None

            return None

        def _get_properties_schema(t: Any) -> dict[str, Any] | None:
            try:
                model = t.model  # Pydantic model generated from signature
                schema = model.model_json_schema()
                return schema.get("properties", {})
            except Exception:
                return None

        resolved_tool = _resolve_tool_for_schema(tool)
        props = _get_properties_schema(resolved_tool) if resolved_tool else None

        # If no schema available, fall back to heuristic parsing of JSON-looking strings
        def _maybe_parse(value: Any, expected_type: str | None) -> Any:
            if not isinstance(value, str):
                return value
            s = value.strip()
            # Only parse strings that look like JSON
            if expected_type == "object" and s.startswith("{") and s.endswith("}"):
                try:
                    parsed = orjson.loads(s)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return value
            if expected_type == "array" and s.startswith("[") and s.endswith("]"):
                try:
                    parsed = orjson.loads(s)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    return value
            # Heuristic fallback when no schema (try object/array detection)
            if expected_type is None and (
                (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]"))
            ):
                try:
                    return orjson.loads(s)
                except Exception:
                    return value
            return value

        coerced = dict(parameters)

        if props:
            for key, prop_schema in props.items():
                if key not in coerced:
                    continue
                # Skip special/internal parameters
                if key in {"_agent", "_tool_call"}:
                    continue
                expected_type = prop_schema.get("type")
                coerced[key] = _maybe_parse(coerced[key], expected_type)
        else:
            # No schema available — apply heuristic to all values
            for key, val in list(coerced.items()):
                if key in {"_agent", "_tool_call"}:
                    continue
                coerced[key] = _maybe_parse(val, None)

        return coerced

    def add_tool_invocation(
        self,
        tool: Tool | Callable | str,
        response: ToolResponse | Any,
        parameters: dict[str, Any] | None = None,
        *,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
    ) -> None:
        """Record a tool invocation via the tool execution manager."""

        self._tool_executor.record_invocation(
            tool,
            response,
            parameters,
            tool_call_id=tool_call_id,
            skip_assistant_message=skip_assistant_message,
        )

    def add_tool_invocations(
        self,
        tool: Tool | Callable | str,
        invocations: Sequence[tuple[dict[str, Any], ToolResponse | Any]],
        skip_assistant_message: bool = False,
    ) -> None:
        """Record multiple tool invocations via the tool execution manager."""

        self._tool_executor.record_invocations(
            tool,
            invocations,
            skip_assistant_message=skip_assistant_message,
        )

    @overload
    async def invoke(
        self,
        tool: Tool[..., T_FuncResp] | BoundTool[Any, Any, T_FuncResp],
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        **parameters: Any,
    ) -> ToolResponse[T_FuncResp]: ...

    @overload
    async def invoke(
        self,
        tool: str,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        **parameters: Any,
    ) -> ToolResponse: ...

    @overload
    async def invoke(
        self,
        tool: Callable[..., Awaitable[T_FuncResp]],
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        **parameters: Any,
    ) -> ToolResponse[T_FuncResp]: ...

    async def invoke(
        self,
        tool: Tool | Callable | str,
        *,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
        hide: list[str] | None = None,
        **parameters: Any,
    ) -> ToolResponse:
        """Directly invoke a tool and add messages to conversation.

        Args:
            tool: Tool instance, callable, or tool name string
            tool_name: Optional name override
            tool_call_id: Optional tool call ID (generated if not provided)
            skip_assistant_message: If True, only add tool response
            hide: List of parameter names to hide from tool definition
            **parameters: Parameters to pass to the tool

        Returns:
            ToolResponse with execution result
        """

        return await self._tool_executor.invoke(
            tool,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            skip_assistant_message=skip_assistant_message,
            hide=hide,
            **parameters,
        )

    async def invoke_many(
        self,
        invocations: Sequence[tuple[Tool | str | Callable, dict[str, Any]]],
    ) -> list[ToolResponse]:
        """Execute multiple tools in parallel.

        Args:
            invocations: Sequence of (tool, parameters) tuples

        Returns:
            List of ToolResponse objects in invocation order
        """

        return await self._tool_executor.invoke_many(invocations)

    def invoke_func(
        self,
        tool: Tool | str | Callable,
        *,
        tool_name: str | None = None,
        hide: list[str] | None = None,
        tool_call_id: str | None = None,
        **bound_parameters: Any,
    ) -> Callable[..., Awaitable[ToolResponse]]:
        """Create a bound function that invokes a tool with preset parameters."""

        return self._tool_executor.invoke_func(
            tool,
            tool_name=tool_name,
            hide=hide,
            tool_call_id=tool_call_id,
            **bound_parameters,
        )

    def invoke_many_func(
        self,
        invocations: Sequence[tuple[Tool | str | Callable, dict[str, Any]]],
    ) -> Callable[[], Awaitable[list[ToolResponse]]]:
        """Create a bound coroutine that executes a batch of tool invocations."""

        return self._tool_executor.invoke_many_func(invocations)

    def get_pending_tool_calls(self) -> list[ToolCall]:
        """Get list of tool calls that don't have corresponding responses.

        Returns:
            List of ToolCall objects that are pending execution
        """

        return self._tool_executor.get_pending_tool_calls()

    def has_pending_tool_calls(self) -> bool:
        """Check if there are any pending tool calls.

        Returns:
            True if there are pending tool calls
        """
        return self._tool_executor.has_pending_tool_calls()

    async def resolve_pending_tool_calls(self) -> AsyncIterator[ToolMessage]:
        """Find and execute all pending tool calls in conversation.

        Yields:
            ToolMessage for each resolved tool call
        """
        async for msg in self._tool_executor.resolve_pending_tool_calls():
            yield msg

    @overload
    def __getitem__(self, key: int) -> Message: ...

    @overload
    def __getitem__(self, key: slice) -> Self: ...

    @overload
    def __getitem__(self, key: type[T_AgentComponent]) -> T_AgentComponent: ...

    def __getitem__(self, key: int | slice | type[T_AgentComponent]) -> Any:
        """
        Get item by index, slice, or component type.

        Args:
            key: Index, slice, or component type

        Returns:
            Message, Agent slice, or component
        """
        if isinstance(key, int):
            # Special handling for index 0 (system message position)
            if key == 0:
                # Return system message if exists, else None with warning
                if self._messages:
                    match self._messages[0]:
                        case SystemMessage() as system_msg:
                            return system_msg
                        case _:
                            import warnings

                            warnings.warn(
                                "No system message set. messages[0] is None",
                                UserWarning,
                                stacklevel=2,
                            )
                            return None
                else:
                    import warnings

                    warnings.warn(
                        "No system message set. messages[0] is None",
                        UserWarning,
                        stacklevel=2,
                    )
                    return None
            else:
                # For non-zero indices, handle the virtual indexing system
                # where index 1 = first non-system message, etc.
                if key > 0:
                    # Calculate actual index in message list
                    has_system = False
                    if self._messages:
                        match self._messages[0]:
                            case SystemMessage():
                                has_system = True
                            case _:
                                has_system = False

                    if has_system:
                        # Normal indexing (system at 0, user messages at 1+)
                        return self.messages[key]
                    else:
                        # No system message, so index 1 maps to messages[0]
                        return self.messages[key - 1]
                else:
                    # Negative indexing - delegate directly
                    return self.messages[key]
        elif isinstance(key, slice):
            # Fork with sliced messages
            _agent = self.fork(include_messages=False)

            for message in self._messages[key]:
                if isinstance(message, SystemMessage):
                    # System messages are handled via set_system_message
                    _agent.set_system_message(message)
                else:
                    _agent.append(message)
            return _agent

        else:
            # Component type access (e.g., agent[CitationIndex])
            if isinstance(key, type) and issubclass(key, AgentComponent):
                extension = self._component_registry.get_extension_by_type(key)
                if extension is None:
                    raise KeyError(f"Extension {key.__name__} not found in agent")
                return extension
            else:
                raise TypeError(f"Invalid key type for agent access: {type(key)}")

    def __setitem__(
        self,
        key: int | slice | list[int],
        value: Message | list[Message] | Sequence[Message],
    ) -> None:
        """
        Set messages at specific indices. Only accepts message assignments.

        This method supports:
        - Single index assignment: agent[0] = SystemMessage("New system")
        - Slice assignment: agent[1:3] = [msg1, msg2]
        - List index assignment: agent[[1, 3, 5]] = [msg1, msg2, msg3]

        Args:
            key: Index, slice, or list of indices to set
            value: Message or list of messages to set

        Raises:
            TypeError: If trying to assign non-message values
            ValueError: If number of values doesn't match number of indices
        """
        # Normalize value to a list
        if isinstance(value, Message):
            values = [value]
        elif isinstance(value, (list, tuple)):
            values = list(value)
        else:
            raise TypeError(
                f"Can only assign Message objects or lists of Messages, got {type(value).__name__}"
            )

        # Validate all values are Messages
        for v in values:
            if not isinstance(v, Message):
                raise TypeError(f"All values must be Message objects, got {type(v).__name__}")

        # Normalize key to a list of indices
        if isinstance(key, int):
            indices = [key]
        elif isinstance(key, slice):
            # Convert slice to list of indices
            start, stop, step = key.indices(len(self._messages))
            indices = list(range(start, stop, step))
        elif isinstance(key, list):
            indices = key
        else:
            raise TypeError(f"Key must be int, slice, or list[int], got {type(key).__name__}")

        # Validate indices are within bounds
        for idx in indices:
            if idx < 0:
                # Handle negative indexing
                idx = len(self._messages) + idx
            if idx < 0 or idx >= len(self._messages):
                raise IndexError(f"Index {idx} out of range for {len(self._messages)} messages")

        # Check if we have the right number of values
        if len(indices) != len(values):
            raise ValueError(
                f"Number of values ({len(values)}) must match number of indices ({len(indices)})"
            )

        # Replace messages at the specified indices
        for idx, msg in zip(indices, values, strict=False):
            # Handle negative indexing
            if idx < 0:
                idx = len(self._messages) + idx

            # Use replace_message for proper handling
            self.replace_message(idx, msg)

    def __len__(self) -> int:
        """
        Return the number of messages in the agent.
        """
        return len(self.messages)

    def __iter__(self) -> Iterator[Message]:
        """
        Iterate over all messages in the agent.
        """
        return iter(self.messages)

    def __or__(self, other: Agent) -> Conversation:
        """
        Create a conversation between this agent and another using the | operator.

        Args:
            other: Another Agent to converse with

        Returns:
            Conversation context manager

        Usage:
            async with agent_one | agent_two as conversation:
                # Assistant messages from one agent become user messages in the other
                agent_one.append(AssistantMessage("Hello"))
        """
        from good_agent.agent.conversation import Conversation

        return Conversation(self, other)

    async def __aenter__(self) -> Agent:
        """
        Async context manager entry. Returns self.

        Usage:
            async with Agent("System prompt") as agent:
                agent.append("Test message")
                # Tasks will be automatically cleaned up on exit
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Async context manager exit. Ensures all pending tasks are cleaned up.

        This automatically calls events.join() to wait for all EventRouter tasks to complete,
        preventing "Task was destroyed but it is pending!" warnings.
        """
        # Cancel init task if still running
        if self._state_machine._init_task and not self._state_machine._init_task.done():
            self._state_machine._init_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._state_machine._init_task

        # Cancel managed tasks
        await self.tasks.cancel_all()

        await self.join()

    def get_token_count(
        self,
        include_system: bool = True,
        include_tools: bool = True,
        messages: Sequence[Message] | None = None,
    ) -> int:
        """Get total token count for agent messages.

        Args:
            include_system: Whether to include system messages in count
            include_tools: Whether to include tool call tokens
            messages: Optional subset of messages to count. If None, counts all messages.

        Returns:
            Total token count across specified messages
        """

        from good_agent.utilities.tokens import get_message_token_count

        # Use provided messages or all agent messages
        msgs = messages if messages is not None else self.messages

        # Filter messages if needed
        if not include_system:
            msgs = [m for m in msgs if m.role != "system"]

        # Sum token counts for all messages
        total = 0
        for msg in msgs:
            total += get_message_token_count(
                message=msg,
                model=self.config.model,
                include_tools=include_tools,
            )

        return total

    def get_token_count_by_role(
        self,
        include_tools: bool = True,
    ) -> dict[str, int]:
        """Get token counts broken down by message role.

        Args:
            include_tools: Whether to include tool call tokens

        Returns:
            Dictionary mapping role to token count
        """

        from good_agent.utilities.tokens import get_message_token_count

        counts: dict[str, int] = {
            "system": 0,
            "user": 0,
            "assistant": 0,
            "tool": 0,
        }

        for msg in self.messages:
            token_count = get_message_token_count(
                message=msg,
                model=self.config.model,
                include_tools=include_tools,
            )
            counts[msg.role] = counts.get(msg.role, 0) + token_count

        return counts

    @property
    def token_count(self) -> int:
        """Get total token count for all messages in agent.

        This is a convenience property that counts all messages including
        system messages and tool calls.

        Returns:
            Total token count
        """
        return self.get_token_count(include_system=True, include_tools=True)

    # def __len__(self) -> int:
    #     """Return total token count for all messages in agent.

    #     This is a convenience method that counts all messages including
    #     system messages and tool calls.

    #     Returns:
    #         Total token count
    #     """
    #     return self.get_token_count(include_system=True, include_tools=True)

    def _update_version(self) -> None:
        """Update the agent's version ID when state changes."""
        self._versioning_manager.update_version()

    def __bool__(self):
        """Agent is always truthy - avoids __len__ conflict."""
        return True
