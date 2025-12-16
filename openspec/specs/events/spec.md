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

