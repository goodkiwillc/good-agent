# Overview

We previously introduced backwards-compatibility shim modules (for `good_agent.config`, `good_agent.store`, etc.) while refactoring the package layout. The user confirmed we can now remove those shims and update all references to the new module locations. This work eliminates redundant modules, removes deprecation warnings, and ensures consumers use the canonical package structure.

# Requirements

1. Replace every import/reference to legacy modules (`good_agent.base`, `config`, `config_types`, `context`, `conversation`, `pool`, `thread_context`, `store`, `validation`, `versioning`, `interfaces`, `type_guards`, `spec`) with their new canonical counterparts under `good_agent.agent.*`, `good_agent.messages.*`, or `good_agent.utilities.typing` as appropriate, covering source, tests, and examples.
2. Remove the shim files themselves from `src/good_agent` once no code references them.
3. Ensure package exports remain usable via `good_agent.__init__` (lazy imports should already point to new module paths; adjust if necessary but avoid reintroducing shims).
4. Update any string-based references (e.g., `patch("good_agent.store.put_message")`, import-performance expectation lists) to match the new modules.
5. Retain functionality and type coverage—no regressions in lint/tests.

# Implementation Notes

- Use `rg` to find all `good_agent.<module>` occurrences and verify relative imports (e.g., `from ..base import Index`). Only two production modules (`good_agent/extensions/index.py` and `good_agent/extensions/citations/index.py`) still reference `good_agent.base` and must point to `good_agent.core.indexing`.
- Examples/tests under `examples/context/*`, `examples/pool/*`, and `tests/unit/**/*` still import the shim modules; rewrite those to use `good_agent.agent.config`, `good_agent.agent.pool`, `good_agent.agent.thread_context`, `good_agent.messages.store`, etc.
- Some tests patch strings targeting `good_agent.store`; update those to `good_agent.messages.store`.
- After all references are updated, delete the shim files (`base.py`, `config.py`, ... , `type_guards.py`, `spec.py`).
- Re-run linter/tests to confirm no missing imports.

# Todo List

1. Enumerate and update all code/tests/examples that still import the shim modules.
2. Remove the deprecated shim modules from `src/good_agent`.
3. Verify package exports (especially `good_agent.__init__`) and adjust if anything still references removed modules.
4. Run validators (`uv run ruff check`, `uv run pytest`).

# Testing Strategy

- `uv run ruff check`
- `uv run pytest`
