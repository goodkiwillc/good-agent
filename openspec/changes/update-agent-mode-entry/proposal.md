# Change: Simplify Agent Mode entry API

## Why
- Users currently register modes via `@agent.modes("name")` but enter them through the plural-index form `agent.modes["name"]`, while state is exposed via `agent.mode`; the mismatch is confusing, error-prone, and contradicts the `agent.mode` accessor naming.
- The bracket-based API is also harder to discover in type hints and has been flagged in docs as unintuitive; unified naming improves ergonomics before the API stabilizes.

## What Changes
- Keep the decorator-based registration (`@agent.modes("name")`) exactly as-is to avoid churn for mode authors.
- Replace the plural-index entry point with a singular callable: `agent.mode("name")` (optionally parameterized) returns an async context manager for that mode.
- Remove `agent.modes["name"]` and related overloads entirely—this is a **BREAKING** change with no shims or migrations.
- Update the `ModeManager`, `ModeAccessor`, and `Agent` core to expose the new entry API, plus adjust any helper utilities/tests referencing the old pattern.
- Refresh documentation, tutorials, and examples so all snippets use `agent.mode("name")` and describe the revised interface.

## Impact
- **Specs**: Introduce an `agent-modes` capability spec documenting the new entry semantics.
- **Code**: `src/good_agent/agent/core.py`, `src/good_agent/agent/modes.py`, mode-related helpers, and any consumers in `examples/`, `docs/`, and CLI entrypoints.
- **Tests**: Update mode unit tests/integration flows under `tests/agent/` and `tests/examples/` to exercise the new API.
- **Docs**: `docs/features/modes.md`, README usage snippets, and AGENTS.md quickstart must all reflect the singular `agent.mode("name")` usage.
