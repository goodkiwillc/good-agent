# Tasks: Agent Hooks Accessor

## 1. Create HooksAccessor Class
- [ ] 1.1 Create `agent/hooks.py`
- [ ] 1.2 Implement `HooksAccessor.__init__(self, agent)`
- [ ] 1.3 Add private `_register()` helper method

## 2. Add Message Event Methods
- [ ] 2.1 Add `on_message_append_before()` (interceptable)
- [ ] 2.2 Add `on_message_append_after()` (signal)
- [ ] 2.3 Add `on_message_create_before()` (interceptable)
- [ ] 2.4 Add `on_message_create_after()` (signal)
- [ ] 2.5 Add `on_message_render_before()` (interceptable)
- [ ] 2.6 Add `on_message_render_after()` (signal)
- [ ] 2.7 Add `on_message_replace_before()` (interceptable)
- [ ] 2.8 Add `on_message_replace_after()` (signal)
- [ ] 2.9 Add `on_message_set_system_before()` (interceptable)
- [ ] 2.10 Add `on_message_set_system_after()` (signal)

## 3. Add Tool Event Methods
- [ ] 3.1 Add `on_tool_call_before()` (interceptable)
- [ ] 3.2 Add `on_tool_call_after()` (signal)
- [ ] 3.3 Add `on_tool_call_error()` (interceptable for fallback)
- [ ] 3.4 Add `on_tools_provide()` (interceptable)
- [ ] 3.5 Add `on_tools_generate_signature()` (interceptable)

## 4. Add LLM Event Methods
- [ ] 4.1 Add `on_llm_complete_before()` (interceptable)
- [ ] 4.2 Add `on_llm_complete_after()` (signal)
- [ ] 4.3 Add `on_llm_complete_error()` (signal)
- [ ] 4.4 Add `on_llm_extract_before()` (interceptable)
- [ ] 4.5 Add `on_llm_extract_after()` (signal)
- [ ] 4.6 Add `on_llm_stream_before()` (interceptable)
- [ ] 4.7 Add `on_llm_stream_after()` (signal)
- [ ] 4.8 Add `on_llm_stream_chunk()` (signal)
- [ ] 4.9 Add `on_llm_error()` (signal)

## 5. Add Execution Event Methods
- [ ] 5.1 Add `on_execute_before()` (interceptable)
- [ ] 5.2 Add `on_execute_after()` (signal)
- [ ] 5.3 Add `on_execute_error()` (interceptable for recovery)
- [ ] 5.4 Add `on_execute_iteration_before()` (interceptable)
- [ ] 5.5 Add `on_execute_iteration_after()` (signal)

## 6. Add Agent Lifecycle Event Methods
- [ ] 6.1 Add `on_agent_init_after()` (signal)
- [ ] 6.2 Add `on_agent_close_before()` (interceptable)
- [ ] 6.3 Add `on_agent_close_after()` (signal)
- [ ] 6.4 Add `on_agent_state_change()` (signal)
- [ ] 6.5 Add `on_agent_version_change()` (signal)

## 7. Add Mode Event Methods
- [ ] 7.1 Add `on_mode_entering()` (signal)
- [ ] 7.2 Add `on_mode_entered()` (signal)
- [ ] 7.3 Add `on_mode_exiting()` (signal)
- [ ] 7.4 Add `on_mode_exited()` (signal)

## 8. Integrate with Agent
- [ ] 8.1 Add `_hooks_accessor` attribute to Agent
- [ ] 8.2 Add `hooks` property that lazily creates HooksAccessor
- [ ] 8.3 Export `HooksAccessor` from `agent/__init__.py`

## 9. Deprecate TypedEventHandlersMixin
- [ ] 9.1 Add deprecation warning to `TypedEventHandlersMixin`
- [ ] 9.2 Update docstring to point to `agent.hooks`

## 10. Testing
- [ ] 10.1 Test `agent.hooks.on_message_append_before()` registration
- [ ] 10.2 Test decorator syntax `@agent.hooks.on_tool_call_before`
- [ ] 10.3 Test function syntax `agent.hooks.on_tool_call_before(handler)`
- [ ] 10.4 Test priority and predicate parameters

## 11. Documentation
- [ ] 11.1 Add comprehensive docstrings to all methods
- [ ] 11.2 Document interceptable vs signal semantics in each method
- [ ] 11.3 Add usage examples in module docstring
