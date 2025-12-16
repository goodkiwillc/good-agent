# Tasks: Complete Event Coverage

## 1. Add New Event Definitions
- [ ] 1.1 Add `AGENT_CLOSE_BEFORE` to `AgentEvents` enum
- [ ] 1.2 Add `AGENT_CLOSE_AFTER` to `AgentEvents` enum
- [ ] 1.3 Verify `EXECUTE_ERROR` exists or add it
- [ ] 1.4 Verify `LLM_COMPLETE_ERROR` exists or add it

## 2. Add New TypedDicts
- [ ] 2.1 Add `AgentCloseParams` TypedDict
- [ ] 2.2 Add `ExecuteErrorParams` TypedDict
- [ ] 2.3 Add `ExecuteIterationAfterParams` TypedDict
- [ ] 2.4 Export all new types from `events/__init__.py`

## 3. Add Missing Dispatch Points
- [ ] 3.1 Add `EXECUTE_ITERATION_AFTER` dispatch in execute loop
- [ ] 3.2 Add `EXECUTE_ERROR` dispatch with `apply()` in execute error handler
- [ ] 3.3 Add `CONTEXT_PROVIDER_AFTER` dispatch in template manager
- [ ] 3.4 Add `LLM_COMPLETE_ERROR` dispatch in LLM complete error handler

## 4. Add Agent Close Lifecycle
- [ ] 4.1 Add `AGENT_CLOSE_BEFORE` dispatch in `Agent.close()`
- [ ] 4.2 Add `AGENT_CLOSE_AFTER` dispatch in `Agent.close()`
- [ ] 4.3 Add `AGENT_CLOSE_BEFORE` dispatch in `Agent.close_sync()`
- [ ] 4.4 Add `AGENT_CLOSE_AFTER` dispatch in `Agent.close_sync()`

## 5. Make Error Events Interceptable
- [ ] 5.1 Change `TOOL_CALL_ERROR` dispatch to `apply()` in `agent/tools.py`
- [ ] 5.2 Handle `ctx.return_value` as fallback ToolResponse
- [ ] 5.3 Ensure `EXECUTE_ERROR` uses `apply()` for recovery

## 6. Testing
- [ ] 6.1 Add test for `EXECUTE_ITERATION_AFTER` firing after each iteration
- [ ] 6.2 Add test for `EXECUTE_ERROR` interception with fallback
- [ ] 6.3 Add test for `TOOL_CALL_ERROR` fallback response
- [ ] 6.4 Add test for `AGENT_CLOSE_BEFORE/AFTER` lifecycle
- [ ] 6.5 Run existing test suite

## 7. Documentation
- [ ] 7.1 Update event docstrings
- [ ] 7.2 Document interceptable error events pattern
