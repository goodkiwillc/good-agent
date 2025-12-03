from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

from good_agent.core.event_router import EventContext, on
from good_agent.events import AgentEvents

if TYPE_CHECKING:
    pass

# Type variable for handler functions
F = TypeVar("F", bound=Callable[..., Any])


@runtime_checkable
class EventRouterProtocol(Protocol):
    """Protocol defining the interface that TypedEventHandlersMixin expects."""

    def on(
        self,
        event: str | AgentEvents,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """Register an event handler."""
        ...


class TypedEventHandlersMixin(EventRouterProtocol):
    """
    Mixin class that provides type-safe event handler registration methods.

    This mixin adds convenience methods to the Agent class for registering
    event handlers with proper type hints for their EventContext parameters.

    Note: This mixin expects to be mixed with a class that implements the
    EventRouterProtocol interface (i.e., has an 'on' method).

    Example usage:
        class Agent(EventRouter, TypedEventHandlersMixin):
            ...

        agent = Agent()

        @agent.on_message_append
        def handle_message(ctx: EventContext[MessageAppendParams, None]):
            # Type checker knows ctx.parameters has MessageAppendParams fields
            message = ctx.parameters["message"]
            agent = ctx.parameters["agent"]
    """

    # ========================================================================
    # Agent Lifecycle Events
    # ========================================================================

    def on_agent_init_after(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for agent initialization completion.

        Handler signature:
            def handler(ctx: EventContext[AgentInitializeParams, None]) -> None

        Available parameters:
            - agent: The initialized Agent instance
            - tools: Optional list of tools to be loaded
        """
        return self.on(AgentEvents.AGENT_INIT_AFTER, priority=priority, predicate=predicate)

    def on_agent_state_change(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for agent state changes.

        Handler signature:
            def handler(ctx: EventContext[AgentStateChangeParams, None]) -> None

        Available parameters:
            - agent: The Agent instance
            - new_state: The new AgentState
            - old_state: The previous AgentState
        """
        return self.on(AgentEvents.AGENT_STATE_CHANGE, priority=priority, predicate=predicate)

    def on_agent_fork(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for agent forking.

        Handler signature:
            def handler(ctx: EventContext[AgentForkParams, None]) -> None

        Available parameters:
            - parent: The parent Agent
            - child: The forked Agent
            - config_changes: Optional configuration changes
        """
        return self.on(AgentEvents.AGENT_FORK_AFTER, priority=priority, predicate=predicate)

    def on_agent_version_change(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for agent version changes.

        Handler signature:
            def handler(ctx: EventContext[AgentVersionChangeParams, None]) -> None

        Available parameters:
            - agent: The Agent instance
            - old_version: Previous version ULID
            - new_version: New version ULID
            - changes: Dictionary describing what changed
        """
        return self.on(AgentEvents.AGENT_VERSION_CHANGE, priority=priority, predicate=predicate)

    # ========================================================================
    # Message Events
    # ========================================================================

    def on_message_append(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for message appending.

        Handler signature:
            def handler(ctx: EventContext[MessageAppendParams, None]) -> None

        Available parameters:
            - message: The appended Message
            - agent: The Agent instance
        """
        return self.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=priority, predicate=predicate)

    def on_message_create(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for message creation.

        Handler signature:
            def handler(ctx: EventContext[MessageCreateParams, dict]) -> dict | None

        Available parameters:
            - content: Message content
            - role: Message role (user/assistant/system/tool)
            - context: Optional context dictionary
            - citations: Optional citation URLs
            - metadata: Optional metadata

        Returns:
            Modified parameters dictionary or None
        """
        return self.on(AgentEvents.MESSAGE_CREATE_BEFORE, priority=priority, predicate=predicate)

    def on_message_replace(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for message replacement.

        Handler signature:
            def handler(ctx: EventContext[MessageReplaceParams, None]) -> None

        Available parameters:
            - index: Index of replaced message
            - message: The new Message
            - agent: The Agent instance
        """
        return self.on(AgentEvents.MESSAGE_REPLACE_AFTER, priority=priority, predicate=predicate)

    def on_message_set_system(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for system message setting.

        Handler signature:
            def handler(ctx: EventContext[MessageSetSystemParams, None]) -> None

        Available parameters:
            - message: The system Message
            - agent: The Agent instance
        """
        return self.on(AgentEvents.MESSAGE_SET_SYSTEM_AFTER, priority=priority, predicate=predicate)

    def on_message_render(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for message rendering.

        Handler signature:
            def handler(ctx: EventContext[MessageRenderParams, str]) -> str | None

        Available parameters:
            - message: The Message being rendered
            - mode: Render mode (text/llm/display)
            - context: Optional render context

        Returns:
            Modified rendered string or None
        """
        return self.on(AgentEvents.MESSAGE_RENDER_AFTER, priority=priority, predicate=predicate)

    # ========================================================================
    # LLM Events
    # ========================================================================

    def on_llm_complete(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for LLM completion.

        Handler signature:
            def handler(ctx: EventContext[LLMCompleteParams, None]) -> None

        Available parameters:
            - messages: List of message dictionaries
            - model: Model name
            - temperature: Optional temperature
            - max_tokens: Optional max tokens
            - tools: Optional tool definitions
            - response: ResponseWithUsage (after event)
        """
        return self.on(AgentEvents.LLM_COMPLETE_AFTER, priority=priority, predicate=predicate)

    def on_llm_extract(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for LLM structured extraction.

        Handler signature:
            def handler(ctx: EventContext[LLMExtractParams, Any]) -> Any | None

        Available parameters:
            - messages: List of message dictionaries
            - response_model: Pydantic model class
            - model: Model name
            - output: Extracted model instance (after event)

        Returns:
            Modified output or None
        """
        return self.on(AgentEvents.LLM_EXTRACT_AFTER, priority=priority, predicate=predicate)

    def on_llm_stream(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for LLM streaming responses.

        Handler signature:
            def handler(ctx: EventContext[LLMStreamParams, None]) -> None

        Available parameters:
            - messages: List of message dictionaries
            - model: Model name
            - temperature: Optional temperature
            - max_tokens: Optional max tokens
            - chunk: Stream chunk (for stream:chunk event)
        """
        return self.on(AgentEvents.LLM_STREAM_AFTER, priority=priority, predicate=predicate)

    def on_llm_stream_chunk(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for individual LLM stream chunks.

        Handler signature:
            def handler(ctx: EventContext[LLMStreamParams, None]) -> None

        Available parameters:
            - chunk: The stream chunk data
            - messages: Original messages
            - model: Model name
        """
        return self.on(AgentEvents.LLM_STREAM_CHUNK, priority=priority, predicate=predicate)

    def on_llm_error(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for LLM errors.

        Handler signature:
            def handler(ctx: EventContext[LLMErrorParams, None]) -> None

        Available parameters:
            - error: The exception that occurred
            - parameters: Original LLM parameters
            - agent: The Agent instance
        """
        return self.on(AgentEvents.LLM_ERROR, priority=priority, predicate=predicate)

    # ========================================================================
    # Tool Events
    # ========================================================================

    def on_tool_call_before(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for before tool calls.

        Handler signature:
            def handler(ctx: EventContext[ToolCallBeforeParams, dict]) -> dict | None

        Available parameters:
            - tool_call: Optional ToolCall object
            - tool: Optional Tool instance
            - tool_name: Optional tool name
            - arguments/parameters: Tool arguments
            - tool_call_id: Optional tool call ID
            - agent: The Agent instance

        Returns:
            Modified arguments dictionary or None
        """
        return self.on(AgentEvents.TOOL_CALL_BEFORE, priority=priority, predicate=predicate)

    def on_tool_call_after(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for after tool calls.

        Handler signature:
            def handler(ctx: EventContext[ToolCallAfterParams, None]) -> None

        Available parameters:
            - response: Tool response
            - tool_call: Optional ToolCall object
            - tool: Optional Tool instance
            - tool_name: Tool name
            - tool_call_id: Tool call ID
            - success: Whether call succeeded
            - agent: The Agent instance
        """
        return self.on(AgentEvents.TOOL_CALL_AFTER, priority=priority, predicate=predicate)

    def on_tool_call_error(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for tool call errors.

        Handler signature:
            def handler(ctx: EventContext[ToolCallErrorParams, None]) -> None

        Available parameters:
            - error: Exception or error string
            - tool_call: Optional ToolCall object
            - tool: Optional Tool instance
            - tool_name: Tool name
            - tool_call_id: Tool call ID
            - parameters: Tool parameters
            - agent: The Agent instance
        """
        return self.on(AgentEvents.TOOL_CALL_ERROR, priority=priority, predicate=predicate)

    # ========================================================================
    # Execution Events
    # ========================================================================

    def on_execute_before(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for before execution.

        Handler signature:
            def handler(ctx: EventContext[ExecuteBeforeParams, None]) -> None

        Available parameters:
            - agent: The Agent instance
            - max_iterations: Maximum iterations allowed
        """
        return self.on(AgentEvents.EXECUTE_BEFORE, priority=priority, predicate=predicate)

    def on_execute_after(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for after execution.

        Handler signature:
            def handler(ctx: EventContext[ExecuteAfterParams, None]) -> None

        Available parameters:
            - agent: The Agent instance
            - iterations: Number of iterations executed
            - final_message: Final message or None
        """
        return self.on(AgentEvents.EXECUTE_AFTER, priority=priority, predicate=predicate)

    def on_execute_iteration(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for execution iterations.

        Handler signature:
            def handler(ctx: EventContext[ExecuteIterationParams, None]) -> None

        Available parameters:
            - agent: The Agent instance
            - iteration: Current iteration number
            - messages_count: Number of messages (before event)
        """
        return self.on(AgentEvents.EXECUTE_ITERATION_BEFORE, priority=priority, predicate=predicate)

    # ========================================================================
    # Context and Template Events
    # ========================================================================

    def on_context_provider(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for context provider calls.

        Handler signature:
            def handler(ctx: EventContext[ContextProviderParams, Any]) -> Any | None

        Available parameters:
            - name: Provider name
            - context: Current context
            - result: Provider result (after event)

        Returns:
            Modified result or None
        """
        return self.on(AgentEvents.CONTEXT_PROVIDER_AFTER, priority=priority, predicate=predicate)

    def on_template_compile(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for template compilation.

        Handler signature:
            def handler(ctx: EventContext[TemplateCompileParams, Any]) -> Any | None

        Available parameters:
            - template: Template string
            - context: Render context
            - compiled: Compiled result (after event)

        Returns:
            Modified compiled result or None
        """
        return self.on(AgentEvents.TEMPLATE_COMPILE_AFTER, priority=priority, predicate=predicate)

    # ========================================================================
    # Storage Events
    # ========================================================================

    def on_storage_save(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for storage save operations.

        Handler signature:
            def handler(ctx: EventContext[StorageSaveParams, None]) -> None

        Available parameters:
            - key: Storage key
            - value: Value being saved
            - ttl: Optional TTL
            - success: Whether save succeeded (after event)
        """
        return self.on(AgentEvents.STORAGE_SAVE_AFTER, priority=priority, predicate=predicate)

    def on_storage_load(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for storage load operations.

        Handler signature:
            def handler(ctx: EventContext[StorageLoadParams, Any]) -> Any | None

        Available parameters:
            - key: Storage key
            - found: Whether key was found (after event)
            - value: Loaded value (after event)

        Returns:
            Modified value or None
        """
        return self.on(AgentEvents.STORAGE_LOAD_AFTER, priority=priority, predicate=predicate)

    # ========================================================================
    # Cache Events
    # ========================================================================

    def on_cache_hit(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for cache hits.

        Handler signature:
            def handler(ctx: EventContext[CacheHitParams, Any]) -> Any | None

        Available parameters:
            - key: Cache key
            - value: Cached value

        Returns:
            Modified value or None
        """
        return self.on(AgentEvents.CACHE_HIT, priority=priority, predicate=predicate)

    def on_cache_miss(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for cache misses.

        Handler signature:
            def handler(ctx: EventContext[CacheMissParams, None]) -> None

        Available parameters:
            - key: Cache key that missed
        """
        return self.on(AgentEvents.CACHE_MISS, priority=priority, predicate=predicate)

    def on_cache_set(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for cache set operations.

        Handler signature:
            def handler(ctx: EventContext[CacheSetParams, None]) -> None

        Available parameters:
            - key: Cache key
            - value: Value being cached
            - ttl: Optional TTL
        """
        return self.on(AgentEvents.CACHE_SET, priority=priority, predicate=predicate)

    def on_cache_invalidate(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for cache invalidation.

        Handler signature:
            def handler(ctx: EventContext[CacheInvalidateParams, None]) -> None

        Available parameters:
            - key: Optional specific key to invalidate
            - pattern: Optional pattern for invalidation
        """
        return self.on(AgentEvents.CACHE_INVALIDATE, priority=priority, predicate=predicate)

    # ========================================================================
    # Validation Events
    # ========================================================================

    def on_validation(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for validation operations.

        Handler signature:
            def handler(ctx: EventContext[ValidationParams, None]) -> None

        Available parameters:
            - target: Object being validated
            - schema: Optional validation schema
            - errors: Validation errors (after/error events)
            - valid: Whether validation passed (after event)
        """
        return self.on(AgentEvents.VALIDATION_AFTER, priority=priority, predicate=predicate)

    def on_validation_error(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for validation errors.

        Handler signature:
            def handler(ctx: EventContext[ValidationParams, None]) -> None

        Available parameters:
            - target: Object that failed validation
            - schema: Optional validation schema
            - errors: List of validation errors
        """
        return self.on(AgentEvents.VALIDATION_ERROR, priority=priority, predicate=predicate)

    # ========================================================================
    # Extension Events
    # ========================================================================

    def on_extension_install(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for extension installation.

        Handler signature:
            def handler(ctx: EventContext[ExtensionInstallParams, None]) -> None

        Available parameters:
            - extension: The AgentComponent being installed
            - agent: The Agent instance
        """
        return self.on(AgentEvents.EXTENSION_INSTALL, priority=priority, predicate=predicate)

    def on_extension_error(
        self,
        priority: int = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Register a handler for extension errors.

        Handler signature:
            def handler(ctx: EventContext[ExtensionErrorParams, None]) -> None

        Available parameters:
            - extension: The AgentComponent that errored
            - error: The exception
            - context: Where the error occurred
            - agent: The Agent instance
        """
        return self.on(AgentEvents.EXTENSION_ERROR, priority=priority, predicate=predicate)


# ============================================================================
# Standalone decorator functions for use without the mixin
# ============================================================================


def on_message_append(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for message append handlers.

    Example:
        @on_message_append()
        def handle_message(ctx: EventContext[MessageAppendParams, None]):
            message = ctx.parameters["message"]
    """
    return on(AgentEvents.MESSAGE_APPEND_AFTER, priority=priority, predicate=predicate)


def on_tool_call(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for tool call completion handlers.

    Example:
        @on_tool_call()
        def handle_tool_response(ctx: EventContext[ToolCallAfterParams, None]):
            response = ctx.parameters["response"]
    """
    return on(AgentEvents.TOOL_CALL_AFTER, priority=priority, predicate=predicate)


def on_llm_complete(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for LLM completion handlers.

    Example:
        @on_llm_complete()
        def handle_completion(ctx: EventContext[LLMCompleteParams, None]):
            response = ctx.parameters.get("response")
    """
    return on(AgentEvents.LLM_COMPLETE_AFTER, priority=priority, predicate=predicate)


def on_execute_iteration(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for execution iteration handlers.

    Example:
        @on_execute_iteration()
        def handle_iteration(ctx: EventContext[ExecuteIterationParams, None]):
            iteration = ctx.parameters["iteration"]
    """
    return on(AgentEvents.EXECUTE_ITERATION_BEFORE, priority=priority, predicate=predicate)


def on_llm_stream(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for LLM stream completion handlers.

    Example:
        @on_llm_stream()
        def handle_stream(ctx: EventContext[LLMStreamParams, None]):
            chunk = ctx.parameters.get("chunk")
    """
    return on(AgentEvents.LLM_STREAM_AFTER, priority=priority, predicate=predicate)


def on_llm_extract(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for LLM structured extraction handlers.

    Example:
        @on_llm_extract()
        def handle_extraction(ctx: EventContext[LLMExtractParams, Any]):
            output = ctx.parameters.get("output")
    """
    return on(AgentEvents.LLM_EXTRACT_AFTER, priority=priority, predicate=predicate)


def on_agent_init(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for agent initialization handlers.

    Example:
        @on_agent_init()
        def handle_init(ctx: EventContext[AgentInitializeParams, None]):
            agent = ctx.parameters["agent"]
    """
    return on(AgentEvents.AGENT_INIT_AFTER, priority=priority, predicate=predicate)


def on_cache_hit(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for cache hit handlers.

    Example:
        @on_cache_hit()
        def handle_cache_hit(ctx: EventContext[CacheHitParams, Any]):
            key = ctx.parameters["key"]
            value = ctx.parameters["value"]
    """
    return on(AgentEvents.CACHE_HIT, priority=priority, predicate=predicate)


def on_cache_miss(
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for cache miss handlers.

    Example:
        @on_cache_miss()
        def handle_cache_miss(ctx: EventContext[CacheMissParams, None]):
            key = ctx.parameters["key"]
    """
    return on(AgentEvents.CACHE_MISS, priority=priority, predicate=predicate)


# ============================================================================
# Export public API
# ============================================================================

__all__ = [
    # Mixin class
    "TypedEventHandlersMixin",
    # Standalone decorators - commonly used
    "on_message_append",
    "on_tool_call",
    "on_llm_complete",
    "on_llm_extract",
    "on_llm_stream",
    "on_execute_iteration",
    "on_agent_init",
    "on_cache_hit",
    "on_cache_miss",
]
