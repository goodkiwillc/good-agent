## Overview
- Current coverage is 65.73% with `fail_under = 65`, so any regression will break CI.
- Key drags are templating helpers, runtime utilities, serialization type adapters, and phantom files no longer in the repo but still counted by coverage.
- Strategy: (1) exclude genuinely untestable or non-existent modules from coverage; (2) add targeted, high-ROI unit tests to the remaining low-coverage areas.

## Requirements
1. Update `[tool.coverage.report].omit` to drop phantom files and data-only modules:
   - `src/good_agent/spec.py`
   - `src/good_agent/type_guards.py`
   - `src/good_agent/core/models/reference.py`
   - `src/good_agent/core/models/protocols.py`
   - `src/good_agent/core/templating/type_safety_patterns.py`
2. Add unit tests covering the following modules:
   - Tempting helpers: `core/markdown.py`, `core/templates.py`, `core/templating/_filters.py`, `core/templating/_extensions.py`.
   - Runtime helpers: `core/param_naming.py`, `utilities/integration.py`, `model/__init__.py`, `extensions/task_manager.py`.
   - Serialization/type helpers: `core/models/serializers.py`, `core/types/_dates.py`, `core/types/_uuid.py`.
   - Text/MDXL utilities: `core/text.py`, `core/mdxl.py`.
   - Event + signals: `core/event_router/decorators.py`, `core/signal_handler.py`.
3. Keep tests deterministic (no real signals or network) and fast; reuse pytest markers (`requires_signals`) where appropriate.
4. Ensure coverage climbs comfortably above 70% after changes.

## Implementation Notes
- Reuse existing `tests/unit/...` tree; create new modules only when no obvious home exists.
- Favor dependency injection and monkeypatching for signal handling and lazy-import verification.
- Snapshot small inline templates/HTML rather than large fixtures for templating tests.
- For MDXL tests, target helper behaviors (`_should_convert_legacy`, `_parse` sanitization, `references`, `sort_children`) instead of full integration scenarios.
- Share lightweight Pydantic models/fixtures for serializer and UUID tests to minimize boilerplate.

## Todo List
- [ ] Update coverage omit list in `pyproject.toml`.
- [ ] Add templating helper tests (markdown, templates, filters, extensions).
- [ ] Add runtime helper tests (param naming, patch_method, lazy imports, task manager).
- [ ] Add serialization/type helper tests (serializers, dates, UUID).
- [ ] Add text + MDXL tests.
- [ ] Add event router decorator + signal handler tests.
- [ ] Run `uv run ruff check`.
- [ ] Run `uv run pytest --cov=src/good_agent --cov-report=term-missing` and confirm coverage > 70%.

## Testing Strategy
1. Fast local iteration with targeted pytest nodes (e.g., `uv run pytest tests/unit/templating/test_markdown_extensions.py`).
2. Full validation gate:
   - `uv run ruff check`
   - `uv run pytest --maxfail=1 --cov=src/good_agent --cov-report=term-missing`
3. Re-run coverage after modifying omit list to ensure phantom files disappear from the report.
