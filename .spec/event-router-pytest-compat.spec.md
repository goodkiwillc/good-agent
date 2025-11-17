## Overview

Event router regression tests in `tests/unit/event_router` now fail after recent refactors and the pytest-asyncio 0.23 upgrade. The failures fall into two buckets: (1) async tests without `@pytest.mark.asyncio` now error under the plugin's strict mode, and (2) backwards-compatibility behaviors (context helpers, broadcast semantics, exception propagation) diverged from the expectations encoded in the unit tests. This spec outlines the changes required to restore the historical contract without forcing test updates.

## Requirements

1. **Pytest asyncio configuration** – Configure pytest so async tests run without individual `@pytest.mark.asyncio` decorators (`asyncio_mode = auto`) while keeping strict signal markers.
2. **EventContext compatibility** – Reintroduce legacy helpers used in tests: `ctx.event`, `ctx.stop(...)`, `ctx.stopped`, `ctx.stopped_with_exception`, and ensure `ctx.stop(exception=...)` stores the exception in `ctx.output`.
3. **Context population** – Every dispatch path (`do`, `apply_sync`, `apply_async`, typed variants) must populate `ctx.event` so handlers can inspect the originating event name.
4. **Exception semantics** – `apply_sync` should propagate synchronous handler exceptions (still capturing async ones), while `apply_async` must continue swallowing handler exceptions but allow manually raised `ApplyInterrupt` from async handlers to bubble when no stop flag was set.
5. **Broadcast routing** – `broadcast_to` should establish bidirectional routing without breaking the unidirectional `consume_from` behavior; recursion must avoid infinite loops when registries reference each other.

## Implementation Notes

- Extend `EventContext` (slots dataclass) with `event: str | None`, `_stopped_with_exception` flag, a backwards-compatible `stop()` helper, and `stopped`/`stopped_with_exception` properties. Update `stop_with_exception` to set both `exception` and `output` for legacy tests. Ensure all router dispatchers set `ctx.event` immediately after instantiation.
- In `core.EventRouter.apply_sync`, detect whether a handler is coroutine-based. Re-raise synchronous exceptions after recording them, but continue processing when async handlers fail (storing the latest exception). Adjust `ApplyInterrupt` handling so async manual raises bubble when `ctx.should_stop` is false.
- Mirror the same `ApplyInterrupt` logic inside `apply_async` while keeping normal exceptions contained in the context. The fire-and-forget `do()` path already ignores handler errors; no change needed beyond setting the event name.
- Introduce a private helper (or inline logic) so `broadcast_to` links registries both ways, while `consume_from` keeps the existing one-way semantics. Update `HandlerRegistry.get_sorted_handlers` to accept an internal `visited` set that prevents infinite recursion when traversing broadcast targets.
- Update `tests/pytest.ini` with pytest-asyncio settings, keeping existing markers untouched.

## Todo List

1. Update `tests/pytest.ini` with global pytest-asyncio configuration.
2. Enhance `EventContext` with legacy API surface (event name, stop helpers, stopped properties).
3. Ensure router dispatchers populate `ctx.event` and honor new stop semantics.
4. Rework exception handling in `apply_sync`/`apply_async` per requirement 4.
5. Implement bidirectional `broadcast_to` plus recursion guards in `HandlerRegistry` while leaving `consume_from` unidirectional.
6. Re-run `uv run pytest tests/unit/event_router -vv` and ensure all tests pass.

## Testing Strategy

- Primary validator: `uv run pytest tests/unit/event_router -vv`.
- Re-run targeted subsets if individual failures persist (e.g., decorator or broadcast modules) to speed up iteration.
