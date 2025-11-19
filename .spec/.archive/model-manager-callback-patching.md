## Overview
Eliminate the remaining `uv run mypy src --check-untyped-defs` failures in `ModelManager` by replacing the ad-hoc monkey patching of LiteLLM callback manager methods with a typed, scoped helper that preserves the runtime isolation guarantees without assigning directly to method attributes.

## Requirements
- Stop assigning directly to `logging_callback_manager.add_*` methods; use a structured helper so mypy no longer reports "Cannot assign to a method" errors at lines 168/172/182/186.
- Preserve the temporary suppression semantics: callbacks must be replaced with a no-op only during `Router.__init__` and restored afterward even if initialization fails.
- Maintain existing behavior for async/sync success and failure callbacks plus any instructor integrations; avoid widening the patching window or leaking references.

## Implementation Notes
- Introduce a small context manager (e.g., `_temporary_callback_patch`) that accepts the callback manager object and a mapping of attribute names to replacements, storing originals and restoring them in `finally`.
- Type the helper with `Callable[..., Any]` or a `Protocol` so mypy understands the stored originals and reinstatement; keep it private to `model.manager`.
- Inside `_ManagedRouter.__init__`, wrap `super().__init__` with the context manager rather than duplicating try/finally blocks; reuse the existing `noop_add` closure.
- Keep logging, `_managed_callbacks`, and instructor behavior untouched; avoid introducing new global state.

## Todo List
1. Add the temporary patch helper in `src/good_agent/model/manager.py` and migrate the current try/finally block to use it.
2. Ensure replacements and restores happen via `setattr` to avoid direct method assignment.
3. Re-run `uv run mypy src --check-untyped-defs` to confirm the method-assign errors are resolved.

## Testing Strategy
- Primary: `uv run mypy src --check-untyped-defs`.
- Regression: rely on existing router tests; no additional runtime behavior should change, but run `uv run pytest` if not already part of validator suite.
