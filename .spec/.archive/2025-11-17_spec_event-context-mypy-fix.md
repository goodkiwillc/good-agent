## Overview

EventRouter contexts currently annotate `output` as `T_Return | None` while legacy behavior stores `BaseException` instances when handlers call `stop_with_exception()`. This causes mypy to reject assignments inside `EventContext.stop_with_exception` and fails downstream typing guarantees. We need to formalize the mixed payload while keeping API ergonomics for handlers and router helpers.

## Requirements

1. Define a reusable type alias (e.g., `EventResult[T_Return] = T_Return | BaseException`) to describe possible payloads stored on the context.
2. Update `EventContext` so `output` consistently uses the alias; ensure helper methods (`stop_with_output`, `stop_with_exception`, `stop`) and docstrings reflect the broadened type.
3. Provide a typed convenience accessor (e.g., `def result(self) -> T_Return | None`) or casts at call sites so existing code that expects `T_Return` can continue to type-check without forcing consumers to handle exceptions unless they explicitly need to.
4. Adjust any call sites with explicit annotations (e.g., examples/tests) so their expectations align with the new alias while preserving runtime behavior.
5. Keep backwards compatibility: `ctx.output` must still carry the exception object for legacy integrations, and `ctx.exception` semantics remain unchanged.

## Implementation Notes

- Introduce the alias near other type definitions inside `context.py` to avoid circular imports; prefer `TypeAlias` for clarity.
- Consider adding a small helper method/property (like `def output_result(self) -> T_Return | None`) that returns `None` when the payload is an exception, minimizing downstream changes. Alternatively, apply localized `typing.cast` for annotated sites (tests/examples) to acknowledge the union explicitly.
- Ensure `stop_with_exception` sets `_should_stop`/`_stopped_with_exception` before returning and continues to raise `ApplyInterrupt` only for the output variant.
- Update docstrings and inline comments to describe the new typing expectations to other contributors.

## Todo List

1. Add the `EventResult` type alias and update `EventContext.output` plus helper methods to use it.
2. Provide `output_result` helper (or equivalent) for consumers wanting just `T_Return | None`.
3. Update affected call sites/examples/tests with explicit casts or helper usage so mypy stays clean.
4. Rerun `uv run mypy src` to verify the error is resolved.

## Testing Strategy

- `uv run mypy src`
