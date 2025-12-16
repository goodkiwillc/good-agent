# Events Capability Specification

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Deprecated Event Aliases
**Reason**: These aliases create confusion and maintenance burden.
**Migration**: Use the canonical event names instead.

Removed aliases:
- `TOOL_RESPONSE` → use `TOOL_CALL_AFTER`
- `TOOL_ERROR` → use `TOOL_CALL_ERROR`
- `EXECUTE_START` → use `EXECUTE_BEFORE`
- `EXECUTE_COMPLETE` → use `EXECUTE_AFTER`
- `EXECUTE_ITERATION` → use `EXECUTE_ITERATION_BEFORE` or `EXECUTE_ITERATION_AFTER`
- `EXECUTE_ITERATION_START` → use `EXECUTE_ITERATION_BEFORE`
- `EXECUTE_ITERATION_COMPLETE` → use `EXECUTE_ITERATION_AFTER`
- `CONTEXT_PROVIDER_CALL` → use `CONTEXT_PROVIDER_BEFORE`
- `CONTEXT_PROVIDER_RESPONSE` → use `CONTEXT_PROVIDER_AFTER`
- `TEMPLATE_COMPILE` → use `TEMPLATE_COMPILE_BEFORE` or `TEMPLATE_COMPILE_AFTER`
