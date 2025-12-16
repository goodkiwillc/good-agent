from __future__ import annotations

from typing import Any

from good_agent.events.agent import AgentEvents
from good_agent.events.classification import (
    EVENT_SEMANTICS,
    EventSemantics,
)
from good_agent.events.classification import (
    get_event_semantics as _get_event_semantics,
)
from good_agent.events.types import (
    AgentCloseParams,
    AgentForkParams,
    AgentInitializeParams,
    AgentMergeParams,
    AgentStateChangeParams,
    AgentVersionChangeParams,
    CacheHitParams,
    CacheInvalidateParams,
    CacheMissParams,
    CacheSetParams,
    ContextProviderParams,
    ExecuteAfterParams,
    ExecuteBeforeParams,
    ExecuteErrorParams,
    ExecuteIterationAfterParams,
    ExecuteIterationParams,
    ExtensionErrorParams,
    ExtensionInstallParams,
    LLMCompleteParams,
    LLMErrorParams,
    LLMExtractParams,
    LLMStreamParams,
    MessageAppendBeforeParams,
    MessageAppendParams,
    MessageCreateParams,
    MessagePartRenderParams,
    MessageRenderParams,
    MessageReplaceParams,
    MessageSetSystemParams,
    StorageLoadParams,
    StorageSaveParams,
    TemplateCompileParams,
    ToolCallAfterParams,
    ToolCallBeforeParams,
    ToolCallErrorParams,
    ToolsGenerateSignature,
    ValidationParams,
)

EventParamsType = type[Any] | None


EVENT_PARAMS: dict[AgentEvents, EventParamsType] = {
    # Agent lifecycle
    AgentEvents.AGENT_INIT_BEFORE: AgentInitializeParams,
    AgentEvents.AGENT_INIT_AFTER: AgentInitializeParams,
    AgentEvents.AGENT_CLOSE_BEFORE: AgentCloseParams,
    AgentEvents.AGENT_CLOSE_AFTER: AgentCloseParams,
    AgentEvents.AGENT_STATE_CHANGE: AgentStateChangeParams,
    AgentEvents.AGENT_FORK_BEFORE: AgentForkParams,
    AgentEvents.AGENT_FORK_AFTER: AgentForkParams,
    AgentEvents.AGENT_MERGE_BEFORE: AgentMergeParams,
    AgentEvents.AGENT_MERGE_AFTER: AgentMergeParams,
    AgentEvents.AGENT_VERSION_CHANGE: AgentVersionChangeParams,

    # Extensions
    AgentEvents.EXTENSION_INSTALL_BEFORE: ExtensionInstallParams,
    AgentEvents.EXTENSION_INSTALL: ExtensionInstallParams,
    AgentEvents.EXTENSION_INSTALL_AFTER: ExtensionInstallParams,
    AgentEvents.EXTENSION_ERROR: ExtensionErrorParams,

    # Messages
    AgentEvents.MESSAGE_CREATE_BEFORE: MessageCreateParams,
    AgentEvents.MESSAGE_CREATE_AFTER: MessageCreateParams,
    AgentEvents.MESSAGE_APPEND_BEFORE: MessageAppendBeforeParams,
    AgentEvents.MESSAGE_APPEND_AFTER: MessageAppendParams,
    AgentEvents.MESSAGE_REPLACE_BEFORE: MessageReplaceParams,
    AgentEvents.MESSAGE_REPLACE_AFTER: MessageReplaceParams,
    AgentEvents.MESSAGE_SET_SYSTEM_BEFORE: MessageSetSystemParams,
    AgentEvents.MESSAGE_SET_SYSTEM_AFTER: MessageSetSystemParams,
    AgentEvents.MESSAGE_RENDER_BEFORE: MessageRenderParams,
    AgentEvents.MESSAGE_RENDER_AFTER: MessageRenderParams,
    AgentEvents.MESSAGE_PART_RENDER: MessagePartRenderParams,

    # LLM
    AgentEvents.LLM_COMPLETE_BEFORE: LLMCompleteParams,
    AgentEvents.LLM_COMPLETE_AFTER: LLMCompleteParams,
    AgentEvents.LLM_COMPLETE_ERROR: LLMErrorParams,
    AgentEvents.LLM_EXTRACT_BEFORE: LLMExtractParams,
    AgentEvents.LLM_EXTRACT_AFTER: LLMExtractParams,
    AgentEvents.LLM_EXTRACT_ERROR: LLMErrorParams,
    AgentEvents.LLM_STREAM_BEFORE: LLMStreamParams,
    AgentEvents.LLM_STREAM_AFTER: LLMStreamParams,
    AgentEvents.LLM_STREAM_CHUNK: LLMStreamParams,
    AgentEvents.LLM_STREAM_ERROR: LLMErrorParams,
    AgentEvents.LLM_ERROR: LLMErrorParams,
    AgentEvents.TOOLS_PROVIDE: ToolsGenerateSignature,
    AgentEvents.TOOLS_GENERATE_SIGNATURE: ToolsGenerateSignature,

    # Tools
    AgentEvents.TOOL_CALL_BEFORE: ToolCallBeforeParams,
    AgentEvents.TOOL_CALL_AFTER: ToolCallAfterParams,
    AgentEvents.TOOL_CALL_ERROR: ToolCallErrorParams,

    # Execution
    AgentEvents.EXECUTE_BEFORE: ExecuteBeforeParams,
    AgentEvents.EXECUTE_AFTER: ExecuteAfterParams,
    AgentEvents.EXECUTE_ERROR: ExecuteErrorParams,
    AgentEvents.EXECUTE_ITERATION_BEFORE: ExecuteIterationParams,
    AgentEvents.EXECUTE_ITERATION_AFTER: ExecuteIterationAfterParams,
    AgentEvents.EXECUTE_ITERATION_ERROR: ExecuteErrorParams,

    # Context and templates
    AgentEvents.CONTEXT_PROVIDER_BEFORE: ContextProviderParams,
    AgentEvents.CONTEXT_PROVIDER_AFTER: ContextProviderParams,
    AgentEvents.CONTEXT_PROVIDER_ERROR: ContextProviderParams,
    AgentEvents.TEMPLATE_COMPILE_BEFORE: TemplateCompileParams,
    AgentEvents.TEMPLATE_COMPILE_AFTER: TemplateCompileParams,
    AgentEvents.TEMPLATE_COMPILE_ERROR: TemplateCompileParams,

    # Storage
    AgentEvents.STORAGE_SAVE_BEFORE: StorageSaveParams,
    AgentEvents.STORAGE_SAVE_AFTER: StorageSaveParams,
    AgentEvents.STORAGE_SAVE_ERROR: StorageSaveParams,
    AgentEvents.STORAGE_LOAD_BEFORE: StorageLoadParams,
    AgentEvents.STORAGE_LOAD_AFTER: StorageLoadParams,
    AgentEvents.STORAGE_LOAD_ERROR: StorageLoadParams,

    # Cache
    AgentEvents.CACHE_HIT: CacheHitParams,
    AgentEvents.CACHE_MISS: CacheMissParams,
    AgentEvents.CACHE_SET: CacheSetParams,
    AgentEvents.CACHE_INVALIDATE: CacheInvalidateParams,

    # Validation
    AgentEvents.VALIDATION_BEFORE: ValidationParams,
    AgentEvents.VALIDATION_AFTER: ValidationParams,
    AgentEvents.VALIDATION_ERROR: ValidationParams,

    # Modes
    AgentEvents.MODE_ENTERING: None,
    AgentEvents.MODE_ENTERED: None,
    AgentEvents.MODE_EXITING: None,
    AgentEvents.MODE_EXITED: None,
    AgentEvents.MODE_ERROR: None,
    AgentEvents.MODE_TRANSITION: None,

    # Citations
    AgentEvents.CITATIONS_EXTRACTED: None,
    AgentEvents.CITATIONS_UPDATED: None,

    # Web fetcher
    AgentEvents.FETCH_URL_REQUESTED: None,
    AgentEvents.FETCH_URL_STARTED: None,
    AgentEvents.FETCH_URL_COMPLETED: None,
    AgentEvents.FETCH_URL_ERROR: None,
    AgentEvents.CITATION_CONTENT_REQUESTED: None,
    AgentEvents.CITATION_CONTENT_RESOLVED: None,

    # Summary generation
    AgentEvents.SUMMARY_GENERATE_BEFORE: None,
    AgentEvents.SUMMARY_GENERATE_AFTER: None,
    AgentEvents.SUMMARY_GENERATE_ERROR: None,
}


def get_params_type(event: AgentEvents | str) -> EventParamsType:
    """Return the TypedDict type for the given event, if registered."""

    try:
        key = AgentEvents(event)
    except ValueError:
        return None
    return EVENT_PARAMS.get(key)


def get_event_semantics(event: AgentEvents | str) -> EventSemantics | None:
    """Return the semantics classification for a given event."""

    return _get_event_semantics(event)


__all__ = [
    "EVENT_PARAMS",
    "get_params_type",
    "get_event_semantics",
    "EventSemantics",
    "EVENT_SEMANTICS",
]
