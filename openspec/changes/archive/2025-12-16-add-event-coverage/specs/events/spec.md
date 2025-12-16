# Events Capability Specification

## ADDED Requirements

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
