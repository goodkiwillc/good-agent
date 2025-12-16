# Change: Event System Foundation

## Why

The event system currently has inconsistent dispatch semantics - some `:before` events use `do()` (fire-and-forget) when they should use `apply()` (interceptable), and the critical `MESSAGE_APPEND_BEFORE` event is defined but never dispatched, blocking the ToolAdapter response transformation pattern.

## What Changes

- **BREAKING**: `_append_message()` becomes async to support interceptable `MESSAGE_APPEND_BEFORE`
- Add `MESSAGE_APPEND_BEFORE` dispatch point with `apply()` for message interception
- Fix `LLM_STREAM_BEFORE` to use `apply()` instead of `do()`
- Fix `EXECUTE_BEFORE` to use `apply()` instead of `do()`
- Fix `EXECUTE_ITERATION_BEFORE` to use `apply()` instead of `do()`
- Fix `CONTEXT_PROVIDER_BEFORE` to use `apply()` instead of `do()`
- Add `MessageAppendBeforeParams` TypedDict

## Impact

- Affected specs: events (new capability spec)
- Affected code:
  - `src/good_agent/agent/messages.py` - `_append_message()` async conversion
  - `src/good_agent/agent/core.py` - execute() dispatch changes
  - `src/good_agent/model/streaming.py` - LLM_STREAM_BEFORE dispatch
  - `src/good_agent/extensions/template_manager/core.py` - context provider dispatch
  - `src/good_agent/events/types.py` - new TypedDict
- Breaking: Any code calling `_append_message()` synchronously must be updated
- Dependencies: None
