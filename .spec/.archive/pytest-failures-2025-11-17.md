## Overview
The current `uv run pytest` invocation reports 11 failures across serialization utilities, templating/text helpers, signal handler infrastructure, and the extensions task manager. These regressions block CI and must be resolved to restore confidence in the suite before landing further changes.

## Requirements
- Reproduce the failures via `uv run pytest` and capture precise stack traces for each group.
- Restore expected behavior for serialization helpers (UTC normalization, UUID schema integration) without regressing existing consumers.
- Ensure templating/text helpers (async rendering, MDXL grouping, section extension) conform to the latest product requirements.
- Fix signal handler registration so weak references work with the router's internal namespace objects.
- Repair the extensions task manager behavior and validations to satisfy CRUD, completion, and schema expectations.
- Maintain backwards compatibility for public APIs unless explicitly versioned elsewhere.

## Implementation Notes
- Investigate the `ZoneInfo` vs `datetime.timezone.utc` comparison; normalize serializer output to a shared tzinfo object rather than relying on identity equality.
- The UUID serializer likely adopted Pydantic v2 hooks; ensure `__get_pydantic_json_schema__` signature matches expectations and update callers/tests accordingly.
- Confirm the async template renderer awaits coroutine results and renders final strings before assertion.
- Review the MDXL/text formatter cleaners for extra blank lines and bullet markers—apply idempotent whitespace collapsing where necessary.
- Signal handler tests fail because `SimpleNamespace` lacks weakref support; swap in a lightweight weak-ref capable proxy or store plain callables.
- Task manager tests suggest async CRUD helpers return coroutines rather than resolved models; ensure CRUD APIs return dataclasses/records and validate `todo_lists` bookkeeping.

## Todo List
1. Capture fresh pytest output for the 11 failing cases.
2. Patch serialization utilities (datetime, UUID) and extend unit coverage.
3. Fix templating/text helpers (async render, MDXL grouping, section extension tags) with regression tests.
4. Update signal handler registration stack to avoid weakref errors and cover handler restoration.
5. Correct task manager extension CRUD + completion flows, covering validations and schema keys.
6. Re-run full validators: `uv run ruff check`, `uv run mypy`, `uv run pytest`.

## Testing Strategy
- Run targeted unit modules during development for faster iteration (e.g., `uv run pytest tests/unit/core/test_serialization_types.py`).
- Before completion, execute the repository-standard validators: lint via `uv run ruff check`, type checking via `uv run mypy`, and the full `uv run pytest` suite to ensure no regressions remain.
