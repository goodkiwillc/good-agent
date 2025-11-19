## Overview

`CitationIndex` and `CitationManager` must satisfy the generic `Index[KeyT, RefT, ValueT]` protocol. Currently `_resolve_aliases`/`_get_aliases` only accept `URL`, and citation extraction utilities build `list[None]` placeholders, which breaks typing when URLs are inserted. This spec aligns the contract with protocol requirements and enforces consistent container typing for citation lists.

## Requirements

1. Update `CitationIndex` overrides so `_resolve_aliases` and `_get_aliases` accept `URL | str` inputs while still returning canonical `URL` instances.
2. Normalize alias traversal to always return `URL` objects even when canonical strings cannot be re-parsed, falling back gracefully without raising new exceptions.
3. Ensure citation collection helpers in `CitationManager` construct explicitly typed `list[str]` (or `list[URL]`) so assignments no longer violate list item types, preserving ordering semantics.
4. Maintain existing runtime behavior: alias resolution must remain idempotent, and markdown/XML extraction should continue producing sequential citation arrays with gaps removed.
5. Keep future `mypy` runs clean by updating helper annotations and any dependent docstrings/tests as needed.

## Implementation Notes

- Prefer utility helpers (e.g., `_coerce_url(value: URL | str) -> URL`) to centralize conversion logic and avoid repeated try/except blocks.
- When building citation arrays from reference blocks, annotate with `list[str | None]` or build ordered arrays via comprehension, then convert to `list[str]` after filtering `None` values.
- For alias resolution, track visited nodes using canonical strings; attempt `URL(canonical)` and fall back to the original `URL` argument when parsing fails.
- Add targeted unit coverage if practical (e.g., verifying `_resolve_aliases` accepts raw strings) to guard against regressions.

## Todo List

1. Introduce canonical URL coercion helper and use it inside `_resolve_aliases` / `_get_aliases`.
2. Annotate citation extraction lists explicitly and normalize entries to `str` values before returning.
3. Re-run `uv run mypy src` to ensure no remaining errors originate from citation modules.

## Testing Strategy

- `uv run mypy src`
