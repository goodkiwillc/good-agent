# Design: Agent locking for thread safety

## Current state
- Agent is marked “Not thread-safe” and has no guard around `_messages`, `_mode_manager`, or `_tool_executor`.
- ToolExecutor runs tools in parallel (`asyncio.gather`) and emits messages unsynchronized, so emissions can interleave with other agent calls.
- `do()` dispatch is fire-and-forget; async handlers can mutate Agent concurrently.

## Proposed approach
- Add an Agent-level async lock (per-instance) to serialize mutating operations: message append/replace, version updates, execute iteration bookkeeping, mode transitions, and tool-message emission. Keep tool execution parallel but funnel their side effects through the lock to preserve ordering.
- Provide a thread-safe proxy or helper that schedules Agent coroutines onto its loop (e.g., via `asyncio.run_coroutine_threadsafe`) while respecting the lock, enabling cross-thread usage without races.
- Offer a guarded path for event handlers that mutate Agent state: either run them under the lock or explicitly document that only non-mutating handlers should use `do()`; prefer using `apply` for mutating hooks.

## Compatibility considerations
- Default-on locking minimizes surprises; consider opt-out flag for callers relying on concurrent mutation (documented as unsafe today).
- Preserve public APIs; changes are behavioral (serialization) and should not alter tool parallelism or event semantics beyond ordering guarantees for Agent state changes.
