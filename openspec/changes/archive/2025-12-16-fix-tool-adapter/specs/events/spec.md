# Events Capability Specification

## ADDED Requirements

### Requirement: ToolMessage.with_tool_response Method
The `ToolMessage` class SHALL provide a `with_tool_response(response: ToolResponse)` method that returns a new `ToolMessage` instance with the updated tool response.

#### Scenario: Create message with new response
- **GIVEN** a `ToolMessage` instance
- **WHEN** `with_tool_response(new_response)` is called
- **THEN** a new `ToolMessage` SHALL be returned with the new response

#### Scenario: Preserve other fields
- **GIVEN** a `ToolMessage` with content, tool_call_id, and metadata
- **WHEN** `with_tool_response(new_response)` is called
- **THEN** all other fields SHALL be preserved in the new message

### Requirement: Tool Response Transformation via MESSAGE_APPEND_BEFORE
Tool adapters SHALL transform responses by hooking into `MESSAGE_APPEND_BEFORE` rather than `TOOL_CALL_AFTER`.

#### Scenario: Adapter transforms tool response
- **GIVEN** a `ToolAdapter` with `adapt_response()` implementation
- **AND** `MESSAGE_APPEND_BEFORE` fires with a `ToolMessage`
- **WHEN** the adapter transforms the response
- **THEN** `ctx.output` SHALL be set to the modified `ToolMessage`

#### Scenario: Non-tool messages pass through
- **GIVEN** a `ToolAdapter` registered on the agent
- **AND** `MESSAGE_APPEND_BEFORE` fires with a `UserMessage`
- **THEN** the handler SHALL NOT modify the message

#### Scenario: Messages without tool_response pass through
- **GIVEN** a `ToolMessage` without a `tool_response` attribute
- **WHEN** `MESSAGE_APPEND_BEFORE` fires
- **THEN** the adapter handler SHALL NOT attempt transformation

### Requirement: AgentComponent Adapter Handler
The `AgentComponent` base class SHALL provide a `_on_message_append_before_adapter` handler that applies registered `ToolAdapter` response transformations.

#### Scenario: Handler registered at correct priority
- **GIVEN** an `AgentComponent` with registered adapters
- **WHEN** installed on an agent
- **THEN** the handler SHALL be registered at priority 50 for `MESSAGE_APPEND_BEFORE`

#### Scenario: Handler checks enabled state
- **GIVEN** an `AgentComponent` with `enabled=False`
- **WHEN** `MESSAGE_APPEND_BEFORE` fires
- **THEN** the handler SHALL return early without processing

#### Scenario: Handler checks for adapters
- **GIVEN** an `AgentComponent` with no registered adapters
- **WHEN** `MESSAGE_APPEND_BEFORE` fires
- **THEN** the handler SHALL return early without processing

### Requirement: TOOL_CALL_AFTER Observational Only
The `TOOL_CALL_AFTER` event SHALL be purely observational - handlers SHALL NOT rely on `ctx.output` being used.

#### Scenario: TOOL_CALL_AFTER for logging
- **GIVEN** a handler registered for `TOOL_CALL_AFTER`
- **WHEN** a tool call completes
- **THEN** the handler SHALL receive the response for logging/metrics

#### Scenario: TOOL_CALL_AFTER output ignored
- **GIVEN** a handler registered for `TOOL_CALL_AFTER`
- **WHEN** the handler sets `ctx.output`
- **THEN** the value SHALL be ignored (event dispatched with `do()`)
