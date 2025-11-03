"""
CONTEXT: Agent-specific event definitions for the GoodIntel event system.
ROLE: Defines typed event names and lifecycle hooks for agent operations,
      LLM interactions, tool execution, and system integration.
DEPENDENCIES:
  - enum.StrEnum: String-based enumeration for event type safety
  - good_agent.utilities.event_router: Core event system infrastructure
ARCHITECTURE:
  - Central event registry for all agent lifecycle and operation events
  - Follows namespace:action:phase naming convention for consistency
  - Integrates with EventRouter for typed event handling
  - Provides hooks for extensions and monitoring systems
KEY EXPORTS: AgentEvents enum with comprehensive event definitions
USAGE PATTERNS:
  1. Event emission: agent.do(AgentEvents.LLM_COMPLETE_BEFORE, messages=messages)
  2. Event handling: agent.on(AgentEvents.TOOL_CALL_AFTER)(my_handler)
  3. Event filtering: agent.on(AgentEvents.STATE_CHANGE).filter(lambda ctx: ctx.params['new_state'] == 'READY')
  4. Extension integration: Monitor events to provide additional functionality
RELATED MODULES:
  - good_agent.utilities.event_router: Core event infrastructure
  - ..agent: Primary event emitter for agent lifecycle
  - ..components: Event consumers for extension functionality
  - ..extensions: Third-party event consumers for integrations

EVENT SYSTEM INTEGRATION:
Agent Core → Event Router → Component Extensions → External Systems

Key patterns:
- Before/After pairs for major operations (LLM_COMPLETE_BEFORE/AFTER)
- State transition events with old/new state parameters
- Error events with context for debugging and recovery
- Message events for content processing pipelines
- Tool events for execution monitoring and instrumentation

PERFORMANCE NOTES:
- Event dispatch is async but non-blocking for agent execution
- Handler failures don't interrupt agent operation (logged as warnings)
- Event parameter validation happens at emission time
- Consider handler execution time for performance-critical events
- Use apply() for events that modify data, do() for notifications only
"""

from enum import StrEnum


class AgentEvents(StrEnum):
    """
    PURPOSE: Comprehensive event type definitions for agent lifecycle and operations.

    PURPOSE: Defines all events that agents can emit during their lifecycle,
    providing hooks for extensions, monitoring, debugging, and system integration.
    Events follow a consistent naming convention and include comprehensive
    coverage of agent operations from initialization to execution.

    NAMING CONVENTION:
    - Format: domain:action:phase where phase is before/after/error
    - Examples: llm:complete:before, tool:call:after, execute:before
    - State transitions may omit phase (agent:state:change)
    - DEPRECATED events marked with replacement suggestions

    EVENT FLOW PATTERNS:
    1. BEFORE events: Allow modification of parameters before operation
    2. MAIN events: Core operation execution (may not exist for all operations)
    3. AFTER events: Notification of completion with results
    4. ERROR events: Error handling with context and recovery information

    USAGE GUIDELINES:
    - Use apply() for events that can modify data (BEFORE events)
    - Use do() for notification-only events (AFTER/ERROR events)
    - Event handlers should be async and handle exceptions gracefully
    - Parameter validation occurs at emission time
    - Consider performance impact for frequently fired events

    EVENT CATEGORIES:
    - AGENT_*: Core agent lifecycle and state management
    - EXTENSION_*: Extension installation and management
    - MESSAGE_*: Message creation, rendering, and manipulation
    - LLM_*: Language model interactions and completions
    - TOOL_*: Tool execution and response handling
    - EXECUTE_*: Main agent execution flow control
    - CONTEXT_*: Context provider integration
    - TEMPLATE_*: Template compilation and rendering
    - STORAGE_*: Data persistence operations
    - CACHE_*: Caching layer interactions
    - VALIDATION_*: Input validation and schema checking
    - CITATIONS_*: Citation extraction and management
    - FETCH_*: Web content retrieval and processing
    - SUMMARY_*: Content summarization operations

    INTEGRATION EXAMPLES:
    ```python
    # Monitor LLM completions for logging
    agent.on(AgentEvents.LLM_COMPLETE_AFTER)(log_completion_metrics)

    # Modify messages before rendering
    agent.on(AgentEvents.MESSAGE_RENDER_BEFORE).apply(add_security_headers)

    # Handle tool errors with fallback logic
    agent.on(AgentEvents.TOOL_CALL_ERROR)(handle_tool_failure)

    # Track agent state changes
    agent.on(AgentEvents.AGENT_STATE_CHANGE)(update_agent_status)

    # Monitor cache performance
    agent.on(AgentEvents.CACHE_HIT)(track_cache_hit)
    agent.on(AgentEvents.CACHE_MISS)(track_cache_miss)
    ```

    PERFORMANCE CONSIDERATIONS:
    - Event dispatch is designed to be non-blocking
    - Handler failures are logged but don't interrupt agent flow
    - Frequently fired events (like streaming chunks) should have lightweight handlers
    - Use event filtering to reduce unnecessary handler execution
    - Consider async handler patterns for I/O-intensive operations

    DEPRECATION POLICY:
    - Deprecated events marked with replacement suggestions
    - Maintained for backward compatibility but may be removed in future versions
    - New event names follow consistent naming conventions
    - Migration path provided for all deprecated events

    EXTENSION POINTS:
    - All events are available for extension integration
    - Use events to provide cross-cutting concerns (logging, monitoring, security)
    - Events enable loose coupling between agent core and extensions
    - Custom events can be added following the naming convention
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
    TOOLS_GENERATE_SIGNATURE = (
        "tools:generate_signature"  # DEPRECATED: Use tools:provide
    )

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
