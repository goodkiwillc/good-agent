## Overview
The CI workflow currently fails on `macos-latest` because the cache key expression `hashFiles('pyproject.toml, uv.lock')` is treated as a single path string, causing `hashFiles` to error when attempting to hash a non-existent file name containing a comma. This blocks GitHub Actions from starting before tests even run.

## Requirements
- Update every cache step in `.github/workflows/ci-cd.yml` to compute deterministic keys without causing `hashFiles` failures on macOS runners.
- Ensure both `pyproject.toml` and `uv.lock` changes invalidate the cache.
- Keep the workflow compatible with Linux runners and the existing cache restore key structure.
- Avoid introducing new actions or secrets.

## Implementation Notes
- Replace the multi-argument `hashFiles` invocation with two independent `hashFiles` calls concatenated into the key (e.g. `${{ hashFiles('pyproject.toml') }}` and `${{ hashFiles('uv.lock') }}`) to avoid the comma parsing issue observed on macOS.
- Apply the same key format to both the `test` and `deploy_docs` jobs to keep cache hits consistent across jobs.
- Leave the `restore-keys` untouched so existing partial matches still work.

## Todo List
1. Edit `.github/workflows/ci-cd.yml` cache steps to build the key using separate `hashFiles` calls per file.
2. Verify YAML formatting and indentation remain unchanged to avoid workflow validation errors.
3. Run lint (`uv run ruff check .`), type checking (`uv run mypy`), and tests (`uv run pytest`) locally before finalizing.

## Testing Strategy
- Execute `uv run ruff check .` to ensure style and workflow file formatting expectations hold.
- Execute `uv run mypy` for static type validation (guards against unrelated regressions).
- Execute `uv run pytest` to confirm the application test suite remains healthy despite workflow edits.
