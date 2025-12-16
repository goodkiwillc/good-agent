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
