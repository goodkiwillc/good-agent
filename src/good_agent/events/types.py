from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from ulid import ULID

if TYPE_CHECKING:
    from good_agent.agent import Agent, AgentState
    from good_agent.messages import Message
    from good_agent.model.protocols import ResponseWithUsage
    from good_agent.tools import Tool, ToolCall, ToolResponse


# ============================================================================
# Agent Lifecycle Event Parameters
# ============================================================================


class AgentInitializeParams(TypedDict):
    """Parameters for agent:init:* events.

    Note: AGENT_INIT_AFTER fires during __init__, so external handlers
    cannot be registered. Use class-level @on decorators or subclassing
    to handle this event.
    """

    agent: Agent
    tools: list[str | Any]  # Tools to be loaded


class AgentStateChangeParams(TypedDict):
    """Parameters for agent:state:change event."""

    agent: Agent
    new_state: AgentState
    old_state: AgentState


class AgentForkParams(TypedDict):
    """Parameters for agent:fork:* events."""

    parent: Agent
    child: Agent
    config_changes: NotRequired[dict[str, Any]]


class AgentMergeParams(TypedDict):
    """Parameters for agent:merge:* events."""

    target: Agent
    sources: list[Agent]
    strategy: Literal["tool_call", "interleaved"]
    result: NotRequired[str | None]  # "success" or None


class AgentVersionChangeParams(TypedDict):
    """Parameters for agent:version:change event."""

    agent: Agent
    old_version: ULID
    new_version: ULID
    changes: dict[str, Any]


# ============================================================================
# Extension Event Parameters
# ============================================================================


class ExtensionInstallParams(TypedDict):
    """Parameters for extension:install:* events."""

    extension: Any  # AgentComponent
    agent: Agent


class ExtensionErrorParams(TypedDict):
    """Parameters for extension:error event."""

    extension: Any  # AgentComponent
    error: Exception
    context: str  # Where the error occurred (e.g., "install")
    agent: Agent


# ============================================================================
# Message Event Parameters
# ============================================================================


class MessageCreateParams(TypedDict):
    """Parameters for message:create:* events."""

    content: Any  # MessageContent or sequence of content parts
    role: Literal["user", "assistant", "system", "tool"]
    context: NotRequired[dict[str, Any] | None]
    citations: NotRequired[list[str] | None]
    metadata: NotRequired[dict[str, Any]]


class MessageAppendParams(TypedDict):
    """Parameters for message:append:* events."""

    message: Message
    agent: Agent


class MessageReplaceParams(TypedDict):
    """Parameters for message:replace:* events."""

    index: int
    message: Message
    agent: Agent


class MessageSetSystemParams(TypedDict):
    """Parameters for message:set_system:* events."""

    message: Message  # SystemMessage
    agent: Agent


class MessageRenderParams(TypedDict):
    """Parameters for message:render:* events."""

    message: Message
    mode: Literal["text", "llm", "display"]
    context: NotRequired[dict[str, Any]]
    output: NotRequired[list[Any]]


class MessagePartRenderParams(TypedDict):
    """Parameters for message:part:render event."""

    part: Any  # ContentPart
    mode: Literal["text", "llm", "display"]
    context: NotRequired[dict[str, Any]]


# ============================================================================
# LLM Event Parameters
# ============================================================================


class LLMCompleteParams(TypedDict):
    """Parameters for llm:complete:* events."""

    messages: list[dict[str, Any]]
    model: str
    temperature: NotRequired[float]
    max_tokens: NotRequired[int]
    tools: NotRequired[list[dict[str, Any]]]
    parallel_tool_calls: NotRequired[bool]
    response: NotRequired[ResponseWithUsage]  # After event


class LLMExtractParams(TypedDict):
    """Parameters for llm:extract:* events."""

    messages: list[dict[str, Any]]
    response_model: type[Any]  # Pydantic model class
    model: str
    temperature: NotRequired[float]
    max_tokens: NotRequired[int]
    output: NotRequired[Any]  # After event - extracted model instance


class LLMStreamParams(TypedDict):
    """Parameters for llm:stream:* events."""

    messages: list[dict[str, Any]]
    model: str
    temperature: NotRequired[float]
    max_tokens: NotRequired[int]
    chunk: NotRequired[Any]  # For stream:chunk event


class LLMErrorParams(TypedDict):
    """Parameters for llm:error event."""

    error: Exception
    parameters: dict[str, Any]  # Original LLM parameters
    agent: Agent


# ============================================================================
# Tool Event Parameters
# ============================================================================


class ToolsGenerateSignature(TypedDict):
    """Parameters for tools:provide event."""

    tool: Tool
    agent: Agent


class ToolCallBeforeParams(TypedDict):
    """Parameters for tool:call:before event."""

    tool_call: NotRequired[ToolCall]  # When called from execute()
    tool: NotRequired[Tool]  # When available
    tool_name: NotRequired[str]  # When called from invoke()
    arguments: NotRequired[dict[str, Any]]  # Tool arguments
    parameters: NotRequired[dict[str, Any]]  # Alternative name for arguments
    tool_call_id: NotRequired[str]
    agent: Agent


class ToolCallAfterParams(TypedDict):
    """Parameters for tool:call:after event."""

    response: NotRequired[ToolResponse | Any]
    tool_call: NotRequired[ToolCall]
    tool: NotRequired[Tool]
    tool_name: NotRequired[str]
    tool_call_id: NotRequired[str]
    success: NotRequired[bool]
    agent: Agent


class ToolCallErrorParams(TypedDict):
    """Parameters for tool:call:error event."""

    error: Exception | str
    tool_call: NotRequired[ToolCall]
    tool: NotRequired[Tool]
    tool_name: NotRequired[str]
    tool_call_id: NotRequired[str]
    parameters: NotRequired[dict[str, Any]]
    agent: Agent


# ============================================================================
# Execution Event Parameters
# ============================================================================


class ExecuteBeforeParams(TypedDict):
    """Parameters for execute:before event."""

    agent: Agent
    max_iterations: int


class ExecuteAfterParams(TypedDict):
    """Parameters for execute:after event."""

    agent: Agent
    iterations: int
    final_message: Message | None


class ExecuteIterationParams(TypedDict):
    """Parameters for execute:iteration:* events."""

    agent: Agent
    iteration: int
    messages_count: NotRequired[int]  # For before event


# ============================================================================
# Context and Template Event Parameters
# ============================================================================


class ContextProviderParams(TypedDict):
    """Parameters for context:provider:* events."""

    name: str
    context: dict[str, Any]
    result: NotRequired[Any]  # After event


class TemplateCompileParams(TypedDict):
    """Parameters for template:compile:* events."""

    template: str
    context: dict[str, Any]
    compiled: NotRequired[Any]  # After event


# ============================================================================
# Storage Event Parameters
# ============================================================================


class StorageSaveParams(TypedDict):
    """Parameters for storage:save:* events."""

    key: str
    value: Any
    ttl: NotRequired[int]
    success: NotRequired[bool]  # After event


class StorageLoadParams(TypedDict):
    """Parameters for storage:load:* events."""

    key: str
    found: NotRequired[bool]  # After event
    value: NotRequired[Any]  # After event


# ============================================================================
# Cache Event Parameters
# ============================================================================


class CacheHitParams(TypedDict):
    """Parameters for cache:hit event."""

    key: str
    value: Any


class CacheMissParams(TypedDict):
    """Parameters for cache:miss event."""

    key: str


class CacheSetParams(TypedDict):
    """Parameters for cache:set event."""

    key: str
    value: Any
    ttl: NotRequired[int]


class CacheInvalidateParams(TypedDict):
    """Parameters for cache:invalidate event."""

    key: NotRequired[str]
    pattern: NotRequired[str]  # For pattern-based invalidation


# ============================================================================
# Validation Event Parameters
# ============================================================================


class ValidationParams(TypedDict):
    """Parameters for validation:* events."""

    target: Any
    schema: NotRequired[type[Any]]
    errors: NotRequired[list[str]]  # After/error events
    valid: NotRequired[bool]  # After event


# ============================================================================
# Type Aliases for Common Return Types
# ============================================================================

# Most events don't return values (None)
NoReturn = None

# Some events can modify their inputs and return them
# Use string literals to avoid circular imports at runtime
MessageReturn = "Message | None"
ToolResponseReturn = "ToolResponse | None"
ParametersReturn = dict[str, Any] | None

# ============================================================================
# Export all parameter types
# ============================================================================

__all__ = [
    # Agent lifecycle
    "AgentInitializeParams",
    "AgentStateChangeParams",
    "AgentForkParams",
    "AgentMergeParams",
    "AgentVersionChangeParams",
    # Extensions
    "ExtensionInstallParams",
    "ExtensionErrorParams",
    # Messages
    "MessageCreateParams",
    "MessageAppendParams",
    "MessageReplaceParams",
    "MessageSetSystemParams",
    "MessageRenderParams",
    "MessagePartRenderParams",
    # LLM
    "LLMCompleteParams",
    "LLMExtractParams",
    "LLMStreamParams",
    "LLMErrorParams",
    # Tools
    "ToolCallBeforeParams",
    "ToolCallAfterParams",
    "ToolCallErrorParams",
    # Execution
    "ExecuteBeforeParams",
    "ExecuteAfterParams",
    "ExecuteIterationParams",
    # Context/Template
    "ContextProviderParams",
    "TemplateCompileParams",
    # Storage
    "StorageSaveParams",
    "StorageLoadParams",
    # Cache
    "CacheHitParams",
    "CacheMissParams",
    "CacheSetParams",
    "CacheInvalidateParams",
    # Validation
    "ValidationParams",
    # Return types
    "NoReturn",
    "MessageReturn",
    "ToolResponseReturn",
    "ParametersReturn",
]
