# Tasks: Event System Foundation

## 1. Add MessageAppendBeforeParams TypedDict
- [ ] 1.1 Add `MessageAppendBeforeParams` to `events/types.py`
- [ ] 1.2 Export from `events/__init__.py`

## 2. Add MESSAGE_APPEND_BEFORE Dispatch
- [ ] 2.1 Make `_append_message()` async in `agent/messages.py`
- [ ] 2.2 Add `apply()` dispatch for `MESSAGE_APPEND_BEFORE` before appending
- [ ] 2.3 Use `ctx.return_value` to allow message replacement
- [ ] 2.4 Audit and update all callers of `_append_message()` to use `await`

## 3. Fix :before Events Using Wrong Dispatch Method
- [ ] 3.1 Change `LLM_STREAM_BEFORE` from `do()` to `apply()` in `model/streaming.py`
- [ ] 3.2 Change `EXECUTE_BEFORE` from `do()` to `apply()` in `agent/core.py`
- [ ] 3.3 Change `EXECUTE_ITERATION_BEFORE` from `do()` to `apply()` in `agent/core.py`
- [ ] 3.4 Change `CONTEXT_PROVIDER_BEFORE` from `do()` to `apply()` in `template_manager/core.py`

## 4. Testing
- [ ] 4.1 Add test for `MESSAGE_APPEND_BEFORE` interception (modify message)
- [ ] 4.2 Add test for `MESSAGE_APPEND_BEFORE` observational (no modification)
- [ ] 4.3 Add test verifying `:before` events are interceptable
- [ ] 4.4 Run existing test suite and fix any regressions

## 5. Documentation
- [ ] 5.1 Update docstrings for modified methods
- [ ] 5.2 Add inline comments explaining dispatch semantics
