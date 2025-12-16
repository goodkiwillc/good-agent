# Tasks: Agent Hooks Accessor

## 1. Create HooksAccessor Class
- [x] 1.1 Create `agent/hooks.py`
- [x] 1.2 Implement `HooksAccessor.__init__(self, agent)`
- [x] 1.3 Add private `_register()` helper method

## 2. Add Message Event Methods
- [x] 2.1 Add `on_message_append_before()` (interceptable)
- [x] 2.2 Add `on_message_append_after()` (signal)
- [x] 2.3 Add `on_message_create_before()` (interceptable)
- [x] 2.4 Add `on_message_create_after()` (signal)
- [x] 2.5 Add `on_message_render_before()` (interceptable)
- [x] 2.6 Add `on_message_render_after()` (signal)
- [x] 2.7 Add `on_message_replace_before()` (interceptable)
- [x] 2.8 Add `on_message_replace_after()` (signal)
- [x] 2.9 Add `on_message_set_system_before()` (interceptable)
- [x] 2.10 Add `on_message_set_system_after()` (signal)

## 3. Add Tool Event Methods
- [x] 3.1 Add `on_tool_call_before()` (interceptable)
- [x] 3.2 Add `on_tool_call_after()` (signal)
- [x] 3.3 Add `on_tool_call_error()` (interceptable for fallback)
- [x] 3.4 Add `on_tools_provide()` (interceptable)
- [x] 3.5 Add `on_tools_generate_signature()` (interceptable)

## 4. Add LLM Event Methods
- [x] 4.1 Add `on_llm_complete_before()` (interceptable)
- [x] 4.2 Add `on_llm_complete_after()` (signal)
- [x] 4.3 Add `on_llm_complete_error()` (signal)
- [x] 4.4 Add `on_llm_extract_before()` (interceptable)
- [x] 4.5 Add `on_llm_extract_after()` (signal)
- [x] 4.6 Add `on_llm_stream_before()` (interceptable)
- [x] 4.7 Add `on_llm_stream_after()` (signal)
- [x] 4.8 Add `on_llm_stream_chunk()` (signal)
- [x] 4.9 Add `on_llm_error()` (signal)

## 5. Add Execution Event Methods
- [x] 5.1 Add `on_execute_before()` (interceptable)
- [x] 5.2 Add `on_execute_after()` (signal)
- [x] 5.3 Add `on_execute_error()` (interceptable for recovery)
- [x] 5.4 Add `on_execute_iteration_before()` (interceptable)
- [x] 5.5 Add `on_execute_iteration_after()` (signal)

## 6. Add Agent Lifecycle Event Methods
- [x] 6.1 Add `on_agent_init_after()` (signal)
- [x] 6.2 Add `on_agent_close_before()` (interceptable)
- [x] 6.3 Add `on_agent_close_after()` (signal)
- [x] 6.4 Add `on_agent_state_change()` (signal)
- [x] 6.5 Add `on_agent_version_change()` (signal)

## 7. Add Mode Event Methods
- [x] 7.1 Add `on_mode_entering()` (signal)
- [x] 7.2 Add `on_mode_entered()` (signal)
- [x] 7.3 Add `on_mode_exiting()` (signal)
- [x] 7.4 Add `on_mode_exited()` (signal)

## 8. Integrate with Agent
- [x] 8.1 Add `_hooks_accessor` attribute to Agent
- [x] 8.2 Add `hooks` property that lazily creates HooksAccessor
- [x] 8.3 Export `HooksAccessor` from `agent/__init__.py`

## 9. Deprecate TypedEventHandlersMixin
- [x] 9.1 Add deprecation warning to `TypedEventHandlersMixin`
- [x] 9.2 Update docstring to point to `agent.hooks`

## 10. Testing
- [x] 10.1 Test `agent.hooks.on_message_append_before()` registration
- [x] 10.2 Test decorator syntax `@agent.hooks.on_tool_call_before`
- [x] 10.3 Test function syntax `agent.hooks.on_tool_call_before(handler)`
- [x] 10.4 Test priority and predicate parameters

## 11. Documentation
- [x] 11.1 Add comprehensive docstrings to all methods
- [x] 11.2 Document interceptable vs signal semantics in each method
- [x] 11.3 Add usage examples in module docstring
