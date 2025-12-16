# Change: Fix Tool Adapter Response Transformation

## Why

The ToolAdapter's response transformation is currently broken because it hooks into `TOOL_CALL_AFTER` which is dispatched with `do()` (fire-and-forget), meaning `ctx.output` modifications are ignored. With the new event foundation, response transformation should use `MESSAGE_APPEND_BEFORE` which is the natural interception point for modifying content before it's committed.

## What Changes

- Remove broken `_on_tool_call_after_adapter` handler from `AgentComponent`
- Add `_on_message_append_before_adapter` handler that transforms tool responses
- Add `ToolMessage.with_tool_response()` method for creating modified messages
- Update `TOOL_ADAPTER.md` documentation
- Add examples showing correct response transformation pattern

## Impact

- Affected specs: events (tool adapter pattern)
- Affected code:
  - `src/good_agent/core/components/component.py` - handler migration
  - `src/good_agent/messages/tool.py` - add `with_tool_response()` method
  - `docs/` or inline docs - update TOOL_ADAPTER.md
- Breaking: Components that relied on `TOOL_CALL_AFTER` for response modification need migration
- Dependencies: Requires Phase 1 (MESSAGE_APPEND_BEFORE dispatch)

## Requirements

### Requirement: Transform tool responses via MESSAGE_APPEND_BEFORE
Tool adapters SHALL apply response transformations during `MESSAGE_APPEND_BEFORE` so modified `ToolMessage` instances are appended.

#### Scenario: Tool response is transformed before append
- **GIVEN** a tool adapter with `adapt_response()` implemented
- **WHEN** `MESSAGE_APPEND_BEFORE` fires for a `ToolMessage`
- **THEN** the adapter SHALL set `ctx.output` to the transformed `ToolMessage`

### Requirement: Provide ToolMessage.with_tool_response helper
`ToolMessage` SHALL expose `with_tool_response(response: ToolResponse)` to create a new message with the updated response while preserving other fields.

#### Scenario: Helper returns updated message
- **GIVEN** an existing `ToolMessage`
- **WHEN** `with_tool_response(new_response)` is called
- **THEN** a new `ToolMessage` SHALL be returned with `tool_response=new_response` and other fields unchanged

### Requirement: TOOL_CALL_AFTER remains observational
`TOOL_CALL_AFTER` handlers SHALL be used for observation only and SHALL NOT rely on `ctx.output` being consumed.

#### Scenario: TOOL_CALL_AFTER output ignored
- **GIVEN** a handler registered for `TOOL_CALL_AFTER`
- **WHEN** the handler sets `ctx.output`
- **THEN** the value SHALL be ignored because the event is dispatched with `do()`
