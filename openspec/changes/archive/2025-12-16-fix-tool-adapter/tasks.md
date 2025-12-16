# Tasks: Fix Tool Adapter Response Transformation

## 1. Add ToolMessage Helper Method
- [x] 1.1 Add `with_tool_response(response: ToolResponse)` method to `ToolMessage`
- [x] 1.2 Method SHALL return new `ToolMessage` with updated `tool_response`
- [x] 1.3 Method SHALL preserve all other message fields
- [x] 1.4 Add unit tests for `with_tool_response()`

## 2. Migrate AgentComponent Handler
- [x] 2.1 Remove `_on_tool_call_after_adapter` handler from `AgentComponent`
- [x] 2.2 Add `_on_message_append_before_adapter` handler
- [x] 2.3 Handler SHALL only process `ToolMessage` instances
- [x] 2.4 Handler SHALL check if message has `tool_response`
- [x] 2.5 Handler SHALL apply `adapt_response()` from adapter registry
- [x] 2.6 Handler SHALL set `ctx.output` to modified message if changed

## 3. Update ToolAdapterRegistry
- [x] 3.1 Verify `adapt_response()` works with new pattern
- [x] 3.2 Update any internal state management if needed

## 4. Update Documentation
- [x] 4.1 Update `TOOL_ADAPTER.md` to reference `MESSAGE_APPEND_BEFORE`
- [x] 4.2 Add example showing response transformation pattern
- [x] 4.3 Document that `TOOL_CALL_AFTER` is purely observational
- [x] 4.4 Add migration guide for existing adapters

## 5. Testing
- [x] 5.1 Add test for tool response transformation via `MESSAGE_APPEND_BEFORE`
- [x] 5.2 Add test verifying adapter modifies message before append
- [x] 5.3 Add test verifying non-tool messages pass through unchanged
- [x] 5.4 Add test verifying adapters without response transformation work
- [x] 5.5 Run existing ToolAdapter tests

## 6. Migration Check
- [x] 6.1 Search codebase for `TOOL_CALL_AFTER` handlers that modify `ctx.output`
- [x] 6.2 Update any found handlers to use `MESSAGE_APPEND_BEFORE`
