# Agent API Reference

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

This document provides a comprehensive reference for the public API of the `Agent` class.

Each row in the summary table links to a runnable example (living under `examples/`) or includes a
plain snippet illustrating preferred usage. The new `tests/test_examples.py`
suite executes all examples to prevent `DeprecationWarning` regressions.

## Public API Summary

| Symbol | Kind | Summary | Examples |
| --- | --- | --- | --- |
| `EVENTS` | Constant | Alias to `AgentEvents`; import once and reference enum members when wiring lifecycle hooks. | [examples/events/basic_events.py](https://github.com/goodkiwi/good-agent/blob/main/examples/events/basic_events.py) |
| `append` | Method | Canonical way to add user/assistant/tool/system messages; supersedes `set_system_message()` and `replace_message()`. | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `assistant` | Property | Filtered `MessageList` exposing only assistant authored messages (useful for telemetry or analytics). | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `call` | Async method | Single LLM turn that returns the final `AssistantMessage`. | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `config` | Attribute | `AgentConfigManager` bound to this agent; mutate to tweak temperature, provider defaults, and render modes. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `context` | Attribute | `AgentContext` shared with templates and events; layered overrides live here. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `context_manager` | Facade | **Deprecated.** Use direct methods: `fork()`, `fork_context()`, `thread_context()`, `context_provider()`. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `do` | Method | Fire EventRouter events synchronously; ideal for instrumentation hooks that should not await. | [examples/event_router/basic_usage.py](https://github.com/goodkiwi/good-agent/blob/main/examples/event_router/basic_usage.py) |
| `events` | Property | Returns `self` (Agent inherits from EventRouter). Use `agent.apply()`, `agent.on()` directly. | [examples/event_router/basic_usage.py](https://github.com/goodkiwi/good-agent/blob/main/examples/event_router/basic_usage.py) |
| `execute` | Async iterator | Runs the multi-turn loop, yielding every assistant/tool/system message until completion. | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `extensions` | Property | Mapping of installed `AgentComponent` instances keyed by dotted name. | [examples/components/basic_component.py](https://github.com/goodkiwi/good-agent/blob/main/examples/components/basic_component.py) |
| `id` | Property | ULID that uniquely identifies this agent instance; stable until the process disposes it. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `messages` | Property | Underlying `MessageList`; supports slicing, direct assignment, and version tracking. | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `model` | Property | Active `LanguageModel` (mock or real) powering completions/streaming. | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `name` | Property | Optional friendly name for logs, pools, or registries. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `on` | Decorator | Register event handlers on the agent; thin wrapper over `EventRouter.on`. | [examples/events/basic_events.py](https://github.com/goodkiwi/good-agent/blob/main/examples/events/basic_events.py) |
| `initialize` | Async method | Replaces `ready()`; installs components, registers tools, and warms caches. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `is_ready` | Property | Cheap readiness flag tied to the state machine. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `session_id` | Property | ULID shared across forks spawned from the same conversation. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `state` | Property | Snapshot of the `AgentStateMachine` (INITIALIZING, READY, etc.). | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `system` | Property | Filtered `MessageList` containing system prompts (typically index 0). | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `task_count` | Property | Number of active tasks managed by `agent.tasks`. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `tasks` | Facade | Task orchestration facade (`create`, `join`, `stats`) replacing `create_task()`/`wait_for_tasks()`. | [examples/pool/agent_pool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/pool/agent_pool.py) |
| `tool` | Property | Filtered view of tool role messages (after calling `agent.append(..., role="tool")`). | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `tool_calls` | Facade | **Deprecated.** Use direct methods: `invoke()`, `invoke_func()`, `invoke_many()`, `add_tool_invocation()`. | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `tools` | Property | Underlying `ToolManager`; inspect registered tools or call them directly. | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `user` | Property | Filtered `MessageList` for user messages only. | [examples/agent/basic_chat.py](https://github.com/goodkiwi/good-agent/blob/main/examples/agent/basic_chat.py) |
| `invoke` | Async method | Execute a tool directly, returning the result. Replaces `tool_calls.invoke()`. | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `invoke_func` | Async method | Execute a tool function with partial arguments. Replaces `tool_calls.invoke_func()`. | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `invoke_many` | Async method | Execute multiple tools in parallel. Replaces `tool_calls.invoke_many()`. | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `add_tool_invocation` | Method | Record a tool invocation result. Replaces `tool_calls.record_invocation()`. | [examples/tools/basic_tool.py](https://github.com/goodkiwi/good-agent/blob/main/examples/tools/basic_tool.py) |
| `fork` | Async method | Create a forked copy of the agent. Replaces `context_manager.fork()`. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `fork_context` | Method | Context manager for forked agent operations. Replaces `context_manager.fork_context()`. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `thread_context` | Method | Context manager for temporary message modifications. Replaces `context_manager.thread_context()`. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `context_provider` | Decorator | Register instance-specific context providers. | [examples/context/thread_context.py](https://github.com/goodkiwi/good-agent/blob/main/examples/context/thread_context.py) |
| `validate_message_sequence` | Method | Validates ordering/roles before sending to the LLM; typically called before custom LLM integrations. | [tests/unit/agent/test_agent_message_store_integration.py](https://github.com/goodkiwi/good-agent/blob/main/tests/unit/agent/test_agent_message_store_integration.py) |
| `version_id` | Property | ULID that increments when the message list mutates; use for optimistic concurrency. | [examples/resources/editable_mdxl.py](https://github.com/goodkiwi/good-agent/blob/main/examples/resources/editable_mdxl.py) |
| `versioning` | Facade | Access to `AgentVersioningManager` (revert, audit history). | [examples/resources/editable_mdxl.py](https://github.com/goodkiwi/good-agent/blob/main/examples/resources/editable_mdxl.py) |

## Detailed API Documentation

::: good_agent.Agent
    options:
      show_root_heading: true
      show_source: false


### Usage Notes

- **Direct methods preferred** – The `context_manager` and `tool_calls` facades are
  deprecated. Use direct Agent methods like `invoke()`, `fork()`, `thread_context()` instead.
  The `events` property now returns `self` since Agent inherits from EventRouter.
- **Active facades** – `tasks` and `versioning` remain the recommended facades for
  task orchestration and version management.
- **Message filters** – `assistant`, `user`, `system`, and `tool` each return a
  `FilteredMessageList`. They are inexpensive views and safe to access per
  request.
- **Deprecation guard** – If you rely on an attribute that no longer appears
  here, expect it to emit a `DeprecationWarning` and disappear in v1.0.0.
