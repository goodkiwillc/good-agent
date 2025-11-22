# Feature Spec: GitHub Pages Documentation Deployment

**Status**: 📝 Draft  
**Created**: 2025-11-21  
**Author**: Droid  
**Related**: `.github/workflows/ci-cd.yml`, `mkdocs.yml`, `docs/`, `site/`

## Overview

Extend the existing CI/CD pipeline so that successful builds on the default branch automatically publish the MkDocs-powered documentation site to GitHub Pages. This keeps the public docs in lockstep with the codebase without requiring manual steps.

## Requirements

- Trigger documentation deployment only after the `test` job passes and only for pushes to `main` (optionally workflow_dispatch releases can reuse it later).
- Use the officially supported GitHub Pages deployment sequence (`actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages`) with the correct permissions (`pages: write`, `id-token: write`).
- Build docs with the repo-standard tooling (`uv` + `mkdocs`) to ensure parity with local builds and avoid duplicating dependency logic.
- Output the built site to the existing `site/` directory (or a temp directory) and upload it as the Pages artifact consumed by the deploy step.
- Expose the resulting deployment URL via the workflow `environment` configuration so GitHub surfaces it on the run summary.
- Keep jobs declarative, reusing shared env vars (e.g., `PYTHON_VERSION`) and caching strategy when possible without interfering with the primary test matrix.

## Implementation Notes

- Add a `deploy_docs` job that `needs: test`, `runs-on: ubuntu-latest`, and gates execution via `if: github.ref == 'refs/heads/main' && github.event_name == 'push'` (adjustable later for other triggers).
- Steps: checkout full history, set up Python via `actions/setup-python`, install `uv`, run `uv sync --group dev` (or `uv sync` if dev deps already included) to ensure MkDocs plugins are available, then invoke `uv run mkdocs build --clean --site-dir site`.
- Use `actions/configure-pages@v5` to set configuration, `actions/upload-pages-artifact@v3` pointing at the built `site/` directory, and `actions/deploy-pages@v4` with `environment: github-pages` capturing the `page_url` output for visibility.
- Ensure job-level `permissions` include `contents: read`, `pages: write`, and `id-token: write`; keep default for others.
- Consider caching the MkDocs build inputs via `actions/cache` on `~/.cache/uv` similar to the test job for faster builds.
- Keep YAML comments minimal per repo guidance; rely on descriptive step names.

## Todo List

- [ ] Define the `deploy_docs` job with correct trigger conditions and dependencies.
- [ ] Install MkDocs dependencies within the job and build the site using `uv run mkdocs build --clean`.
- [ ] Wire in GitHub Pages actions to upload and deploy the built documentation artifact.
- [ ] Verify workflow passes `act`/lint check locally if applicable (sanity check `yamllint` optional).

## Testing Strategy

- Run `uv run mkdocs build --clean` locally to confirm the docs build succeeds before relying on CI (optional but recommended when editing MkDocs config).
- After editing the workflow, use `gh workflow run ci-cd.yml` or rely on the next push to validate the GitHub Pages deployment path, ensuring the job completes and publishes the site.
