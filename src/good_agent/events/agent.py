from enum import StrEnum


class AgentEvents(StrEnum):
    """Canonical event names emitted by Agent and its components.

    Names follow ``domain:action[:phase]`` and cover lifecycle, LLM, tool, and
    template operations. ``examples/events/basic_events.py`` shows how to attach
    handlers using ``agent.on(AgentEvents.*)``.
    """

    # ===== Agent Lifecycle Events =====
    # Agent initialization
    AGENT_INIT_BEFORE = "agent:init:before"
    AGENT_INIT_AFTER = "agent:init:after"  # Replaces AGENT_INITIALIZED

    # Agent state changes
    AGENT_STATE_CHANGE = "agent:state:change"

    # Agent forking
    AGENT_FORK_BEFORE = "agent:fork:before"
    AGENT_FORK_AFTER = "agent:fork:after"

    # Agent merging
    AGENT_MERGE_BEFORE = "agent:merge:before"
    AGENT_MERGE_AFTER = "agent:merge:after"

    # Agent versioning
    AGENT_VERSION_CHANGE = "agent:version:change"

    # ===== Extension Events =====
    EXTENSION_INSTALL_BEFORE = "extension:install:before"
    EXTENSION_INSTALL = "extension:install"
    EXTENSION_INSTALL_AFTER = "extension:install:after"
    EXTENSION_ERROR = "extension:error"

    # ===== Message Events =====
    # Message creation
    MESSAGE_CREATE_BEFORE = "message:create:before"
    MESSAGE_CREATE_AFTER = "message:create:after"

    # Message appending
    MESSAGE_APPEND_BEFORE = "message:append:before"
    # MESSAGE_APPEND = "message:append"
    MESSAGE_APPEND_AFTER = "message:append:after"

    # Message replacement
    MESSAGE_REPLACE_BEFORE = "message:replace:before"
    # MESSAGE_REPLACE = "message:replace"
    MESSAGE_REPLACE_AFTER = "message:replace:after"

    # System message setting
    MESSAGE_SET_SYSTEM_BEFORE = "message:set_system:before"
    MESSAGE_SET_SYSTEM_AFTER = "message:set_system:after"

    # Message rendering
    MESSAGE_RENDER_BEFORE = "message:render:before"
    MESSAGE_RENDER_AFTER = "message:render:after"
    MESSAGE_PART_RENDER = "message:part:render"

    # ===== LLM Events =====
    # LLM completion (raw text responses)
    LLM_COMPLETE_BEFORE = "llm:complete:before"
    LLM_COMPLETE_AFTER = "llm:complete:after"
    LLM_COMPLETE_ERROR = "llm:complete:error"

    # LLM extraction (structured output)
    LLM_EXTRACT_BEFORE = "llm:extract:before"
    LLM_EXTRACT_AFTER = "llm:extract:after"
    LLM_EXTRACT_ERROR = "llm:extract:error"

    # LLM streaming
    LLM_STREAM_BEFORE = "llm:stream:before"
    LLM_STREAM_AFTER = "llm:stream:after"
    LLM_STREAM_CHUNK = "llm:stream:chunk"
    LLM_STREAM_ERROR = "llm:stream:error"

    # General LLM error
    LLM_ERROR = "llm:error"

    TOOLS_PROVIDE = "tools:provide"
    TOOLS_GENERATE_SIGNATURE = "tools:generate_signature"  # DEPRECATED: Use tools:provide

    # ===== Tool Events =====
    TOOL_CALL_BEFORE = "tool:call:before"
    TOOL_CALL_AFTER = "tool:call:after"
    TOOL_CALL_ERROR = "tool:call:error"

    # Deprecated tool events
    TOOL_RESPONSE = "tool:call:after"  # DEPRECATED: Use TOOL_CALL_AFTER
    TOOL_ERROR = "tool:call:error"  # DEPRECATED: Use TOOL_CALL_ERROR

    # ===== Execution Events =====
    # Main execution lifecycle
    EXECUTE_BEFORE = "execute:before"
    EXECUTE_AFTER = "execute:after"
    EXECUTE_ERROR = "execute:error"

    # Legacy execution events (kept for compatibility)
    EXECUTE_START = "execute:before"  # DEPRECATED: Use EXECUTE_BEFORE
    EXECUTE_COMPLETE = "execute:after"  # DEPRECATED: Use EXECUTE_AFTER

    # Iteration events
    EXECUTE_ITERATION_BEFORE = "execute:iteration:before"
    EXECUTE_ITERATION_AFTER = "execute:iteration:after"
    EXECUTE_ITERATION_ERROR = "execute:iteration:error"

    # Legacy iteration events
    EXECUTE_ITERATION = "execute:iteration"  # DEPRECATED: Use specific phase events
    EXECUTE_ITERATION_START = "execute:iteration:before"  # DEPRECATED
    EXECUTE_ITERATION_COMPLETE = "execute:iteration:after"  # DEPRECATED

    # ===== Context and Template Events =====
    # Context provider
    CONTEXT_PROVIDER_BEFORE = "context:provider:before"
    CONTEXT_PROVIDER_AFTER = "context:provider:after"
    CONTEXT_PROVIDER_ERROR = "context:provider:error"

    # Legacy context events
    CONTEXT_PROVIDER_CALL = "context:provider:before"  # DEPRECATED
    CONTEXT_PROVIDER_RESPONSE = "context:provider:after"  # DEPRECATED

    # Template compilation
    TEMPLATE_COMPILE_BEFORE = "template:compile:before"
    TEMPLATE_COMPILE_AFTER = "template:compile:after"
    TEMPLATE_COMPILE_ERROR = "template:compile:error"
    TEMPLATE_COMPILE = "template:compile"  # DEPRECATED: Use specific phase events

    # ===== Storage Events (NEW) =====
    STORAGE_SAVE_BEFORE = "storage:save:before"
    STORAGE_SAVE_AFTER = "storage:save:after"
    STORAGE_SAVE_ERROR = "storage:save:error"

    STORAGE_LOAD_BEFORE = "storage:load:before"
    STORAGE_LOAD_AFTER = "storage:load:after"
    STORAGE_LOAD_ERROR = "storage:load:error"

    # ===== Cache Events (NEW) =====
    CACHE_HIT = "cache:hit"
    CACHE_MISS = "cache:miss"
    CACHE_SET = "cache:set"
    CACHE_INVALIDATE = "cache:invalidate"

    # ===== Validation Events (NEW) =====
    VALIDATION_BEFORE = "validation:before"
    VALIDATION_AFTER = "validation:after"
    VALIDATION_ERROR = "validation:error"

    # ===== Mode Events (NEW) =====
    # Mode lifecycle
    MODE_ENTERING = "mode:entering"  # Before setup runs
    MODE_ENTERED = "mode:entered"  # After setup completes
    MODE_EXITING = "mode:exiting"  # Before cleanup runs
    MODE_EXITED = "mode:exited"  # After cleanup completes
    MODE_ERROR = "mode:error"  # Exception in handler
    MODE_TRANSITION = "mode:transition"  # Handler requested transition

    # ===== Citation Events (NEW) =====
    # Citation extraction events
    CITATIONS_EXTRACTED = "citations:extracted"
    CITATIONS_UPDATED = "citations:updated"

    # ===== WebFetcher Events (NEW) =====
    # URL fetch requests
    FETCH_URL_REQUESTED = "fetch:url:requested"
    FETCH_URL_STARTED = "fetch:url:started"
    FETCH_URL_COMPLETED = "fetch:url:completed"
    FETCH_URL_ERROR = "fetch:url:error"

    # Citation content requests
    CITATION_CONTENT_REQUESTED = "citation:content:requested"
    CITATION_CONTENT_RESOLVED = "citation:content:resolved"

    # Summary generation
    SUMMARY_GENERATE_BEFORE = "summary:generate:before"
    SUMMARY_GENERATE_AFTER = "summary:generate:after"
    SUMMARY_GENERATE_ERROR = "summary:generate:error"
