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
