# events Specification

## Purpose
TBD - created by archiving change refactor-event-foundation. Update Purpose after archive.
## Requirements
### Requirement: Event Dispatch Semantics
The event system SHALL follow consistent dispatch semantics based on event phase:
- All `:before` events SHALL be dispatched with `apply()` (interceptable)
- All `:after` events SHALL be dispatched with `do()` (observational/fire-and-forget)

#### Scenario: Before event allows interception
- **GIVEN** a `:before` event is dispatched
- **WHEN** a handler sets `ctx.output`
- **THEN** the dispatching code SHALL use the modified value

#### Scenario: After event ignores output
- **GIVEN** an `:after` event is dispatched with `do()`
- **WHEN** a handler sets `ctx.output`
- **THEN** the value SHALL be ignored (fire-and-forget semantics)

### Requirement: MESSAGE_APPEND_BEFORE Event
The system SHALL dispatch `MESSAGE_APPEND_BEFORE` with `apply()` before any message is appended to the conversation, allowing handlers to modify or replace the message.

#### Scenario: Message interception before append
- **GIVEN** a message is being appended via `_append_message()`
- **WHEN** `MESSAGE_APPEND_BEFORE` is dispatched
- **AND** a handler sets `ctx.output` to a different Message
- **THEN** the replacement message SHALL be appended instead

#### Scenario: Message passes through unchanged
- **GIVEN** a message is being appended via `_append_message()`
- **WHEN** `MESSAGE_APPEND_BEFORE` is dispatched
- **AND** no handler modifies `ctx.output`
- **THEN** the original message SHALL be appended

### Requirement: MessageAppendBeforeParams TypedDict
The system SHALL provide a `MessageAppendBeforeParams` TypedDict for type-safe event handlers with fields:
- `message`: The Message being appended
- `agent`: The Agent instance

#### Scenario: Type-safe handler registration
- **GIVEN** a developer registers a `MESSAGE_APPEND_BEFORE` handler
- **WHEN** they annotate `ctx` as `EventContext[MessageAppendBeforeParams, Message]`
- **THEN** type checkers SHALL recognize the parameter and return types

### Requirement: LLM_STREAM_BEFORE Interceptable
The `LLM_STREAM_BEFORE` event SHALL be dispatched with `apply()` to allow handlers to modify streaming parameters before the stream begins.

#### Scenario: Modify streaming parameters
- **GIVEN** a streaming LLM call is initiated
- **WHEN** `LLM_STREAM_BEFORE` is dispatched
- **AND** a handler modifies `ctx.output`
- **THEN** the modified parameters SHALL be used for streaming

### Requirement: EXECUTE_BEFORE Interceptable
The `EXECUTE_BEFORE` event SHALL be dispatched with `apply()` to allow handlers to modify execution parameters or abort execution.

#### Scenario: Modify max_iterations
- **GIVEN** `agent.execute()` is called
- **WHEN** `EXECUTE_BEFORE` is dispatched
- **AND** a handler sets `ctx.output` with modified `max_iterations`
- **THEN** the modified value SHALL be used

### Requirement: EXECUTE_ITERATION_BEFORE Interceptable
The `EXECUTE_ITERATION_BEFORE` event SHALL be dispatched with `apply()` to allow handlers to modify or skip iterations.

#### Scenario: Intercept iteration start
- **GIVEN** an execute loop iteration begins
- **WHEN** `EXECUTE_ITERATION_BEFORE` is dispatched
- **THEN** handlers SHALL be able to modify iteration behavior via `ctx.output`

### Requirement: CONTEXT_PROVIDER_BEFORE Interceptable
The `CONTEXT_PROVIDER_BEFORE` event SHALL be dispatched with `apply()` to allow handlers to modify context provider calls.

#### Scenario: Intercept context provider call
- **GIVEN** a template context provider is called
- **WHEN** `CONTEXT_PROVIDER_BEFORE` is dispatched
- **THEN** handlers SHALL be able to modify the call via `ctx.output`

### Requirement: EXECUTE_ITERATION_AFTER Event
The system SHALL dispatch `EXECUTE_ITERATION_AFTER` with `do()` after each iteration of the execute loop completes.

#### Scenario: Iteration completion notification
- **GIVEN** an execute loop iteration completes
- **WHEN** `EXECUTE_ITERATION_AFTER` is dispatched
- **THEN** handlers SHALL receive iteration count and messages processed

### Requirement: EXECUTE_ERROR Event
The system SHALL dispatch `EXECUTE_ERROR` with `apply()` when an exception occurs during execute(), allowing handlers to provide recovery behavior.

#### Scenario: Execute error with recovery
- **GIVEN** an exception occurs during `agent.execute()`
- **WHEN** `EXECUTE_ERROR` is dispatched
- **AND** a handler sets `ctx.output` with recovery instructions
- **THEN** the execute loop SHALL use the recovery behavior

#### Scenario: Execute error propagates
- **GIVEN** an exception occurs during `agent.execute()`
- **WHEN** `EXECUTE_ERROR` is dispatched
- **AND** no handler provides recovery
- **THEN** the original exception SHALL propagate

### Requirement: CONTEXT_PROVIDER_AFTER Event
The system SHALL dispatch `CONTEXT_PROVIDER_AFTER` with `do()` after a template context provider returns.

#### Scenario: Context provider completion
- **GIVEN** a template context provider is called
- **WHEN** the provider returns
- **THEN** `CONTEXT_PROVIDER_AFTER` SHALL be dispatched with the result

### Requirement: LLM_COMPLETE_ERROR Event
The system SHALL dispatch `LLM_COMPLETE_ERROR` with `do()` specifically for errors during LLM completion (distinct from general `LLM_ERROR`).

#### Scenario: LLM completion error
- **GIVEN** an error occurs during `model.complete()`
- **WHEN** `LLM_COMPLETE_ERROR` is dispatched
- **THEN** handlers SHALL receive error details and original parameters

### Requirement: Agent Close Lifecycle Events
The system SHALL dispatch `AGENT_CLOSE_BEFORE` with `apply()` before cleanup starts and `AGENT_CLOSE_AFTER` with `do()` after cleanup completes.

#### Scenario: Close before event
- **GIVEN** `agent.close()` is called
- **WHEN** `AGENT_CLOSE_BEFORE` is dispatched
- **THEN** handlers SHALL be able to perform pre-cleanup tasks

#### Scenario: Close after event
- **GIVEN** `agent.close()` completes cleanup
- **WHEN** `AGENT_CLOSE_AFTER` is dispatched
- **THEN** handlers SHALL be notified for final logging/metrics

### Requirement: TOOL_CALL_ERROR Interceptable
The `TOOL_CALL_ERROR` event SHALL be dispatched with `apply()` to allow handlers to provide a fallback response.

#### Scenario: Tool error with fallback
- **GIVEN** a tool call fails
- **WHEN** `TOOL_CALL_ERROR` is dispatched
- **AND** a handler sets `ctx.output` to a `ToolResponse`
- **THEN** the fallback response SHALL be used instead of the error

#### Scenario: Tool error propagates
- **GIVEN** a tool call fails
- **WHEN** `TOOL_CALL_ERROR` is dispatched
- **AND** no handler provides a fallback
- **THEN** the error SHALL be recorded as the tool response

### Requirement: AgentCloseParams TypedDict
The system SHALL provide an `AgentCloseParams` TypedDict with fields:
- `agent`: The Agent instance
- `reason` (optional): String describing close reason

#### Scenario: Type-safe close handler
- **GIVEN** a developer registers an `AGENT_CLOSE_BEFORE` handler
- **WHEN** they annotate `ctx` with `EventContext[AgentCloseParams, None]`
- **THEN** type checkers SHALL recognize the parameter types

### Requirement: ExecuteErrorParams TypedDict
The system SHALL provide an `ExecuteErrorParams` TypedDict with fields:
- `agent`: The Agent instance
- `error`: The exception that occurred
- `iteration`: Current iteration count

#### Scenario: Type-safe error handler
- **GIVEN** a developer registers an `EXECUTE_ERROR` handler
- **WHEN** they annotate `ctx` with `EventContext[ExecuteErrorParams, Any]`
- **THEN** type checkers SHALL recognize the parameter and recovery types

### Requirement: Event Semantics Classification
The system SHALL provide an `EventSemantics` Flag enum to classify event dispatch behavior with values:
- `INTERCEPTABLE`: Event uses `apply()`, handlers can modify `ctx.output`
- `SIGNAL`: Event uses `do()`, fire-and-forget

#### Scenario: Query event semantics
- **GIVEN** a developer wants to know if an event is interceptable
- **WHEN** they call `get_event_semantics(AgentEvents.TOOL_CALL_BEFORE)`
- **THEN** they SHALL receive `EventSemantics.INTERCEPTABLE`

#### Scenario: Query signal event
- **GIVEN** a developer wants to know if an event is fire-and-forget
- **WHEN** they call `get_event_semantics(AgentEvents.MESSAGE_APPEND_AFTER)`
- **THEN** they SHALL receive `EventSemantics.SIGNAL`

### Requirement: EVENT_SEMANTICS Mapping
The system SHALL provide an `EVENT_SEMANTICS` dictionary mapping all `AgentEvents` to their `EventSemantics` classification.

#### Scenario: All events classified
- **GIVEN** the `EVENT_SEMANTICS` mapping
- **WHEN** iterating over all `AgentEvents` members
- **THEN** every event SHALL have a corresponding classification

### Requirement: EVENT_PARAMS Registry
The system SHALL provide an `EVENT_PARAMS` dictionary mapping `AgentEvents` to their corresponding TypedDict parameter types.

#### Scenario: Get parameter type for event
- **GIVEN** a developer wants to know the parameter type for an event
- **WHEN** they call `get_params_type(AgentEvents.TOOL_CALL_BEFORE)`
- **THEN** they SHALL receive `ToolCallBeforeParams`

#### Scenario: Event with no typed params
- **GIVEN** an event without a specific TypedDict
- **WHEN** `get_params_type()` is called
- **THEN** it SHALL return `None`

### Requirement: get_params_type Helper
The system SHALL provide a `get_params_type(event)` function that returns the TypedDict type for the event's parameters, or `None` if not defined.

#### Scenario: Lookup by enum
- **GIVEN** `get_params_type(AgentEvents.MESSAGE_APPEND_BEFORE)`
- **THEN** return `MessageAppendBeforeParams`

#### Scenario: Lookup by string
- **GIVEN** `get_params_type("message:append:before")`
- **THEN** return `MessageAppendBeforeParams`

### Requirement: Extension Point Events Documentation
Events for Storage, Cache, Validation, and Summary SHALL be documented as extension points that are not dispatched by core but are available for extensions to use.

#### Scenario: Storage events documented
- **GIVEN** the `STORAGE_SAVE_BEFORE` event
- **THEN** its docstring SHALL indicate it is an extension point

#### Scenario: Cache events documented
- **GIVEN** the `CACHE_HIT` event
- **THEN** its docstring SHALL indicate it is an extension point

### Requirement: Deprecated Event Aliases Removed
The system SHALL NOT expose deprecated event aliases for Tool, Execute, Context Provider, or Template events.

#### Scenario: Aliases absent from AgentEvents
- **GIVEN** a developer enumerates `AgentEvents`
- **WHEN** checking for `TOOL_RESPONSE`, `TOOL_ERROR`, `EXECUTE_START`, `EXECUTE_COMPLETE`, `EXECUTE_ITERATION`, `EXECUTE_ITERATION_START`, `EXECUTE_ITERATION_COMPLETE`, `CONTEXT_PROVIDER_CALL`, `CONTEXT_PROVIDER_RESPONSE`, and `TEMPLATE_COMPILE`
- **THEN** none SHALL be present

#### Scenario: Aliases not resolved by registries
- **GIVEN** the `get_event_semantics()` and `get_params_type()` helpers
- **WHEN** they are called with any deprecated alias name
- **THEN** they SHALL return `None`

### Requirement: HooksAccessor Class
The system SHALL provide a `HooksAccessor` class that provides type-safe methods for registering event handlers with clear documentation of event semantics.

#### Scenario: Access via agent.hooks
- **GIVEN** an Agent instance
- **WHEN** accessing `agent.hooks`
- **THEN** a `HooksAccessor` instance SHALL be returned

#### Scenario: Lazy initialization
- **GIVEN** an Agent instance
- **WHEN** `agent.hooks` is first accessed
- **THEN** the `HooksAccessor` SHALL be created and cached

### Requirement: Typed Handler Registration
Each method on `HooksAccessor` SHALL accept handlers with proper type hints for the event's parameters and return type.

#### Scenario: Type-safe message append handler
- **GIVEN** `agent.hooks.on_message_append_before()`
- **WHEN** a handler is registered with `ctx: EventContext[MessageAppendBeforeParams, Message]`
- **THEN** type checkers SHALL validate parameter access

#### Scenario: Type-safe tool call handler
- **GIVEN** `agent.hooks.on_tool_call_before()`
- **WHEN** a handler is registered with `ctx: EventContext[ToolCallBeforeParams, dict]`
- **THEN** type checkers SHALL validate parameter access

### Requirement: Decorator and Function Syntax
Each `HooksAccessor` method SHALL support both decorator syntax and direct function call syntax.

#### Scenario: Decorator syntax
- **GIVEN** `@agent.hooks.on_message_append_before`
- **WHEN** decorating a handler function
- **THEN** the handler SHALL be registered for the event

#### Scenario: Function syntax
- **GIVEN** `agent.hooks.on_message_append_before(my_handler)`
- **WHEN** called with a handler function
- **THEN** the handler SHALL be registered for the event

#### Scenario: Parameterized decorator
- **GIVEN** `@agent.hooks.on_message_append_before(priority=50)`
- **WHEN** decorating a handler function
- **THEN** the handler SHALL be registered with priority 50

### Requirement: Priority and Predicate Parameters
Each `HooksAccessor` method SHALL accept optional `priority` and `predicate` parameters.

#### Scenario: Custom priority
- **GIVEN** `agent.hooks.on_tool_call_before(priority=200)`
- **WHEN** the handler is registered
- **THEN** it SHALL have priority 200

#### Scenario: Predicate filter
- **GIVEN** `agent.hooks.on_tool_call_before(predicate=lambda ctx: ctx.parameters.get("tool_name") == "search")`
- **WHEN** the event fires for tool "other"
- **THEN** the handler SHALL NOT be called

### Requirement: Semantic Documentation
Each `HooksAccessor` method docstring SHALL clearly document:
- Whether the event is interceptable or observational
- What `ctx.output` should contain for interceptable events
- Available parameters in `ctx.parameters`

#### Scenario: Interceptable method documentation
- **GIVEN** the `on_message_append_before()` method
- **THEN** its docstring SHALL indicate it is interceptable and explain how to modify the message

#### Scenario: Signal method documentation
- **GIVEN** the `on_message_append_after()` method
- **THEN** its docstring SHALL indicate it is observational and ctx.output is ignored

### Requirement: Interceptable Event Methods
The following methods SHALL be marked as interceptable (handlers can modify outcome):
- `on_message_append_before()`
- `on_message_create_before()`
- `on_message_render_before()`
- `on_message_replace_before()`
- `on_message_set_system_before()`
- `on_tool_call_before()`
- `on_tool_call_error()` (for fallback)
- `on_tools_provide()`
- `on_tools_generate_signature()`
- `on_llm_complete_before()`
- `on_llm_extract_before()`
- `on_llm_stream_before()`
- `on_execute_before()`
- `on_execute_error()` (for recovery)
- `on_execute_iteration_before()`
- `on_agent_close_before()`

#### Scenario: Interceptable event modifies outcome
- **GIVEN** a handler registered via `agent.hooks.on_message_append_before()`
- **WHEN** the handler sets `ctx.output` to a new Message
- **THEN** the new message SHALL be used

### Requirement: Signal Event Methods
The following methods SHALL be marked as signals (fire-and-forget, ctx.output ignored):
- `on_message_append_after()`
- `on_message_create_after()`
- `on_message_render_after()`
- `on_message_replace_after()`
- `on_message_set_system_after()`
- `on_tool_call_after()`
- `on_llm_complete_after()`
- `on_llm_extract_after()`
- `on_llm_stream_after()`
- `on_llm_stream_chunk()`
- `on_llm_error()`
- `on_llm_complete_error()`
- `on_execute_after()`
- `on_execute_iteration_after()`
- `on_agent_init_after()`
- `on_agent_close_after()`
- `on_agent_state_change()`
- `on_agent_version_change()`
- `on_mode_entering()`
- `on_mode_entered()`
- `on_mode_exiting()`
- `on_mode_exited()`

#### Scenario: Signal event ignores output
- **GIVEN** a handler registered via `agent.hooks.on_message_append_after()`
- **WHEN** the handler sets `ctx.output`
- **THEN** the value SHALL be ignored

### Requirement: TypedEventHandlersMixin Deprecation
The `TypedEventHandlersMixin` class SHALL be deprecated in favor of `agent.hooks`.

#### Scenario: Deprecation warning
- **GIVEN** code imports `TypedEventHandlersMixin`
- **WHEN** the class is used
- **THEN** a deprecation warning SHALL be issued pointing to `agent.hooks`

