## Overview

Historical citation tests located in `tests/unit/citations/.archive` still depend on the legacy `goodintel_core.types` module. The main codebase completed a refactor to `good_agent.core.types`, and the legacy package is no longer vendored. Pytest now aborts during collection because those archived test modules import a path that no longer exists, preventing the skip markers in `conftest_citation_skip.py` from being applied.

## Requirements

- Identify every archived citation test module that imports `goodintel_core.types.URL`.
- Replace the legacy import with the current canonical path (`good_agent.core.types.URL`) to match the refactored package layout.
- Preserve all other test behaviour; avoid modifying assertions or test logic since these files remain archived and are skipped intentionally.
- Ensure pytest can collect these files successfully so that the skip markers may run, eliminating the collection errors.

## Implementation Notes

- Use a targeted edit that only adjusts the module import statement at the top of each affected test file.
- Confirm there is no remaining dependency on `goodintel_core.*` after the edits by searching the repository.
- No functional code changes in `src/` are required; maintaining compatibility inside tests is sufficient for resolving the collection failure.

## Todo List

1. Enumerate archived test files containing `goodintel_core.types` imports.
2. Update each file to import `URL` from `good_agent.core.types`.
3. Re-run `uv run pytest` (or the archived subset) to verify collection succeeds and tests are skipped as expected.
4. Execute linting/formatting (`uv run ruff format .` and `uv run ruff check --fix .`) to ensure style compliance if any Python files were touched.

## Testing Strategy

- Run `uv run pytest tests/unit/citations/.archive/test_citation_formats.py` (and other edited modules if necessary) to confirm import resolution.
- Finish with `uv run pytest` to ensure no collection errors remain across the full suite.
