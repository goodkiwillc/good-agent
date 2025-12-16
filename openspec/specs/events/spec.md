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

