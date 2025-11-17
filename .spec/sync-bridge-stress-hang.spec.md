## Overview

The `tests/unit/event_router/test_sync_bridge_stress.py` suite intermittently hangs (typically around the ninth or tenth test) when exercising `EventRouter._sync_bridge` under heavy sync→async contention. The hang suggests the sync bridge worker thread is blocked awaiting completion of tasks that never signal, likely due to unbounded queue growth, missing wakeups, or deadlocked lifecycle handling when `join()`/`close()` interplay with in-flight tasks.

## Requirements

1. Reproduce the hang reliably by running the stress suite (and any related edge-case tests) in isolation to capture logs/stack traces.
2. Diagnose the sync bridge implementation (`sync_bridge.py` and its use in `EventRouter`) for potential deadlocks, missing timeouts, or thread-safety issues.
3. Patch the sync bridge so that:
   - `join()` completes even when tasks error or are cancelled.
   - Background worker threads drain queues and exit cleanly under stress.
   - Context handling remains thread-safe.
4. Ensure no regressions across existing sync bridge tests; add targeted regression tests if needed.

## Implementation Notes

- Capture current worker/queue architecture (likely a `queue.Queue` serviced by a single thread interacting with `asyncio` loop). Look for places where `task_done()` isnt called or futures arent awaited.
- Verify that `close()` cancels outstanding asyncio tasks and that `join()` waits on the correct condition; consider adding timeouts or sentinel messages to unblock the worker.
- Review `_sync_bridge.task_count` semantics to ensure it reflects pending work accurately under concurrent `do()` usage.
- Logging or debug counters may help pinpoint which handler/task is stuck; keep instrumentation behind tests only if necessary.

## Todo List

1. Understand `_sync_bridge` design and identify where a hang could occur under concurrent load.
2. Reproduce hanging test with focused pytest invocation; capture stack traces if the process stalls.
3. Implement fixes (likely around queue/task lifecycle) and update/extend tests to cover the scenario.
4. Run full validator suite (ruff, type checks, pytest) to confirm stability.

## Testing Strategy

- `uv run pytest tests/unit/event_router/test_sync_bridge_stress.py -vv`
- Broader router coverage: `uv run pytest tests/unit/event_router`
- Repository-wide checks: `uv run ruff check .`, `uv run pytest`
