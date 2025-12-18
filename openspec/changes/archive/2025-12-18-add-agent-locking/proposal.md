# Proposal: Add Agent locking for thread safety

## Summary
Add a minimal concurrency guard to Agent so overlapping async operations (call/execute/message append/tool dispatch) on the same instance are serialized, preventing racey interleaving and preserving message order.

## Why
- Agents were explicitly “Not thread-safe,” allowing overlapping call/execute/tool flows to interleave message and mode mutations, causing ordering bugs and pending-call tracking errors.
- Tool emissions and event handlers could mutate shared state concurrently, leading to non-deterministic histories and potential deadlocks when mixed with sync bridges.
- Cross-thread use lacked a safe entry path, so callers risked racing the agent loop.

## What Changes
- Introduce a per-Agent reentrant async lock and guard all state mutations (message append/replace/system set, mode transitions, execute bookkeeping, tool emissions) while keeping tool execution parallel.
- Add a threadsafe proxy to schedule Agent operations from other threads onto the Agent loop under the lock.
- Provide guarded helpers (`state_guard`, `run_state_guarded`) so mutating handlers/components can execute safely; keep non-mutating handlers unchanged.

## Background
- Agent is documented as “Not thread-safe”; multiple overlapping execute/call/tool flows can mutate shared `_messages`, mode state, and tool resolution without coordination.
- ToolExecutor uses `asyncio.gather` to run tools in parallel but emits messages unsynchronized, risking out-of-order appends and pending-call tracking errors.

## Goals
- Provide an Agent-level async lock that serializes mutating operations (message append/replace, execute loop iterations, mode transitions, tool result emission) so concurrent calls on one Agent do not corrupt state.
- Keep tool execution parallel where useful, but funnel stateful side effects through the serialized path to retain deterministic ordering.
- Offer a safe entry surface for cross-thread usage (e.g., a proxy that marshals work onto the Agent loop and respects the lock).

## Non-Goals
- Global process-wide locking across Agents (each Agent remains independent).
- Broad refactors of the event system beyond ensuring mutating handlers can optionally run under the guard.

## Open Questions
- Should the lock be opt-out (default on, configurable) for backwards compatibility with highly concurrent callers? If configurable, what is the default?
- Should `do()`-dispatched handlers that mutate Agent state be forced through a serialized path, or is documenting best-effort sufficient?
