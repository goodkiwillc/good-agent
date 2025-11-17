# Agent API Reference

Phase 4 reduced `Agent` to a hard-capped surface of **30 public entries**. The
table below mirrors the allow-list returned by
`good_agent.agent.Agent.public_attribute_names()` so feature work can stay within
the agreed budget.

Each row links to a runnable example (living under `examples/`) or includes a
plain snippet illustrating preferred usage. The new `tests/test_examples.py`
suite executes all examples to prevent `DeprecationWarning` regressions.

## Stable Surface (30 entries)

| Symbol | Kind | Summary | Examples |
| --- | --- | --- | --- |
| `EVENTS` | Constant | Alias to `AgentEvents`; import once and reference enum members when wiring lifecycle hooks. | `examples/events/basic_events.py` |
| `append` | Method | Canonical way to add user/assistant/tool/system messages; supersedes `set_system_message()` and `replace_message()`. | `examples/agent/basic_chat.py` |
| `assistant` | Property | Filtered `MessageList` exposing only assistant authored messages (useful for telemetry or analytics). | `examples/agent/basic_chat.py` |
| `call` | Async method | Single LLM turn that returns the final `AssistantMessage`. | `examples/agent/basic_chat.py` |
| `config` | Attribute | `AgentConfigManager` bound to this agent; mutate to tweak temperature, provider defaults, and render modes. | `examples/context/thread_context.py` |
| `context` | Attribute | `AgentContext` shared with templates and events; layered overrides live here. | `examples/context/thread_context.py` |
| `context_manager` | Facade | Fork/thread/spawn scoped agents and register context providers. | `examples/context/thread_context.py` |
| `do` | Method | Fire EventRouter events synchronously; ideal for instrumentation hooks that should not await. | `examples/event_router/basic_usage.py` |
| `events` | Facade | Full EventRouter API (`apply`, `broadcast_to`, tracing, etc.) exposed via the new facade. | `examples/event_router/basic_usage.py` |
| `execute` | Async iterator | Runs the multi-turn loop, yielding every assistant/tool/system message until completion. | `examples/agent/basic_chat.py` |
| `extensions` | Property | Mapping of installed `AgentComponent` instances keyed by dotted name. | `examples/components/basic_component.py` |
| `id` | Property | ULID that uniquely identifies this agent instance; stable until the process disposes it. | `examples/pool/agent_pool.py` |
| `messages` | Property | Underlying `MessageList`; supports slicing, direct assignment, and version tracking. | `examples/agent/basic_chat.py` |
| `model` | Property | Active `LanguageModel` (mock or real) powering completions/streaming. | `examples/agent/basic_chat.py` |
| `name` | Property | Optional friendly name for logs, pools, or registries. | `examples/pool/agent_pool.py` |
| `on` | Decorator | Register event handlers on the agent; thin wrapper over `EventRouter.on`. | `examples/events/basic_events.py` |
| `initialize` | Async method | Replaces `ready()`; installs components, registers tools, and warms caches. | `examples/pool/agent_pool.py` |
| `is_ready` | Property | Cheap readiness flag tied to the state machine. | `examples/pool/agent_pool.py` |
| `session_id` | Property | ULID shared across forks spawned from the same conversation. | `examples/pool/agent_pool.py` |
| `state` | Property | Snapshot of the `AgentStateMachine` (INITIALIZING, READY, etc.). | `examples/agent/basic_chat.py` |
| `system` | Property | Filtered `MessageList` containing system prompts (typically index 0). | `examples/agent/basic_chat.py` |
| `task_count` | Property | Number of active tasks managed by `agent.tasks`. | `examples/pool/agent_pool.py` |
| `tasks` | Facade | Task orchestration facade (`create`, `join`, `stats`) replacing `create_task()`/`wait_for_tasks()`. | `examples/pool/agent_pool.py` |
| `tool` | Property | Filtered view of tool role messages (after calling `agent.append(..., role="tool")`). | `examples/tools/basic_tool.py` |
| `tool_calls` | Facade | Tool executor facade for `invoke`, `record_invocation(s)`, and resolving pending tool calls. | `examples/tools/basic_tool.py` |
| `tools` | Property | Underlying `ToolManager`; inspect registered tools or call them directly. | `examples/tools/basic_tool.py` |
| `user` | Property | Filtered `MessageList` for user messages only. | `examples/agent/basic_chat.py` |
| `validate_message_sequence` | Method | Validates ordering/roles before sending to the LLM; typically called before custom LLM integrations. | `tests/unit/agent/test_agent_message_store_integration.py` |
| `version_id` | Property | ULID that increments when the message list mutates; use for optimistic concurrency. | `examples/resources/editable_mdxl.py` |
| `versioning` | Facade | Access to `AgentVersioningManager` (revert, audit history). | `examples/resources/editable_mdxl.py` |

### Usage Notes

- **Facades vs core methods** – The four facades (`events`, `context_manager`,
  `tasks`, `tool_calls`) now host the bulk of the advanced APIs. Keep new entry
  points on those facades to avoid blowing the 30-item ceiling.
- **Message filters** – `assistant`, `user`, `system`, and `tool` each return a
  `FilteredMessageList`. They are inexpensive views and safe to access per
  request.
- **Deprecation guard** – If you rely on an attribute that no longer appears
  here, expect it to emit a `DeprecationWarning` and disappear in v1.0.0. Consult
  `MIGRATION.md` for the exact replacement recipe.

For a full migration narrative—including before/after snippets for each shim—see
[`MIGRATION.md`](../MIGRATION.md#phase-4-agent-api-surface-reduction).
