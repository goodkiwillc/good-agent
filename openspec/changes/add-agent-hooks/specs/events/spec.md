# Events Capability Specification

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: TypedEventHandlersMixin Deprecation
The `TypedEventHandlersMixin` class SHALL be deprecated in favor of `agent.hooks`.

#### Scenario: Deprecation warning
- **GIVEN** code imports `TypedEventHandlersMixin`
- **WHEN** the class is used
- **THEN** a deprecation warning SHALL be issued pointing to `agent.hooks`
