# Feature Spec: Tighten typing for `good_agent.mock`

**Status**: Draft  
**Created**: 2025-11-19  
**Owner**: Droid  
**Related**: `.spec/features/handler-based-mocking.md`

## Overview

`src/good_agent/mock.py` was expanded substantially for handler-based mocking but currently fails `mypy --strict` due to loose imports, missing annotations, and unnecessary `type: ignore` usage. This spec documents the plan to restore type safety without reducing mocking flexibility.

## Requirements

1. Eliminate all mypy errors in `src/good_agent/mock.py` under the project’s strict settings (including `--strict` behaviour and `--warn-unused-ignores`).
2. Maintain backwards compatibility for the mocking API and existing tests.
3. Remove redundant `type: ignore` comments by aligning types instead of suppressing diagnostics.
4. Ensure all public helpers expose precise type signatures for user discoverability.

## Implementation Notes

- Import LiteLLM stubs from the `litellm.types.*` namespaces instead of `litellm.utils` to satisfy stub exports.
- Re-export protocol-level primitives (e.g., `StreamChunk`) from their defining modules or adjust imports to reference canonical locations.
- Introduce typed aliases for handler callables (sync and async) and ensure `MockHandler` implements `Protocol` with explicit coroutine return types.
- Parameterise previously raw generics (`list`, `tuple`, `Callable`, `AsyncIterator`) and add return annotations for helper methods/properties.
- Replace MagicMock-heavy conversions with typed helper functions that construct concrete dataclasses or `ToolCall` objects, avoiding `Any` leaks.
- Ensure context manager methods return `MockAgent`/`bool` appropriately and surface deterministic `list[dict[str, Any]]` results for API tracking helpers.

## Todo List

1. Update imports to pull LiteLLM types from `litellm.types.utils` and `litellm.types.completion`.
2. Define reusable type aliases (`HandlerCallable`, `SyncHandlerCallable`, etc.) and annotate handler/LLM classes accordingly.
3. Parameterise generics and add missing argument/return annotations across handler classes, `MockAgent`, and helpers.
4. Replace/remove `type: ignore` by aligning attribute assignments with their declared types.
5. Verify helper factories (`create_usage`, `create_mock_language_model`, etc.) return precise types without `Any` leakage.
6. Run `uv run mypy src/good_agent/mock.py`, `uv run ruff check src/good_agent/mock.py`, and `uv run pytest` to confirm regression-free changes.

## Testing Strategy

- `uv run mypy src/good_agent/mock.py`
- `uv run ruff check src/good_agent/mock.py`
- `uv run pytest`
