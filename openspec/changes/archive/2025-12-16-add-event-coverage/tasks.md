# Tasks: Complete Event Coverage

## 1. Add New Event Definitions
- [x] 1.1 Add `AGENT_CLOSE_BEFORE` to `AgentEvents` enum
- [x] 1.2 Add `AGENT_CLOSE_AFTER` to `AgentEvents` enum
- [x] 1.3 Verify `EXECUTE_ERROR` exists or add it
- [x] 1.4 Verify `LLM_COMPLETE_ERROR` exists or add it

## 2. Add New TypedDicts
- [x] 2.1 Add `AgentCloseParams` TypedDict
- [x] 2.2 Add `ExecuteErrorParams` TypedDict
- [x] 2.3 Add `ExecuteIterationAfterParams` TypedDict
- [x] 2.4 Export all new types from `events/__init__.py`

## 3. Add Missing Dispatch Points
- [x] 3.1 Add `EXECUTE_ITERATION_AFTER` dispatch in execute loop
- [x] 3.2 Add `EXECUTE_ERROR` dispatch with `apply()` in execute error handler
- [x] 3.3 Add `CONTEXT_PROVIDER_AFTER` dispatch in template manager
- [x] 3.4 Add `LLM_COMPLETE_ERROR` dispatch in LLM complete error handler

## 4. Add Agent Close Lifecycle
- [x] 4.1 Add `AGENT_CLOSE_BEFORE` dispatch in `Agent.close()`
- [x] 4.2 Add `AGENT_CLOSE_AFTER` dispatch in `Agent.close()`
- [x] 4.3 Add `AGENT_CLOSE_BEFORE` dispatch in `Agent.close_sync()`
- [x] 4.4 Add `AGENT_CLOSE_AFTER` dispatch in `Agent.close_sync()`

## 5. Make Error Events Interceptable
- [x] 5.1 Change `TOOL_CALL_ERROR` dispatch to `apply()` in `agent/tools.py`
- [x] 5.2 Handle `ctx.return_value` as fallback ToolResponse
- [x] 5.3 Ensure `EXECUTE_ERROR` uses `apply()` for recovery

## 6. Testing
- [x] 6.1 Add test for `EXECUTE_ITERATION_AFTER` firing after each iteration
- [x] 6.2 Add test for `EXECUTE_ERROR` interception with fallback
- [x] 6.3 Add test for `TOOL_CALL_ERROR` fallback response
- [x] 6.4 Add test for `AGENT_CLOSE_BEFORE/AFTER` lifecycle
- [x] 6.5 Run existing test suite

## 7. Documentation
- [x] 7.1 Update event docstrings
- [x] 7.2 Document interceptable error events pattern
