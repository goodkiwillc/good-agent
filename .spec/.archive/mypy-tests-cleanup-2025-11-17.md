## Overview
`uv run mypy tests --check-untyped-defs` currently surfaces ~500 errors across 75 test modules. The failures are concentrated in outdated message API tests, retry utilities lacking type annotations, pytest plugins referencing non-existent helpers, and integration scenarios passing `str` values where strongly typed aliases (e.g., `URL`, `SearchProvider`) are required. This spec scopes the typing repairs needed to make the tests tree mypy-clean without masking issues via ignores.

## Requirements
- Replace bad imports in pytest plugins (e.g., load `current_test_nodeid` from `good_agent.core.event_router`) and avoid monkeypatch patterns that break typing (`asyncio.Task.__del__`).
- Expose missing runtime attributes that tests rely on (e.g., `_token_count_cache` on `Message`) via `PrivateAttr` so mypy knows they exist.
- Update tests to align with the new message/content API by constructing proper `ContentPart` objects, widening literal assignments (role values), and avoiding private attribute peeks that no longer exist.
- Add precise local/type annotations for helper state in retry/token/message tests to satisfy `--check-untyped-defs`.
- Use helper Protocols / casts in tests where third-party stubs (markdown, vcr) are incomplete instead of sprinkling `Any`.
- Reconcile integration tests with stricter signatures (`Agent.append`, `AgentSearch`, `SearchResult`), preferring `Sequence` or annotated `list[URL | str]` arguments to avoid list invariance issues.

## Implementation Notes
- **Pytest plugins**: import `current_test_nodeid` from `good_agent.core.event_router`, gate the asyncio patch behind `typing.TYPE_CHECKING` checks, and use `setattr(asyncio.Task, "__del__", ...)` plus `typing.cast(Any, asyncio.Task.__del__)._patched = True` to appease mypy.
- **Message cache attribute**: declare `Message._token_count_cache: dict[str, int] = PrivateAttr(default_factory=dict)` and update `good_agent.utilities.tokens` to stop using `hasattr` checks.
- **Markdown references**: inside `tests/unit/core/test_markdown_extensions.py` introduce a `Protocol` with a `.references` dict so `typing.cast` makes `md.references` known.
- **Retry/token/message tests**: annotate state/message variables explicitly, e.g. `state: RetryState[Any] = RetryState(...)` and `msg: UserMessage = UserMessage("Test")`; prefer helper factories to avoid repetition.
- **VCR stubs**: guard imports via `if TYPE_CHECKING: import vcr` and provide lightweight stub classes (`class VCRStub(Protocol): ...`) so runtime import still happens but mypy treats it as typed.
- **Integration search tests**: wrap provider lists in helper `Sequence` tuple or declare `providers: list[SearchProvider] = [...]` with casts; convert literal URLs via the `URL` type constructor upfront so subsequent API calls see correct types.

## Todo List
1. Fix pytest plugin typing: correct imports, safe monkeypatching, and annotate helper callables.
2. Add missing message/token infrastructure typing (PrivateAttrs, helper utilities) consumed by tests.
3. Update unit and integration tests with explicit typing, helper Protocols, and content/message construction aligned with the current API.
4. Rerun `uv run mypy tests --check-untyped-defs` and iterate until the suite is clean.

## Testing Strategy
- `uv run ruff check tests` – quick lint sanity for edited tests.
- `uv run mypy tests --check-untyped-defs` – primary gate for this effort.
- `uv run pytest` – regression check to ensure behavior unchanged after typing adjustments.
