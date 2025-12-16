## 1. Implementation
- [x] 1.1 Refactor `ModeManager`/`ModeAccessor` so entering a mode happens via `agent.mode(name, **params)` returning the async context manager, and delete the `agent.modes["name"]` path.
- [x] 1.2 Update `Agent` core wiring, public attributes, and docstrings to expose the singular entry API while keeping the decorator-based registration unchanged.
- [x] 1.3 Adjust unit/integration tests (mode lifecycle, scheduling, standalone modes, docs examples) to target `agent.mode("name")`.
- [x] 1.4 Refresh documentation, README snippets, and examples to demonstrate the new entry syntax and call out the breaking change.
- [x] 1.5 Run validators: `uv run ruff check`, `uv run mypy src tests`, and `uv run pytest` (or targeted suites) to ensure the new API passes lint, type, and test gates.
