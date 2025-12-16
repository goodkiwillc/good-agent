# Event System Overhaul

Reference document for the event system overhaul implementation.

**Master Spec**: `~/.factory/docs/2025-12-16-event-system-overhaul-comprehensive-specification.md`

## Core Design Principle

- **All `:before` events are interceptable** - dispatched with `apply()`, handlers can modify `ctx.output`
- **All `:after` events are observational** - dispatched with `do()`, fire-and-forget

## Implementation Phases

### Phase 1: `refactor-event-foundation` (BLOCKING)
**Priority**: Critical - All other phases depend on this

Add the foundational event dispatch fixes:
- Add `MESSAGE_APPEND_BEFORE` dispatch (critical gap)
- Fix `:before` events to use `apply()` instead of `do()`
- Makes `_append_message()` async

```bash
openspec show refactor-event-foundation
```

### Phase 2: `add-event-coverage`
**Priority**: High
**Depends on**: Phase 1

Complete the event coverage:
- Add `EXECUTE_ITERATION_AFTER`, `EXECUTE_ERROR` dispatches
- Add `AGENT_CLOSE_BEFORE/AFTER` events
- Make `TOOL_CALL_ERROR` and `EXECUTE_ERROR` interceptable for fallback/recovery

```bash
openspec show add-event-coverage
```

### Phase 3: `add-event-registry`
**Priority**: Medium
**Depends on**: Phase 1, 2

Formalize event semantics and tooling:
- Create `EventSemantics` classification (INTERCEPTABLE vs SIGNAL)
- Create `EVENT_PARAMS` registry mapping events to TypedDicts
- Remove deprecated event aliases
- Document extension point events

```bash
openspec show add-event-registry
```

### Phase 4: `add-agent-hooks`
**Priority**: Medium
**Depends on**: Phase 1, 2, 3

Developer experience improvements:
- Create `HooksAccessor` class with typed methods
- Add `agent.hooks` property
- Deprecate `TypedEventHandlersMixin`

```bash
openspec show add-agent-hooks
```

### Phase 5: `fix-tool-adapter`
**Priority**: High
**Depends on**: Phase 1

Fix the broken ToolAdapter response transformation:
- Migrate from `TOOL_CALL_AFTER` to `MESSAGE_APPEND_BEFORE`
- Add `ToolMessage.with_tool_response()` helper
- Update documentation

```bash
openspec show fix-tool-adapter
```

## Dependency Graph

```
Phase 1 (foundation)
    │
    ├──────────────────┐
    │                  │
    v                  v
Phase 2 (coverage)   Phase 5 (tool-adapter)
    │
    v
Phase 3 (registry)
    │
    v
Phase 4 (hooks)
```

## Quick Commands

```bash
# List all changes
openspec list

# View specific change
openspec show <change-id>

# Validate a change
openspec validate <change-id> --strict

# After completing a phase
openspec archive <change-id> --yes
```

## Key Files Affected

| Phase | Key Files |
|-------|-----------|
| 1 | `agent/messages.py`, `agent/core.py`, `model/streaming.py`, `events/types.py` |
| 2 | `agent/core.py`, `agent/tools.py`, `events/agent.py`, `events/types.py` |
| 3 | `events/classification.py` (new), `events/registry.py` (new), `events/agent.py` |
| 4 | `agent/hooks.py` (new), `agent/core.py`, `events/decorators.py` |
| 5 | `core/components/component.py`, `messages/tool.py`, `TOOL_ADAPTER.md` |

## Testing Strategy

Each phase should:
1. Run `uv run pytest` before starting
2. Implement changes
3. Add tests for new functionality
4. Run `uv run pytest` to verify no regressions
5. Run `uv run ruff check` and `uv run ruff format`

## Breaking Changes

- **Phase 1**: `_append_message()` becomes async - audit all callers (NOTE:this is now changed)
- **Phase 3**: Deprecated event aliases removed
- **Phase 5**: Components using `TOOL_CALL_AFTER` for response modification must migrate
