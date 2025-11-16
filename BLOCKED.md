# Blockers (2025-11-16)

## 1. mypy
- Command: `uv run mypy src`
- Status: ❌ 165 errors across 39 files (missing stubs such as `types-Markdown`, `types-PyYAML`, `prefect`, unresolved modules like `good_agent.core.migration`, numerous annotation issues in `core/templating`, `tools`, `resources`, etc.).
- Impact: Type checking cannot pass without a repository-wide cleanup and new stub dependencies. This is unrelated to the Phase 3/4 audit doc.
- Next Steps:
  - Decide whether to pin/skip third-party modules lacking type hints (e.g., add `py.typed` shims or `type: ignore` pragmas).
  - Break the work into module-focused stories; the failure list from the command output can seed individual tickets.

## 2. pytest
- Command: `uv run pytest`
- Status: ❌ 10 failures in `tests/unit/test_prompts_cli.py::TestPromptsCLI::*` (value errors thrown while invoking the prompts CLI).
- Impact: Test suite currently red in main; unrelated to the audit doc changes.
- Next Steps:
  - Investigate prompts CLI fixtures (likely need to update template discovery paths or stub data after recent refactors).
  - Re-run `uv run pytest tests/unit/test_prompts_cli.py` after addressing the CLI regressions.

> Note: Both blockers predate this audit and must be resolved separately before the repo can meet the validation policy.
