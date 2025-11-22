# Feature Spec: Release Automation Parity

**Status**: 📝 Draft  
**Created**: 2025-11-21  
**Author**: Droid  
**Related**: `.github/workflows/ci-cd.yml`, `scripts/release.py`, `CHANGELOG.md`, `pyproject.toml`

## Overview

Bring `good-agent`'s release automation in line with `good-common` by introducing a first-class release script plus any missing workflow wiring. The goal is to have a deterministic, one-command release flow that tags versions, runs tests, and lets GitHub Actions build/publish artifacts automatically once tags land on `main`.

## Requirements

- Provide a Python-based `scripts/release.py` mirroring `good-common`'s ergonomics (bump type arg, dry-run/skip-tests flags, safety checks, git tagging/pushing) but tailored to `good-agent`'s pure-Python stack.
- Ensure the script enforces a clean working tree, runs the repo-standard validators (uv sync, ruff, mypy?, pytest) unless explicitly skipped, and writes version metadata if needed.
- Align the CI/CD workflow so tagged releases follow the same expectations as `good-common`: release job triggered via `workflow_dispatch` or annotated tags, publishes to PyPI/Test PyPI, and surfaces artifacts consistently.
- Documented process (script help text + spec) should mention how to create changelog entries and the expectation that `uv lock` is current.
- Keep tooling consistent with the project (uv, pytest, mkdocs, etc.) and avoid introducing new dependencies unless already present in `pyproject.toml`.

## Implementation Notes

- Base the new script structure off `good-common/scripts/release.py`, removing Cython-specific steps and adjusting validator commands (e.g., `uv run ruff check`, `uv run pytest`, `uv run mkdocs build --strict` optional).
- Provide `--dry-run`, `--skip-tests`, and `--yes` flags so automation can call it non-interactively; default to prompting before tagging/pushing.
- When computing next version, reuse the git tag parsing logic from good-common but optionally read from `pyproject.toml` to ensure consistency.
- Update `.github/workflows/ci-cd.yml` only where needed (e.g., ensure release job expects tags `v*`, confirm artifacts align with script expectations, maybe add environment metadata similar to `good-common`).
- Future-friendly: leave hooks/placeholders for changelog updates or version file writes but avoid over-automating (no heavy templating yet).

## Todo List

- [ ] Create `scripts/release.py` patterned after `good-common` with repo-specific commands and options.
- [ ] Wire script into developer workflow docs (commit message, usage) only if necessary elsewhere (avoid README churn unless requested).
- [ ] Review CI/CD workflow for parity gaps (artifact naming, release triggers, trusted publishing) and update accordingly.
- [ ] Validate release dry run locally to ensure commands succeed and tagging pushes the right refs.

## Testing Strategy

- Execute `uv run python scripts/release.py patch --dry-run` to confirm argument parsing and safety checks.
- Run `uv run python scripts/release.py patch --skip-tests --dry-run` post-implementation to ensure test gating toggles function.
- After tagging a test release (locally or via temporary branch), verify GitHub Actions picks up the workflow and artifacts publish to the correct registries.
