import asyncio
import functools
import logging
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
    TypedDict,
    TypeGuard,
    TypeVar,
    Union,
    Unpack,
    cast,
    overload,
)

import orjson
from ulid import ULID

from good_agent.core.types import URL
from good_agent.core.event_router import EventContext, EventRouter, on
from good_agent.core.ulid_monotonic import (
    create_monotonic_ulid,
)

from .agent_managers.components import ComponentRegistry
from .agent_managers.llm import LLMCoordinator
from .agent_managers.messages import MessageManager
from .agent_managers.state import AgentState, AgentStateMachine
from .agent_managers.tools import ToolExecutor
from .config_types import AGENT_CONFIG_KEYS, AgentOnlyConfig, LLMCommonConfig

if TYPE_CHECKING:
    from litellm.utils import Choices

from .components import AgentComponent
from .config import AgentConfigManager
from .context import Context as AgentContext
from .events import (  # Import typed event parameters
    AgentEvents,
    AgentInitializeParams,
)
from .messages import (
    Annotation,
    AssistantMessage,
    AssistantMessageStructuredOutput,
    FilteredMessageList,
    Message,
    MessageContent,
    MessageList,
    MessageRole,
    SystemMessage,
    T_Output,
    ToolMessage,
    UserMessage,
)
from .mock import AgentMockInterface
from .model.llm import LanguageModel
from .pool import AgentPool
from .store import put_message
from .templating import (
    Template,
    TemplateManager,
    global_context_provider,
)
from .tools import (
    BoundTool,
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolManager,
    ToolResponse,
    ToolSignature,
)
from .utilities import print_message
from .validation import MessageSequenceValidator, ValidationMode

if TYPE_CHECKING:
    from .conversation import Conversation

logger = logging.getLogger(__name__)

type FilterPattern = str

P_Message = TypeVar("P_Message", bound=Message)


class AgentConfigParameters(LLMCommonConfig, AgentOnlyConfig, TypedDict, total=False):
    # Merge of LLM parameters and agent-only configuration
    temperature: float
    max_tokens: int
    max_retries: int
    fallback_models: list[str]
    tools: Sequence[str | Callable[..., Any] | ToolCallFunction]
    # extensions: NotRequired[list[AgentComponent | type[AgentComponent]]]


T_AgentComponent = TypeVar("T_AgentComponent", bound=AgentComponent)

ToolFuncParams = ParamSpec("ToolFuncParams")
T_FuncResp = TypeVar("T_FuncResp")


def _is_choices_instance(obj: Any) -> TypeGuard["Choices"]:
    """Type guard to check if an object is a Choices instance for type narrowing.

    This allows us to keep Choices behind TYPE_CHECKING while still
    providing proper type narrowing at runtime.
    """
    # At runtime, check the class name since we can't import Choices directly
    return obj.__class__.__name__ == "Choices"


# Legacy TypedDict kept for backward compatibility
# New code should use AgentInitializeParams from event_types
class AgentInitialize(TypedDict):
    agent: "Agent"
    tools: list[str | Callable[..., Any] | ToolCallFunction]


# Type variables for decorator
T = TypeVar("T")
P = ParamSpec("P")


# Overload for async generators (methods that yield)
@overload
def ensure_ready(
    func: Callable[P, AsyncIterator[T]],
) -> Callable[P, AsyncIterator[T]]: ...


# Overload for regular async functions (methods that return)
@overload
def ensure_ready(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]: ...


def ensure_ready(func: Callable[P, Any]) -> Callable[P, Any]:
    """
    Decorator that ensures the agent is ready before executing the async method.

    This decorator automatically calls await self.ready() before executing
    the decorated method, eliminating the need for repetitive ready() calls
    at the start of each public async method.

    The decorator preserves the original function's metadata through functools.wraps,
    maintaining proper type hints, signatures, and docstrings.

    Handles both regular async functions and async generators with proper type preservation:
    - For async generators (AsyncIterator[T]), returns AsyncIterator[T]
    - For async functions (Awaitable[T]), returns Awaitable[T]

    Examples:
        @ensure_ready
        async def call(self, ...) -> Message:
            # No need for await self.ready()
            ...

        @ensure_ready
        async def execute(self, ...) -> AsyncIterator[Message]:
            # No need for await self.ready()
            yield message
    """
    import inspect

    # Check if the function is an async generator
    if inspect.isasyncgenfunction(func):
        # Create wrapper for async generators
        @functools.wraps(func)
        async def async_gen_wrapper(
            self: "Agent", *args: Any, **kwargs: Any
        ) -> AsyncIterator[Any]:
            # Ensure agent is ready before proceeding
            await self.ready()
            # Yield from the generator
            # Use getattr to bypass type checker's argument analysis
            method = getattr(func, "__call__", func)  # noqa: B004
            async for item in method(self, *args, **kwargs):  # type: ignore[misc]
                yield item

        return async_gen_wrapper  # type: ignore[return-value]
    else:
        # Create wrapper for regular async functions
        @functools.wraps(func)
        async def async_wrapper(self: "Agent", *args: Any, **kwargs: Any) -> Any:
            # Ensure agent is ready before proceeding
            await self.ready()
            # Await and return the result
            # Use getattr to bypass type checker's argument analysis
            method = getattr(func, "__call__", func)  # noqa: B004
            return await method(self, *args, **kwargs)  # type: ignore[misc]

        return async_wrapper  # type: ignore[return-value]


class Agent(EventRouter):
    """AI conversational agent with tool integration and message management.

    PURPOSE: Orchestrates LLM interactions with structured message handling, tool execution,
    and extensible event-driven architecture for building AI applications.

    ROLE: Central coordinator that manages the flow between:
    - User input → Message validation → LLM API calls → Tool execution → Response

    LIFECYCLE:
    1. Creation: Agent() creates instance with default or provided components
    2. Configuration: Set tools, templates, validation modes via constructor parameters
    3. Initialization: Async component installation via AGENT_INIT_AFTER event
    4. Execution: call() or execute() methods handle message processing
    5. Cleanup: Automatic via weakref registry, explicit via __aexit__ if needed

    THREAD SAFETY: NOT thread-safe. Use AgentPool for concurrent operations.
    Each agent instance should be used by only one async task at a time.

    TYPICAL USAGE:
    ```python
    # Basic usage
    agent = Agent(model="gpt-4", tools=[search_tool])
    response = await agent.call("Hello, how are you?")

    # With tools and templates
    agent = Agent(
        model="gpt-4",
        tools=[search_tool],
        template_path="./templates",
        message_validation_mode="strict",
    )
    response = await agent.execute()

    # Context manager for cleanup
    async with Agent(model="gpt-4") as agent:
        response = await agent.call("Query here")
    ```

    EXTENSION POINTS:
    - Add tools via constructor tools parameter or agent.tools.register_tool()
    - Hook into events via agent.on(AgentEvents.EVENT_NAME)(handler)
    - Custom message validation via validation_mode parameter
    - Template customization via template_path and template_functions
    - Component system via AgentComponent base class

    STATE MANAGEMENT:
    - Agent maintains internal state during execution (AgentState enum)
    - Message history preserved in agent.messages with versioning support
    - Tool context shared across tool calls within same execution
    - Component state managed through dependency injection

    ERROR HANDLING:
    - LLM API failures: Automatic retry with exponential backoff
    - Tool execution failures: Captured and sent to LLM as error messages
    - Validation failures: Immediate ValidationError exception (mode dependent)
    - Component failures: Logged as warnings, don't stop execution
    - Resource failures: Cleanup via weakref registry and finalizers

    RELATED CLASSES:
    - LanguageModel: LLM abstraction layer
    - MessageList: Thread-safe message collection with versioning
    - ToolManager: Tool discovery and execution
    - AgentComponent: Base for extensions
    - TemplateManager: Template processing and rendering

    PERFORMANCE CHARACTERISTICS:
    - Memory: ~1-5MB base + message history (grows with conversation)
    - Initialization: 10-50ms depending on components and MCP servers
    - Execution: 500ms-3s typical, dominated by LLM API latency
    - Concurrency: Single-threaded async, use AgentPool for parallel processing
    """

    __registry__: ClassVar[dict[ULID, weakref.ref["Agent"]]] = {}

    @classmethod
    def get(cls, agent_id: ULID) -> "Agent | None":
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
    def get_by_name(cls, name: str) -> "Agent | None":
        """Retrieve an agent instance by its name (first match)"""
        for ref in cls.__registry__.values():
            agent = ref()
            if agent and agent.name == name:
                return agent
        return None

    # Convienience aliases

    EVENTS: ClassVar[type[AgentEvents]] = AgentEvents

    _init_task: asyncio.Task | None = None
    _conversation: "Conversation | None" = None
    _id: ULID
    _session_id: ULID
    _version_id: ULID
    _name: str | None = None
    _versions: list[list[ULID]] = []
    _extensions: dict[type[AgentComponent], AgentComponent]
    _extension_names: dict[str, AgentComponent]
    _agent_ref: "weakref.ref[Agent | None] | None" = None
    _messages: MessageList[Message]
    _context: AgentContext
    _config_manager: AgentConfigManager
    _language_model: LanguageModel
    _tool_manager: ToolManager
    _template_manager: TemplateManager
    _mock: AgentMockInterface
    _pool: AgentPool | None = None
    _state_machine: AgentStateMachine

    @staticmethod
    def context_providers(name: str):
        """Register a global context provider"""
        return global_context_provider(name)

    def print(
        self, message: int | Message | None = None, mode: str | None = None
    ) -> None:
        """
        Pretty print a message using rich.

        Args:
            message: Message to print (defaults to last message)
            mode: Render mode ('display', 'llm', 'raw'). If None, uses config.print_messages_mode
        """
        from .content import RenderMode

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
        _event_trace: bool | None = None,
        **config: Unpack[AgentConfigParameters],
    ):
        """Initialize agent with model, tools, and configuration.

        PURPOSE: Creates a new agent instance with specified capabilities and behavior.

        INITIALIZATION FLOW:
        1. Component Setup: Create default components if not provided
           - LanguageModel: LLM abstraction (creates default if None)
           - ToolManager: Tool discovery and execution
           - TemplateManager: Template processing and caching
           - AgentMockInterface: Testing and mocking support

        2. Core Infrastructure:
           - Message list with versioning support
           - Event router for component communication
           - Context system for template variable resolution
           - State machine for agent lifecycle management

        3. Component Registration:
           - Register provided extensions
           - Validate component dependencies
           - Set up dependency injection

        4. Async Initialization:
           - Fire AGENT_INIT_AFTER event (triggers component installation)
           - Load MCP servers if configured
           - Register tools from patterns and direct instances

        5. Final Setup:
           - Set system message if provided
           - Register in global registry for cleanup
           - Set initial state to INITIALIZING

        DEPENDENCY INJECTION:
        Components can request dependencies via:
        - Agent instance (automatic injection)
        - Other AgentComponent subclasses (type-based injection)
        - Context values via ContextValue descriptors

        SIDE EFFECTS:
        - Emits AGENT_INIT_AFTER event (triggers async component installation)
        - Registers agent in global weakref registry for cleanup
        - May create default LanguageModel from environment if none provided
        - Initializes message sequence validator
        - Sets up signal handlers if enabled (opt-in via config)

        Args:
            *system_prompt_parts: Content for initial system message.
                Multiple parts will be concatenated with newlines.
                Can include templates that will be rendered during execution.
            config_manager: Configuration manager for agent settings.
                If None, creates default from provided config parameters.
            language_model: Language model for LLM interactions.
                If None, creates default from environment configuration.
                Must support async completion and tool calling.
            tool_manager: Tool discovery and execution manager.
                If None, creates default manager with no initial tools.
            agent_context: Context system for template variable resolution.
                If None, creates default context chainmap.
            template_manager: Template processing and caching system.
                If None, creates default with sandboxing enabled.
            mock: Mock interface for testing and development.
                If None, creates default mock implementation.
            extensions: List of AgentComponent instances for custom functionality.
                Components are automatically registered and dependencies validated.
            _event_trace: Enable detailed event tracing for debugging.
                If None, uses default from config or False.
            **config: Additional agent configuration parameters.
                See AgentConfigParameters for full list of options.
                Common options include model, temperature, max_tokens, tools, etc.

        PERFORMANCE NOTES:
        - Constructor is synchronous and fast (~1-5ms)
        - Async component installation happens after constructor returns
        - Use await agent.ready() to wait for full initialization
        - Component discovery and installation can take 10-50ms

        COMMON PITFALLS:
        - Don't share agent instances between async tasks (not thread-safe)
        - Ensure model supports required operations before passing to agent
        - Tool functions must be async if they perform I/O operations
        - Components with circular dependencies will raise ValueError
        - MCP server loading can hang - use timeouts in production

        EXAMPLES:
        ```python
        # Basic agent with default model
        agent = Agent()

        # Agent with custom model and tools
        agent = Agent(
            model="gpt-4", tools=[search_tool, calculator_tool], temperature=0.7
        )

        # Agent with system message and extensions
        agent = Agent(
            "You are a helpful assistant.",
            "Be concise and accurate.",
            extensions=[custom_extension],
            message_validation_mode="strict",
        )
        ```

        RELATED:
        - Use await agent.ready() to wait for complete initialization (or use with async context manager)
        - See AgentComponent for creating custom extensions
        - See AgentPool for managing multiple agents concurrently
        - See ToolManager.register_tool() for adding tools after construction
        """
        extensions = extensions or []
        self.config = config_manager or AgentConfigManager(**config)
        self.config._set_agent(self)  # Set agent reference for version updates
        self.context = agent_context or AgentContext()
        self.context._set_agent_config(self.config)

        tools: Sequence[str | Callable[..., Any] | ToolCallFunction] = (
            config.pop("tools", []) or []
        )

        # Initialize message list
        self._messages = MessageList[Message]()
        self._messages._set_agent(self)

        # Initialize identifiers
        self._id = create_monotonic_ulid()
        self._session_id = (
            self._id
        )  # Session ID starts as agent ID, but can be overridden
        self._version_id = create_monotonic_ulid()
        self._name: str | None = None
        self._versions: list[list[ULID]] = []

        # Initialize versioning infrastructure
        from .versioning import MessageRegistry, VersionManager

        self._message_registry = MessageRegistry()
        self._version_manager = VersionManager()

        # Enable versioning for messages
        self._messages._init_versioning(
            self._message_registry, self._version_manager, self
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

        # Task management for Agent.create_task()
        self._managed_tasks: dict[asyncio.Task, dict[str, Any]] = {}
        self._task_stats = {
            "total": 0,
            "pending": 0,
            "completed": 0,
            "failed": 0,
        }

        # Initialize message sequence validator
        validation_mode = config.get("message_validation_mode", "warn")
        self._sequence_validator = MessageSequenceValidator(
            mode=ValidationMode(validation_mode)
        )

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

        if system_prompt_parts:
            self.set_system_message(*system_prompt_parts)

        # Store tools for async initialization
        self._pending_tools = tools

        # Track the component installation task
        self._component_install_task = None

        # Fire the initialization event (this triggers async component installation)
        self.do(AgentEvents.AGENT_INIT_AFTER, agent=self, tools=tools)

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
    def id(self) -> ULID:
        """Agent's unique identifier"""
        return self._id

    @property
    def version_id(self) -> ULID:
        """Agent's version identifier (changes with modifications)"""
        return self._version_id

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
    def extensions(self) -> dict[str, AgentComponent]:
        """Access extensions by name"""
        return self._component_registry.extensions

    @property
    def current_version(self) -> list[ULID]:
        """Get the current version's message IDs.

        Returns:
            List of message IDs in the current version
        """
        return self._version_manager.current_version

    def revert_to_version(self, version_index: int) -> None:
        """Revert the agent's messages to a specific version.

        This is non-destructive - it creates a new version with the content
        of the target version rather than deleting newer versions.

        Args:
            version_index: The version index to revert to
        """
        # Revert the version manager
        self._version_manager.revert_to(version_index)

        # Sync the message list with the new version
        self._messages._sync_from_version()

        # Update version ID to indicate change
        self._version_id = create_monotonic_ulid()

        logger.debug(f"Agent {self._id} reverted to version {version_index}")

    def fork_context(self, truncate_at: int | None = None, **fork_kwargs):
        """Create a fork context for isolated operations.

        Args:
            truncate_at: Optional index to truncate messages at
            **fork_kwargs: Additional arguments to pass to fork()

        Returns:
            ForkContext instance to use with async with

        Example:
            async with agent.fork_context(truncate_at=5) as forked:
                response = await forked.call("Summarize")
                # Response only exists in fork
        """
        from .thread_context import ForkContext

        return ForkContext(self, truncate_at, **fork_kwargs)

    def thread_context(self, truncate_at: int | None = None):
        """Create a thread context for temporary modifications.

        Args:
            truncate_at: Optional index to truncate messages at

        Returns:
            ThreadContext instance to use with async with

        Example:
            async with agent.thread_context(truncate_at=5) as ctx_agent:
                response = await ctx_agent.call("Summarize")
                # After context, agent has original messages + response
        """
        from .thread_context import ThreadContext

        return ThreadContext(self, truncate_at)

    async def ready(self) -> None:
        """
        Wait for the agent to be ready for operations.

        This method blocks until the agent has completed initialization and
        is in a READY state or higher. If already ready, returns immediately.
        """
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
            self._pending_tools = None  # Clear to avoid re-initialization
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
                    logger.warning(
                        "Timeout loading tools from patterns after 5 seconds"
                    )

            # Register direct tools
            for direct_tool in direct_tools:
                if hasattr(direct_tool, "_tool_metadata"):
                    # It's already a Tool instance
                    await self[ToolManager].register_tool(direct_tool)
                elif callable(direct_tool):
                    from .tools import Tool

                    tool_instance = Tool(direct_tool)
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
        ready_tasks = [
            task
            for task, info in self._managed_tasks.items()
            if info.get("wait_on_ready", True)
        ]
        if ready_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*ready_tasks, return_exceptions=True), timeout=10.0
                )
            except TimeoutError:
                logger.warning(
                    f"Timeout waiting for {len(ready_tasks)} managed tasks to complete"
                )
                # Don't fail ready() due to task timeouts, just warn

        # Final check
        if not self._state_machine.is_ready:
            raise RuntimeError(
                f"Agent ready event was set but state is still {self._state_machine.state}"
            )

    @on(AgentEvents.AGENT_INIT_AFTER)
    async def _agent_init(self, ctx: EventContext[AgentInitializeParams, None]) -> None:
        """Handle agent initialization event.

        The EventContext is strongly typed:
        - ctx.parameters has type AgentInitializeParams (TypedDict)
        - ctx.output should be None (no return value expected)
        """
        # Track this task so ready() can wait for it
        try:
            loop = asyncio.get_running_loop()
            self._component_install_task = loop.create_task(self._install_components())
        except RuntimeError:
            # No event loop, will be called from ready() instead
            pass

        # Skip if tools will be handled by ready() method
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
        component: Union["AgentComponent", str, None] = None,
        wait_on_ready: bool = True,
        cleanup_callback: Callable[[asyncio.Task], None] | None = None,
    ) -> asyncio.Task[T]:
        """Drop-in replacement for asyncio.create_task() with automatic management.

        Args:
            coro: The coroutine to execute
            name: Optional task name for debugging
            component: Component that created this task (for tracking)
            wait_on_ready: Whether ready() should wait for this task
            cleanup_callback: Optional callback when task completes

        Returns:
            Standard asyncio.Task that can be awaited
        """
        # Create the task
        task = asyncio.create_task(coro, name=name)

        # Track task metadata
        component_name = None
        if component is not None:
            if hasattr(component, "__class__"):
                component_name = component.__class__.__name__
            else:
                component_name = str(component)

        task_info = {
            "component": component_name,
            "wait_on_ready": wait_on_ready,
            "cleanup_callback": cleanup_callback,
            "created_at": asyncio.get_event_loop().time(),
        }
        self._managed_tasks[task] = task_info

        # Update stats
        self._task_stats["total"] += 1
        self._task_stats["pending"] += 1

        # Set up cleanup callback
        def _cleanup_task(t: asyncio.Task) -> None:
            # Remove from tracking
            if t in self._managed_tasks:
                task_info = self._managed_tasks.pop(t)
                self._task_stats["pending"] -= 1

                # Update completion stats
                if t.cancelled():
                    pass  # Don't count cancelled tasks
                elif t.exception():
                    self._task_stats["failed"] += 1
                    # Log the exception but don't raise
                    logger.warning(f"Task {t.get_name()} failed: {t.exception()}")
                else:
                    self._task_stats["completed"] += 1

                # Run custom cleanup callback if provided
                if task_info.get("cleanup_callback"):
                    try:
                        task_info["cleanup_callback"](t)
                    except Exception as e:
                        logger.warning(f"Task cleanup callback failed: {e}")

        task.add_done_callback(_cleanup_task)
        return task

    def get_task_count(self) -> int:
        """Get the number of active managed tasks."""
        return len(self._managed_tasks)

    def get_task_stats(self) -> dict[str, Any]:
        """Get detailed task statistics."""
        stats = dict(self._task_stats)

        # Add breakdown by component
        by_component = {}
        by_wait_on_ready = {"true": 0, "false": 0}

        for task_info in self._managed_tasks.values():
            # Count by component
            component = task_info.get("component", "unknown")
            by_component[component] = by_component.get(component, 0) + 1

            # Count by wait_on_ready
            wait_key = "true" if task_info.get("wait_on_ready", True) else "false"
            by_wait_on_ready[wait_key] += 1

        stats["by_component"] = by_component
        stats["by_wait_on_ready"] = by_wait_on_ready

        return stats

    async def wait_for_tasks(self, timeout: float | None = None) -> None:
        """Wait for all managed tasks to complete.

        Args:
            timeout: Optional timeout in seconds

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        if not self._managed_tasks:
            return

        tasks = list(self._managed_tasks.keys())
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout)

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

    def _track_component_task(
        self, component: AgentComponent, task: asyncio.Task
    ) -> None:
        """Track a component initialization task.

        Args:
            component: Component that owns the task
            task: Async task to track
        """
        self._component_registry.track_component_task(component, task)

    async def _fork_with_messages(self, messages: list[Message]) -> "Agent":
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
        new_agent._version_id = self._version_id
        # Forked agents get their own session_id (already set to new_agent._id)

        # Initialize version history with current state
        if new_agent._messages:
            new_agent._versions = [[msg.id for msg in new_agent._messages]]

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
        annotations: list[Annotation] | None = None,
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

    def add_tool_response(
        self,
        content: str,
        tool_call_id: str,
        tool_name: str | None = None,
        **kwargs,
    ) -> None:
        """Add a tool response message to the conversation"""
        self._message_manager.add_tool_response(
            content, tool_call_id, tool_name=tool_name, **kwargs
        )

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
        return await self._llm_coordinator.llm_call(
            response_model=response_model, **kwargs
        )

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
        """Call the agent with optional input and get a response.

        PURPOSE: High-level interface for single-turn agent interactions with automatic
        tool execution and structured output support. Simplifies common use cases.

        WHEN TO USE:
        - Simple question-answer interactions
        - Single message processing with automatic tool execution
        - Structured data extraction via response_model
        - When you want the final result, not intermediate steps

        EXECUTION STRATEGY:
        1. Input Processing: Append user message if provided
        2. Tool Execution Decision:
           - auto_execute_tools=True: Use execute() for full tool loop
           - auto_execute_tools=False: Use single _llm_call() (raw LLM response)
           - response_model provided: Always use single call with structured output
        3. Response Collection: Return final assistant message or structured output

        TOOL EXECUTION BEHAVIOR:
        - When auto_execute_tools=True: Automatically executes all tool calls and
          continues until LLM provides final response without tools
        - When auto_execute_tools=False: Returns initial response even if it contains
          tool calls (useful for manual tool execution control)
        - Tool execution follows same patterns as execute() method

        STRUCTURED OUTPUT:
        When response_model is provided, forces single LLM call with structured output:
        - Ignores auto_execute_tools parameter
        - Uses model.extract() instead of model.complete()
        - Returns AssistantMessageStructuredOutput[T_Output]
        - Tool calls in structured output are not executed

        STATE TRANSITIONS:
        - READY → PENDING_RESPONSE → PROCESSING → COMPLETE
        - If auto_execute_tools=True: May loop through PENDING_TOOLS state
        - Agent state automatically managed during execution

        SIDE EFFECTS:
        - Appends input message to agent.messages if provided
        - Appends assistant response and any tool messages to agent.messages
        - Updates agent.version_id for each message added
        - Emits agent execution events (same as execute() method)
        - Increments usage statistics and token counts

        ERROR HANDLING:
        - Message validation failures: Immediate ValidationError (mode dependent)
        - LLM API failures: Automatic retry with exponential backoff
        - Tool execution failures: Error messages sent to LLM, execution continues
        - Structured output failures: ValidationError if parsing fails
        - Network timeouts: Propagated after retry exhaustion

        PERFORMANCE:
        - Latency: Single LLM call + tool execution time (if enabled)
        - Throughput: Lower than execute() due to response collection overhead
        - Memory: Message history grows with conversation length
        - Optimal for: Short interactions, simple queries, structured extraction

        Args:
            *content_parts: Message content to append before calling.
                Multiple parts concatenated with newlines. Can include templates.
                If omitted, uses existing message history.
            role: Role of the input message (default: "user").
                Use "system" for system messages, "assistant" for few-shot examples,
                "tool" for tool responses (rarely used manually).
            response_model: Pydantic model for structured output extraction.
                When provided, forces single LLM call with structured parsing.
                Tool calls in structured output are not executed.
                Type: BaseModel subclass
            context: Additional context variables for template rendering.
                Merged with agent context during message processing.
                Useful for dynamic template variables.
            auto_execute_tools: Whether to automatically execute tool calls.
                True (default): Execute tools and return final response
                False: Return initial response even with tool calls
                Ignored when response_model is provided
            **kwargs: Additional model parameters passed to LLM.
                Common options: temperature, max_tokens, top_p, stop, etc.
                See model documentation for provider-specific options.

        Returns:
            AssistantMessage: Final response from the language model.
                Contains text content and optionally tool call results.
                Tool execution results are incorporated into response content.

            AssistantMessageStructuredOutput[T_Output]: When response_model provided.
                Contains parsed structured output in .output field.
                Tool calls in structured responses are not executed.

        Raises:
            ValidationError: Message sequence invalid or structured output parsing fails
            LLMError: Language model API failures after retries
            ToolError: Critical tool failures that prevent continuation
            AgentStateError: Agent in invalid state for execution
            RuntimeError: No assistant response received (internal error)

        TYPICAL USAGE:
        ```python
        # Simple question answering
        response = await agent.call("What's the weather like today?")
        print(response.content)

        # With manual tool control
        response = await agent.call("Search for recent news", auto_execute_tools=False)
        if response.tool_calls:
            # Manually handle tool calls
            await agent.execute_tools(response.tool_calls)

        # Structured data extraction
        from pydantic import BaseModel


        class WeatherInfo(BaseModel):
            temperature: float
            conditions: str
            location: str


        weather = await agent.call(
            "What's the weather in Tokyo?", response_model=WeatherInfo
        )
        print(f"Temperature: {weather.output.temperature}")

        # With context and custom parameters
        response = await agent.call(
            "Summarize this for a {audience}",
            context={"audience": "technical audience"},
            temperature=0.1,  # More deterministic
            max_tokens=500,
        )
        ```

        PERFORMANCE TIPS:
        - Use auto_execute_tools=False for manual tool control or debugging
        - Set response_model for structured data extraction (more reliable than parsing)
        - Use context parameter for dynamic template variables
        - Monitor agent.usage for token consumption analysis

        RELATED:
        - execute(): Full execution loop with streaming support
        - execute_stream(): Streaming version for real-time output
        - append(): Add messages without execution
        - ready(): Ensure agent is initialized before calling
        """
        # Append input message if provided
        if content_parts:
            self.append(*content_parts, role=role, context=context)

        # If auto_execute_tools is False or we have structured output,
        # use the simple single-call approach
        if not auto_execute_tools or response_model:
            return await self._llm_call(response_model=response_model, **kwargs)

        # Otherwise, use execute() to handle tool calls automatically
        final_message = None
        last_assistant_message = None
        async for message in self.execute(**kwargs):
            match message:
                case AssistantMessage() | AssistantMessageStructuredOutput():
                    last_assistant_message = message

            final_message = message

        # If the last message is a tool message (e.g., max_iterations hit during tool execution),
        # return the last assistant message instead
        if not isinstance(
            final_message, (AssistantMessage, AssistantMessageStructuredOutput)
        ):
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

    @ensure_ready
    async def execute(
        self,
        streaming: bool = False,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> AsyncIterator[Message]:
        """Execute the agent and yield messages as they are generated.

        PURPOSE: Core execution loop that handles multi-turn conversations with tool
        execution, message streaming, and iterative LLM interactions.

        WHEN TO USE:
        - Complex multi-turn conversations requiring tool support
        - When you need access to intermediate messages and tool responses
        - For streaming real-time output to users
        - When you want full control over the execution process
        - Prefer call() for simple single-message interactions

        EXECUTION FLOW:
        1. INITIALIZATION: Check for pending tool calls from previous executions
        2. ITERATION LOOP (while iterations < max_iterations):
           a. LLM Call: Send current message history to language model
           b. Response Processing: Parse tool calls from LLM response
           c. Tool Execution: Execute tools concurrently if tool calls present
           d. Message Yielding: Yield each generated message (LLM response + tool responses)
           e. Continuation Decision: Continue if tools executed, else break
        3. COMPLETION: Emit completion event with execution summary

        STATE TRANSITIONS:
        READY → PENDING_RESPONSE → PROCESSING → PENDING_TOOLS → PROCESSING → COMPLETE

        Agent.state follows this pattern throughout execution:
        - PENDING_RESPONSE: About to call LLM
        - PROCESSING: LLM call in progress
        - PENDING_TOOLS: Tool calls detected, about to execute
        - READY: Execution complete or iteration limit reached

        TOOL EXECUTION STRATEGY:
        - Tools execute concurrently using asyncio.gather()
        - Individual tool failures don't stop other tool execution
        - Tool responses automatically added to message history
        - Tool execution isolated with proper error handling
        - Tool context shared across calls within same execution

        ITERATION CONTROL:
        - max_iterations prevents infinite loops (default: 10)
        - Each iteration = one LLM call + optional tool execution
        - Execution stops when LLM returns response without tool calls
        - Use agent.events to monitor iteration progress

        STREAMING SUPPORT:
        - streaming parameter enables real-time message streaming
        - Messages yielded as soon as they're generated
        - Useful for chat interfaces and real-time updates
        - Does not affect token usage or execution logic

        SIDE EFFECTS:
        - Appends assistant response to agent.messages
        - Appends tool response messages for each tool execution
        - Updates agent.state throughout execution process
        - Emits events at each major step (see AgentEvents)
        - May execute tools with external side effects
        - Increments usage statistics and token counts
        - Updates agent.version_id for each message added

        ERROR HANDLING:
        - LLM API failures: Automatic retry with exponential backoff (3 attempts)
        - Tool execution failures: Continue execution, send error messages to LLM
        - Validation failures: Immediate ValidationError (mode dependent)
        - Network errors: Propagated after retries exhausted
        - Timeout errors: Configurable via model.timeout parameter
        - Iteration limit exceeded: Execution stops, returns last messages

        CONCURRENCY AND PERFORMANCE:
        - Method is NOT thread-safe - one execution per agent instance
        - Tool calls within single iteration may run concurrently
        - LLM calls are sequential (one per iteration)
        - Memory usage grows with message history length
        - Typical execution: 500ms-3s depending on LLM and tools
        - Optimal iteration count: 3-5 for most use cases

        RESOURCE MANAGEMENT:
        - HTTP connections: Reused across LLM calls and tool execution
        - Tool execution: Context managers ensure resource cleanup
        - Message history: Versioned and persisted in global store
        - Event handling: Non-blocking, handler failures don't stop execution

        Args:
            streaming: Enable streaming mode for real-time message delivery.
                When True, messages are yielded immediately as they're generated.
                When False (default), behavior is the same but allows future optimization.
                Does not affect the actual execution logic or message sequence.
            max_iterations: Maximum number of LLM-tool cycles.
                Prevents infinite loops when LLM keeps calling tools.
                Default: 10 iterations (sufficient for most use cases).
                Each iteration includes one LLM call and optional tool execution.
            **kwargs: Additional model parameters passed to LLM.
                Common options: temperature, max_tokens, top_p, stop, etc.
                Provider-specific parameters also supported.
                See model documentation for complete parameter list.

        Yields:
            Message: Messages generated during execution in chronological order.
                Sequence pattern: AssistantMessage → [ToolMessage]* → AssistantMessage → ...
                Each message includes metadata like iteration index and execution timing.
                Tool messages contain execution results and error information.
                Assistant messages may contain tool calls for the next iteration.

        Events Emitted:
        - EXECUTE_BEFORE: Start of execution with max_iterations
        - EXECUTE_ITERATION_BEFORE: Start of each iteration with iteration count
        - MESSAGE_APPEND_AFTER: Each message added to conversation
        - TOOL_CALL_BEFORE/AFTER: Individual tool execution lifecycle
        - EXECUTE_AFTER: Execution completion with final summary
        - AGENT_STATE_CHANGE: State transitions during execution

        Raises:
            ValidationError: Message sequence invalid (strict mode only)
            LLMError: Language model API failures after retries
            ToolError: Critical tool failures that prevent continuation
            AgentStateError: Agent in invalid state for execution
            RuntimeError: Internal errors during execution

        TYPICAL USAGE:
        ```python
        # Basic execution with streaming
        async for message in agent.execute(streaming=True):
            if isinstance(message, AssistantMessage):
                print(f"Assistant: {message.content}")
            elif isinstance(message, ToolMessage):
                print(f"Tool result: {message.content[:100]}...")

        # Execute with custom iteration limit
        async for message in agent.execute(max_iterations=5):
            # Process each message
            pass

        # Execute with custom model parameters
        async for message in agent.execute(temperature=0.1, max_tokens=1000):
            # More deterministic responses
            pass

        # Collect all messages from execution
        messages = []
        async for message in agent.execute():
            messages.append(message)


        # Handle execution with event monitoring
        def on_state_change(ctx):
            print(f"State: {ctx.params['old_state']} → {ctx.params['new_state']}")


        agent.on(AgentEvents.AGENT_STATE_CHANGE)(on_state_change)
        async for message in agent.execute():
            pass
        ```

        PERFORMANCE TIPS:
        - Monitor agent.state to track execution progress
        - Use max_iterations to prevent excessive loops
        - Set appropriate timeouts for long-running tools
        - Consider message truncation for long conversations
        - Use agent.events for debugging and monitoring

        DEBUGGING:
        - Set agent.debug = True for detailed execution logging
        - Monitor agent.messages to see full conversation history
        - Use agent.events to track execution progress step-by-step
        - Check agent.usage for token consumption analysis
        - Use streaming=True for real-time debugging output

        RELATED:
        - call(): Simplified single-message interface
        - call_stream(): Streaming version of call()
        - execute_stream(): Alternative streaming interface
        - ready(): Ensure agent is initialized before execution
        - validate(): Run validation without execution
        """
        # Emit execute:start event
        self.do(AgentEvents.EXECUTE_BEFORE, agent=self, max_iterations=max_iterations)

        iterations = 0

        # Check and resolve any pending tool calls first

        message_index = 0
        if pending_tool_calls := self.get_pending_tool_calls():
            logger.debug(
                f"Resolving {len(pending_tool_calls)} pending tool calls before execution"
            )
            async for tool_message in self.resolve_pending_tool_calls():
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
                async for tool_message in self.resolve_pending_tool_calls():
                    tool_message._i = message_index
                    message_index += 1
                    # Yield each tool response message
                    yield tool_message
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
    def _handle_message_append(self, ctx: EventContext[Any, Message], **kwargs):
        assert ctx.output
        message = ctx.output
        if self.config.print_messages and message.role in (
            self.config.print_messages_role or [message.role]
        ):
            self.print(ctx.output, mode=self.config.print_messages_mode)

    def copy(self, include_messages: bool = True, **config):
        _copy = self.__class__(**config)

        if len(self.system) > 0 and not include_messages:
            _copy.set_system_message(self.system[0])

        if include_messages:
            for message in self._messages:
                # Create a copy of each message
                msg_copy = message.model_copy()  # does this work?
                msg_copy._set_agent(_copy)
                _copy.append(msg_copy)

        return _copy

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
    ) -> "Agent":
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
        # Get current config and update with kwargs
        config = self.config.as_dict()
        config.update(kwargs)

        # Filter config to only include valid AgentConfigParameters
        valid_params = AGENT_CONFIG_KEYS
        filtered_config = {k: v for k, v in config.items() if k in valid_params}

        override_keys = {
            key
            for key in kwargs
            if key
            in {
                "language_model",
                "mock",
                "tool_manager",
                "template_manager",
                "extensions",
            }
        }
        self._clone_extensions_for_config(filtered_config, override_keys)

        # Create new agent using the constructor
        new_agent = Agent(**filtered_config)

        # Copy messages if requested
        if include_messages:
            for msg in self._messages:
                # Create new message with same content but new ID
                # We need to create a new instance to get a new ID
                msg_data = msg.model_dump(exclude={"id", "role"})

                # Preserve content_parts directly to avoid triggering render
                # which would cause event loop conflicts in async contexts
                if hasattr(msg, "content_parts"):
                    msg_data["content_parts"] = msg.content_parts

                # Create new message of the same type and add via proper methods
                match msg:
                    case SystemMessage():
                        # Use set_system_message for system messages
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="system"
                        )
                        new_agent.set_system_message(new_msg)
                    case UserMessage():
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="user"
                        )
                        new_agent.append(new_msg)
                    case AssistantMessage():
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="assistant"
                        )
                        new_agent.append(new_msg)
                    case ToolMessage():
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="tool"
                        )
                        new_agent.append(new_msg)
                    case _:
                        raise ValueError(f"Unknown message type: {type(msg).__name__}")

        # Set version to match source (until modified)
        new_agent._version_id = self._version_id

        # Initialize version history with current state
        if new_agent._messages:
            new_agent._versions = [[msg.id for msg in new_agent._messages]]

        # Emit agent:fork event
        # @TODO: event naming
        self.do(
            AgentEvents.AGENT_FORK_AFTER,
            parent=self,
            child=new_agent,
            config_changes=kwargs,
        )

        return new_agent

    @ensure_ready
    async def spawn(
        self,
        n: int | None = None,
        prompts: list[str] | None = None,
        **configuration: Any,
    ) -> "AgentPool":
        """
        Spawn multiple forks as an agent pool.

        Args:
            n: Number of agents to spawn (if prompts not provided)
            prompts: List of prompts to append to each spawned agent
            **configuration: Configuration overrides for spawned agents

        Returns:
            AgentPool containing spawned agents
        """
        # Determine number of agents
        if prompts:
            num_agents = len(prompts)
        elif n:
            num_agents = n
        else:
            raise ValueError("Either 'n' or 'prompts' must be provided")

        # Create agents
        agents = []
        for i in range(num_agents):
            # Fork the agent with optional config overrides
            agent = self.fork(**configuration)

            # Add prompt if provided
            if prompts and i < len(prompts):
                agent.append(prompts[i])

            agents.append(agent)

        # Return as pool
        return AgentPool(agents)

    def context_provider(self, name: str):
        """Register an instance-specific context provider"""
        return self.template.context_provider(name)

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
        if not agents:
            return

        # Emit merge start event
        # @TODO: event naming - should be AGENT_MERGE_START
        self.do(
            AgentEvents.AGENT_MERGE_AFTER,
            target=self,
            sources=list(agents),
            strategy=method,
            result=None,
        )

        if method == "tool_call":
            await self._merge_as_tool_calls(*agents, **kwargs)
        elif method == "interleaved":
            raise NotImplementedError("Interleaved merge strategy not yet implemented")
        else:
            raise ValueError(f"Unknown merge method: {method}")

        # Update version after merge
        self._update_version()

        # Emit merge complete event
        # @TODO: event naming - should be AGENT_MERGE_COMPLETE
        self.do(
            AgentEvents.AGENT_MERGE_AFTER,
            target=self,
            sources=list(agents),
            strategy=method,
            result="success",
        )

    async def _merge_as_tool_calls(self, *agents: Self, **kwargs: Any) -> None:
        """
        Merge agents by converting their last assistant messages to tool calls.

        This creates a single assistant message with multiple tool calls, followed by
        tool response messages for each merged agent.
        """

        tool_calls = []
        tool_responses = []

        for i, agent in enumerate(agents):
            # Find the last assistant message in the source agent
            last_assistant = None
            for msg in reversed(agent.messages):
                match msg:
                    case AssistantMessage() as assistant_msg:
                        last_assistant = assistant_msg
                        break
                    case _:
                        continue

            if last_assistant is None:
                # Skip agents with no assistant messages
                continue

            # Create a virtualized tool call from the assistant message
            tool_call_id = f"merge_{ULID()}"
            tool_name = f"agent_merge_{i}"

            # Use the assistant message content as the tool arguments
            arguments = {
                "agent_id": str(agent.id),
                "content": last_assistant.content,
                "reasoning": getattr(last_assistant, "reasoning", None),
                "citations": getattr(last_assistant, "citations", None),
            }

            tool_call = ToolCall(
                id=tool_call_id,
                type="function",
                function=ToolCallFunction(
                    name=tool_name, arguments=orjson.dumps(arguments).decode("utf-8")
                ),
            )
            tool_calls.append(tool_call)

            # Create tool response
            tool_response = ToolResponse(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                response=last_assistant.content,
                parameters=arguments,
                success=True,
                error=None,
            )

            tool_message = self.model.create_message(
                # content=str(tool_response.response or ""),
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                response=tool_response,
                role="tool",
            )
            tool_responses.append(tool_message)

        if tool_calls:
            # Add assistant message with tool calls
            assistant_message = self.model.create_message(
                content="Merging results from sub-agents",
                tool_calls=tool_calls,
                role="assistant",
            )
            self.append(assistant_message)

            # Add tool response messages
            for tool_message in tool_responses:
                self.append(tool_message)

    def _resolve_tool_name(self, tool: Tool | Callable | str) -> str:
        """
        Resolve tool to its name.

        Args:
            tool: Tool instance, callable, or tool name string

        Returns:
            str: The tool name
        """
        if isinstance(tool, str):
            return tool
        elif isinstance(tool, Tool):
            return tool._tool_metadata.name
        elif callable(tool):
            return getattr(tool, "__name__", str(tool))
        else:
            raise ValueError(
                f"Tool must be a string name, Tool instance, or callable function, got {type(tool)}"
            )

    def _convert_to_tool_response(
        self,
        response: ToolResponse | Any,
        tool_name: str,
        tool_call_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> ToolResponse:
        """
        Convert response to ToolResponse if needed.

        Args:
            response: The response to convert
            tool_name: Name of the tool
            tool_call_id: Tool call ID
            parameters: Parameters passed to the tool

        Returns:
            ToolResponse: Converted or original ToolResponse
        """
        if not isinstance(response, ToolResponse):
            # Create ToolResponse from arbitrary response
            return ToolResponse(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                response=response,
                parameters=parameters if parameters is not None else {},
                success=True,
                error=None,
            )
        else:
            # Use existing ToolResponse, potentially updating fields
            return ToolResponse(
                tool_name=response.tool_name or tool_name,
                tool_call_id=response.tool_call_id or tool_call_id,
                response=response.response,
                parameters=response.parameters if parameters is None else parameters,
                success=response.success,
                error=response.error,
            )

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
        if self.context:
            context.update(self.context.as_dict())

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
        if self.context:
            context.update(self.context.as_dict())

        # 3. Add the agent instance itself
        context["agent"] = self

        # 4. Add additional context (highest priority - can override agent if needed)
        if additional_context:
            context.update(additional_context)

        # 5. Resolve context providers asynchronously
        if self.template and hasattr(self.template, "resolve_context"):
            context = await self.template.resolve_context(context)

        return context

    async def _render_template_parameters(
        self, parameters: dict[str, Any]
    ) -> dict[str, Any]:
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

    def _coerce_tool_parameters(
        self, tool: Any, parameters: dict[str, Any]
    ) -> dict[str, Any]:
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
        import orjson  # Local import to avoid overhead on module import

        def _resolve_tool_for_schema(t: Any) -> Any:
            # Try to resolve to a Tool-like object that has a .model with JSON schema
            try:
                from .tools import Tool as _ToolClass  # Avoid circular at top-level
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
            if expected_type is None:
                if (s.startswith("{") and s.endswith("}")) or (
                    s.startswith("[") and s.endswith("]")
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
        tool_call_id: str | None = None,
        skip_assistant_message: bool = False,
    ) -> None:
        """
        Add a tool invocation record to the agent's message history.

        This method records that a tool was invoked without actually executing it.
        It's useful when you want to record tool usage that happened outside the agent.

        Args:
            tool: Tool instance, callable, or tool name string
            response: The ToolResponse from the tool execution, or any response that will be converted to ToolResponse
            parameters: Parameters that were passed to the tool (visible params only)
            tool_call_id: Optional tool call ID (generated if not provided)
            skip_assistant_message: If True, only add tool response (for when assistant message already exists)
        """
        # Resolve tool name
        tool_name = self._resolve_tool_name(tool)

        # Generate tool call ID if not provided
        if tool_call_id is None:
            tool_call_id = f"call_{ULID()}"

        # Convert response to ToolResponse if needed
        tool_response = self._convert_to_tool_response(
            response, tool_name, tool_call_id, parameters
        )

        # Use provided parameters or extract from response
        if parameters is None:
            parameters = tool_response.parameters

        # Check if we need to add an assistant message with tool call
        if not skip_assistant_message:
            # Look for existing assistant message with this tool call
            existing_tool_call = False
            for msg in reversed(self._messages):
                match msg:
                    case AssistantMessage(tool_calls=tool_calls) if tool_calls:
                        for tc in tool_calls:
                            if tc.id == tool_call_id:
                                existing_tool_call = True
                                break
                        if existing_tool_call:
                            break
                    case _:
                        continue

            # Only add assistant message if tool call doesn't exist
            if not existing_tool_call:
                # Create tool call
                tool_call = ToolCall(
                    id=tool_call_id,
                    type="function",
                    function=ToolCallFunction(
                        name=tool_name,
                        arguments=orjson.dumps(parameters).decode("utf-8"),
                    ),
                )

                # Add assistant message with tool call
                assistant_msg = self.model.create_message(
                    content="",  # Empty content for tool-only message
                    tool_calls=[tool_call],
                    role="assistant",
                )
                self.append(assistant_msg)
        tool_message_content = (
            tool_response.response.render()
            if hasattr(tool_response.response, "render")
            else str(tool_response.response)
        )

        # Create tool message with response
        tool_msg = self.model.create_message(
            content=tool_message_content
            if tool_response.success
            else f"Error: {tool_response.error}",
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_response=tool_response,
            role="tool",
        )
        self.append(tool_msg)

        # Emit tool:response event
        # @TODO: event naming
        self.do(
            AgentEvents.TOOL_CALL_AFTER,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            response=tool_response,
            success=tool_response.success,
        )

    def add_tool_invocations(
        self,
        tool: Tool | Callable | str,
        invocations: Sequence[tuple[dict[str, Any], ToolResponse | Any]],
        skip_assistant_message: bool = False,
    ) -> None:
        """
        Add multiple tool invocation records to the agent's message history.

        If the model supports parallel function calling, all invocations will be
        consolidated into a single AssistantMessage with multiple tool calls.
        Otherwise, falls back to individual messages per invocation.

        Args:
            tool: Tool instance, callable, or tool name string
            invocations: Sequence of (parameters, response) tuples
            skip_assistant_message: If True, only add tool responses (for when assistant message already exists)
        """
        if not invocations:
            return

        # Resolve tool name once for all invocations
        tool_name = self._resolve_tool_name(tool)

        # Check if model supports parallel function calling
        supports_parallel = self.model.supports_parallel_function_calling()

        # Prepare tool calls and their IDs
        tool_call_ids = []
        tool_calls = []

        if not skip_assistant_message:
            if supports_parallel:
                # Build all tool calls for consolidation
                for parameters, _ in invocations:
                    tool_call_id = f"call_{ULID()}"
                    tool_call_ids.append(tool_call_id)

                    tool_call = ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(
                            name=tool_name,
                            arguments=orjson.dumps(parameters).decode("utf-8"),
                        ),
                    )
                    tool_calls.append(tool_call)

                # Add single AssistantMessage with all tool calls
                assistant_msg = self.model.create_message(
                    content="",  # Tool calls typically have empty content
                    tool_calls=tool_calls,
                    role="assistant",
                )
                self.append(assistant_msg)
            else:
                # Fall back to individual messages per invocation
                for parameters, response in invocations:
                    self.add_tool_invocation(
                        tool=tool,
                        response=response,
                        parameters=parameters,
                        skip_assistant_message=False,
                    )
                return  # Exit early since add_tool_invocation handles everything
        else:
            # When skipping assistant message, still need to generate IDs
            for _ in invocations:
                tool_call_ids.append(f"call_{ULID()}")

        # Add tool response messages
        for i, (parameters, response) in enumerate(invocations):
            # Use the corresponding tool call ID
            tool_call_id = tool_call_ids[i] if tool_call_ids else f"call_{ULID()}"

            # Convert response to ToolResponse if needed
            tool_response = self._convert_to_tool_response(
                response, tool_name, tool_call_id, parameters
            )

            # Create tool message
            tool_msg = self.model.create_message(
                content=str(tool_response.response)
                if tool_response.success
                else f"Error: {tool_response.error}",
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_response=tool_response,
                role="tool",
            )
            self.append(tool_msg)

            # Emit tool:response event
            # @TODO: event naming
            self.do(
                AgentEvents.TOOL_CALL_AFTER,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                response=tool_response,
                success=tool_response.success,
            )

    def _resolve_tool(
        self,
        tool_name: str | None,
        tool: Tool | Callable | str,
        hide: list[str] | None = None,
    ):
        if isinstance(tool, str):
            if tool not in self.tools:
                raise ValueError(f"Tool '{tool}' not found in agent's tools")
            tool_instance = self.tools[tool]
            if isinstance(tool_instance, Tool):
                resolved_tool = tool_instance
                resolved_name = tool_name if tool_name is not None else tool
            else:
                # Convert callable to Tool if needed
                resolved_tool = Tool(tool_instance)
                resolved_name = tool_name if tool_name is not None else tool
        elif isinstance(tool, Tool):
            # It's a Tool instance
            resolved_tool = tool
            resolved_name = (
                tool_name
                if tool_name is not None
                else resolved_tool._tool_metadata.name
            )
        elif callable(tool):
            # It's a function - convert to Tool with hide parameter
            resolved_tool = Tool(tool, hide=hide)
            resolved_name = tool_name if tool_name is not None else resolved_tool.name
        else:
            raise ValueError(
                f"Tool must be a string name, Tool instance, or callable function, got {type(tool)}"
            )

        return resolved_tool, resolved_name

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
        **bound_parameters: Any,
    ) -> Callable[..., Awaitable[ToolResponse]]:
        """
        Create a bound function that invokes a tool with pre-set parameters.

        Args:
            tool: Tool instance, tool name, or callable
            tool_name: Optional name to override the inferred tool name
            hide: List of parameter names to hide from the tool definition
            **bound_parameters: Parameters to bind to the tool

        Returns:
            Async function that accepts additional parameters and invokes the tool
        """

        resolved_name = tool_name

        if not tool_name:
            if isinstance(tool, str):
                resolved_name = tool
            elif isinstance(tool, Tool):
                resolved_name = tool.name
            elif callable(tool):
                resolved_name = getattr(tool, "__name__", str(tool))
            logger.debug(f"Resolved tool name: {resolved_name}")

        async def bound_invoke(**kwargs):
            # Check if we're being called from invoke_many (special parameter)
            from_invoke_many = kwargs.pop("_from_invoke_many", False)

            # Merge bound parameters with call-time parameters
            all_params = {**bound_parameters, **kwargs}

            if from_invoke_many:
                # When called from invoke_many, just execute the tool directly
                # WITHOUT creating messages (invoke_many handles that)
                actual_tool = tool
                if isinstance(tool, str):
                    try:
                        actual_tool = self.tools[tool]
                    except KeyError:
                        raise ValueError(f"Tool '{tool}' not found") from None
                elif not isinstance(tool, Tool):
                    actual_tool = Tool(tool)

                assert callable(actual_tool), "Resolved tool is not callable"

                # Execute the tool directly
                result = await actual_tool(**all_params, _agent=self)

                # Convert to ToolResponse if needed
                from good_agent.tools import ToolResponse as ToolResp

                if not isinstance(result, ToolResp):
                    result = ToolResp(
                        tool_name=resolved_name
                        or getattr(actual_tool, "name", str(tool)),
                        tool_call_id="",  # Will be set by invoke_many
                        response=result,
                        parameters=all_params,
                        success=True,
                        error=None,
                    )
                return result
            else:
                # Normal invoke - creates messages
                return await self.invoke(
                    tool, tool_name=resolved_name, hide=hide, **all_params
                )

        # bound_invoke.__name__ = resolved_name
        bound_invoke.__name__ = resolved_name
        # Mark this as a bound function from invoke_func (custom attributes for runtime introspection)
        bound_invoke._is_invoke_func_bound = True  # type: ignore[attr-defined]
        bound_invoke._bound_tool = tool  # type: ignore[attr-defined]
        bound_invoke._bound_parameters = bound_parameters  # type: ignore[attr-defined]
        bound_invoke._hide_params = hide  # type: ignore[attr-defined]

        return bound_invoke

    def invoke_many_func(
        self,
        invocations: Sequence[tuple[Tool | str | Callable, dict[str, Any]]],
    ) -> Callable[[], Awaitable[list[ToolResponse]]]:
        """
        Create a bound function that executes a batch of tool invocations.

        Args:
            invocations: Sequence of (tool, parameters) tuples

        Returns:
            Async function that executes the batch when called
        """

        async def bound_invoke_many():
            return await self.invoke_many(invocations)

        return bound_invoke_many

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

    # async def resolve_pending_tool_calls(self) -> list[ToolResponse]:
    #     """
    #     Find and execute all pending tool calls in the conversation.

    #     This method finds tool calls in assistant messages that don't have
    #     corresponding tool response messages and executes them.

    #     Returns:
    #         List of ToolResponse objects for resolved calls
    #     """
    #     pending = self.get_pending_tool_calls()
    #     responses = []

    #     for tool_call in pending:
    #         tool_name = tool_call.function.name

    #         if tool_name not in self.tools:
    #             # Create error response for missing tool
    #             logger.warning(f"Tool '{tool_name}' not found for pending tool call {tool_call.id}")

    #             # Create error response
    #             tool_response = ToolResponse(
    #                 tool_name=tool_name,
    #                 tool_call_id=tool_call.id,
    #                 response=None,
    #                 parameters=tool_call.parameters,  # Use the built-in parameters property
    #                 success=False,
    #                 error=f"Tool '{tool_name}' not found",
    #             )

    #             # Create and add tool message for the error
    #             tool_message = self.model.create_message(
    #                 content=f"Error: {tool_response.error}",
    #                 tool_call_id=tool_call.id,
    #                 tool_name=tool_name,
    #                 tool_response=tool_response,
    #                 role="tool",
    #             )
    #             self.append(tool_message)

    #             # Emit error event for consistency
    #             self.do(
    #                 AgentEvents.TOOL_CALL_ERROR,
    #                 tool_name=tool_name,
    #                 tool_call_id=tool_call.id,
    #                 error=tool_response.error,
    #                 parameters=tool_call.parameters,
    #             )
    #         else:
    #             # Check if the JSON arguments are valid before attempting to invoke
    #             try:
    #                 # Try to parse the arguments directly to detect invalid JSON
    #                 orjson.loads(tool_call.function.arguments)

    #                 # Use the centralized invoke method
    #                 # Use ToolCall's built-in parameters property instead of manual parsing
    #                 tool_response = await self.invoke(
    #                     tool_name,
    #                     tool_call_id=tool_call.id,
    #                     skip_assistant_message=True,  # Assistant message with tool call already exists
    #                     **tool_call.parameters  # Use the built-in property that handles JSON parsing
    #                 )
    #             except orjson.JSONDecodeError as e:
    #                 # Invalid JSON in tool arguments
    #                 logger.warning(f"Invalid JSON in tool arguments for {tool_name}: {e}")

    #                 # Create error response for invalid JSON
    #                 tool_response = ToolResponse(
    #                     tool_name=tool_name,
    #                     tool_call_id=tool_call.id,
    #                     response=None,
    #                     parameters={},
    #                     success=False,
    #                     error=f"Error parsing tool arguments: {str(e)}",
    #                 )

    #                 # Create and add tool message for the error
    #                 tool_message = self.model.create_message(
    #                     content=f"Error parsing tool arguments: {str(e)}",
    #                     tool_call_id=tool_call.id,
    #                     tool_name=tool_name,
    #                     tool_response=tool_response,
    #                     role="tool",
    #                 )
    #                 self.append(tool_message)

    #                 # Emit error event for consistency
    #                 self.do(
    #                     AgentEvents.TOOL_CALL_ERROR,
    #                     tool_name=tool_name,
    #                     tool_call_id=tool_call.id,
    #                     error=f"Error parsing tool arguments: {str(e)}",
    #                     parameters={},
    #                 )

    #         responses.append(tool_response)

    #     return responses

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
                raise TypeError(
                    f"All values must be Message objects, got {type(v).__name__}"
                )

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
            raise TypeError(
                f"Key must be int, slice, or list[int], got {type(key).__name__}"
            )

        # Validate indices are within bounds
        for idx in indices:
            if idx < 0:
                # Handle negative indexing
                idx = len(self._messages) + idx
            if idx < 0 or idx >= len(self._messages):
                raise IndexError(
                    f"Index {idx} out of range for {len(self._messages)} messages"
                )

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

    def __or__(self, other: "Agent") -> "Conversation":
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
        from .conversation import Conversation

        return Conversation(self, other)

    async def __aenter__(self) -> "Agent":
        """
        Async context manager entry. Returns self.

        Usage:
            async with Agent("System prompt") as agent:
                agent.append("Test message")
                # Tasks will be automatically cleaned up on exit
        """
        await self.ready()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Async context manager exit. Ensures all pending tasks are cleaned up.

        This automatically calls join_async() to wait for all EventRouter tasks to complete,
        preventing "Task was destroyed but it is pending!" warnings.
        """
        # Cancel init task if still running
        if self._state_machine._init_task and not self._state_machine._init_task.done():
            self._state_machine._init_task.cancel()
            try:
                await self._state_machine._init_task
            except asyncio.CancelledError:
                pass

        # Cancel all managed tasks
        for task in list(self._managed_tasks.keys()):
            if not task.done():
                task.cancel()

        # Give a moment for cancellations to process
        if self._managed_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._managed_tasks.keys(), return_exceptions=True),
                    timeout=1.0,
                )
            except TimeoutError:
                logger.warning("Some managed tasks did not cancel within 1 second")

        await self.join_async()

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
        from .utilities.tokens import get_message_token_count

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
        from .utilities.tokens import get_message_token_count

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
        old_version = self._version_id
        # Use monotonic ULID generation to ensure strict ordering
        # create_monotonic_ulid() ensures monotonic ordering even within the same millisecond
        # by incrementing the random component when timestamps are identical
        self._version_id = create_monotonic_ulid()

        # Update version history
        current_message_ids = [msg.id for msg in self._messages]
        self._versions.append(current_message_ids)

        # Emit agent:version:change event
        changes = {
            "messages": len(self._messages),
            "last_version_messages": len(self._versions[-2])
            if len(self._versions) > 1
            else 0,
        }
        # @TODO: event naming
        self.do(
            AgentEvents.AGENT_VERSION_CHANGE,
            agent=self,
            old_version=old_version,
            new_version=self._version_id,
            changes=changes,
        )

    def __bool__(self):
        """Agent is always truthy - avoids __len__ conflict."""
        return True
