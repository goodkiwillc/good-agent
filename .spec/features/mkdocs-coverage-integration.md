# Feature Spec: MkDocs Coverage Integration

**Status**: 📝 Draft  
**Created**: 2025-11-20  
**Author**: Droid  
**Related**: `mkdocs.yml`, `pyproject.toml`, `docs/`, `coverage/`, `htmlcov/`

## Overview

Expose test coverage metrics directly in the Good Agent documentation site by wiring the [`mkdocs-coverage`](https://github.com/pawamoy/mkdocs-coverage) plugin into the MkDocs build. Readers should be able to browse the existing HTML coverage report without leaving the docs.

## Requirements

- Add `mkdocs-coverage` as a development dependency managed through `uv` so that doc builds remain reproducible.
- Enable the plugin in `mkdocs.yml` with settings pointing at our generated HTML coverage directory (`htmlcov`) and choose an intuitive page name.
- Ensure MkDocs navigation exposes the coverage report (either via the automatic page created by the plugin or an explicit nav entry) without breaking existing sections.
- Document/build workflow must produce the HTML coverage data (`coverage html` or `pytest --cov-report=html`) before invoking `mkdocs build`, and failures should surface clearly if the report directory is missing.
- Keep the integration optional for local builds by providing sane defaults and brief inline comments only where necessary.

## Implementation Notes

- Add `mkdocs-coverage` to the `[tool.uv]` dependency set in `pyproject.toml` (mirroring how other MkDocs plugins are declared) and regenerate `uv.lock` via `uv lock` or equivalent.
- Update `mkdocs.yml` to append the `coverage` plugin configuration after existing entries, setting `html_report_dir: htmlcov` if deviating from default and customizing `page_name` (e.g., "Test Coverage").
- Add a navigation entry referencing the generated page (`coverage.md` by default) under the "Project Info" group so users can easily find the report.
- Consider adding a lightweight `docs/coverage.md` stub only if required by navigation; prefer relying on plugin-generated content to avoid duplication.
- Verify the docs build succeeds both with existing `htmlcov/` output and in a clean environment by scripting coverage generation before MkDocs runs (e.g., run `uv run pytest --cov=src --cov-report=html` in CI/docs workflows).

## Todo List

- [ ] Add `mkdocs-coverage` to project dependencies and lock file.
- [ ] Update `mkdocs.yml` to configure the coverage plugin and navigation entry.
- [ ] Validate MkDocs build renders the coverage page when coverage assets exist.
- [ ] Capture any workflow adjustments needed to ensure coverage HTML is generated pre-build.

## Testing Strategy

- Run `uv run pytest --cov=src --cov-report=html` (or the existing coverage command) to refresh `htmlcov/` before testing the docs build.
- Execute `uv run mkdocs build` to confirm the coverage plugin renders without errors and that the navigation includes the new entry.
