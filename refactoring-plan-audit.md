# Refactoring Plan Audit

**Date:** 2025-11-15  
**Auditor:** Factory Droid

## Scope & Methodology

- Reviewed `.spec/refactoring-plan.md` items marked as complete (Phase 1 foundation tasks and Phase 2 file splits).
- Inspected the current repository state under `src/good_agent` and `tests/` with `rg`, `glob`, and `wc -l` to confirm the presence/absence of files and to measure module sizes.
- Verified documentation artifacts (`CHANGELOG.md`, `MIGRATION.md`, PHASE summaries) without modifying code.
- No source files were changed during the audit; this report is the only addition.

## Executive Summary

- **Phase 1:** Wrapper removals and basic test additions landed, but template deduplication (Step 6) never occurred and the “verify & document” step skipped updating the requested CLAUDE.md artifact. Net: 5/7 tasks fully satisfied, 2 remain open.
- **Phase 2:** The agent/messages/model packages exist, yet the acceptance criteria in the spec were not met: `agent/core.py` still spans 2,684 lines, `agent/tools.py` is 696 lines, `.bak` copies of the old monoliths (`messages.py.bak`, `model/llm.py.bak`) are still tracked and will be shipped, and test reorganizations promised in the spec never happened. The phase is therefore **not** complete despite the ✅ markers in the plan.
- **Design concerns:** Template logic still lives in both `core/templating/` and `templating/`, the Agent API surface stays enormous, and the new tests exercise private helpers instead of public behaviors. These issues should be addressed before starting Phase 3.

## Phase 1 Findings

### 1. Remove Utilities Wrappers
**Status:** ✅ Complete  
**Evidence:** `glob` finds no `src/good_agent/utilities/{event_router,ulid_monotonic,signal_handler,text}.py` files, and `rg "good_agent\.utilities\.event_router"` only appears in documentation (CHANGELOG/MIGRATION).  
**Notes:** Canonical imports now point at `good_agent.core.*` as intended.

### 2. Remove Duplicate `text.py`
**Status:** ✅ Complete  
**Evidence:** `src/good_agent/utilities/text.py` is absent and all `good_agent.utilities.text` references are confined to docs.  
**Notes:** No duplicate implementation remains.

### 3. Remove Debug / Manual Tests
**Status:** ✅ Complete  
**Evidence:** The files called out in the spec now live under `scripts/debug/` (`debug_minimal_test.py`, `manual_registry_discovery.py`, `test_decorator_debug.py`); they are no longer collected by pytest.  
**Notes:** Test discovery noise eliminated.

### 4. Add Tests for `pool.py`
**Status:** ⚠️ Partial  
**Evidence:** `tests/unit/test_pool.py` exists (~6.9 KB) and covers construction, indexing, slicing, and simple modulo access. The spec called for coverage of “Agent creation and reuse, concurrent operations, pool cleanup, resource limits,” but there are no asynchronous/concurrent tests, no cleanup/resource-limit scenarios, and no coverage data demonstrating the promised “>80%”.  
**Gap:** Expand tests to exercise actual pool workflows (e.g., concurrent `Agent.call` usage, ensuring agents are reused safely) and collect real coverage numbers.

### 5. Add Tests for `utilities/`
**Status:** ⚠️ Partial  
**Evidence:** New files exist at `tests/unit/utilities/test_{printing,lxml,retries,logger}.py` plus `test_tokens.py`. However, most assertions hit private helpers such as `_detect_markdown` instead of the exported functions (e.g., `print_message`), and no coverage report accompanies the change, so the spec’s “>80% coverage per module” claim is unverified.  
**Gap:** Add tests that drive the public APIs (actual logging output, retry loops, XML sanitization) and record coverage to substantiate the requirement.

### 6. Consolidate Template Duplication
**Status:** ❌ Not done  
**Evidence:** `src/good_agent/templating/core.py` (≈981 lines) still defines `TemplateManager`, and `good_agent.agent.core` continues to import `TemplateManager` directly from `..templating`. No `components/template_manager.py` exists, and both `core/templating/` and `templating/` packages ship side-by-side.  
**Gap:** Move the TemplateManager/component logic into the canonical location (as the spec describes) and delete the redundant package to avoid two divergent template stacks.

### 7. Verify & Document Changes
**Status:** ⚠️ Partial  
**Evidence:** `CHANGELOG.md`, `MIGRATION.md`, `PHASE1_SUMMARY.md` were updated, but the spec explicitly called for updating “project CLAUDE.md,” which does not exist in the repo (confirmed via `rg "CLAUDE"`). There is also no recorded evidence of the required `uv run pytest` / `uv run ruff check .` executions beyond an undated `final_test_run.log` in `tests/`.  
**Gap:** Either add the missing CLAUDE.md artifact or update the spec, and capture the validation commands in the repo (e.g., CI logs or a short note in the summary).

## Phase 2 Findings

### 1. Refactor `agent.py`
**Status:** ❌ Acceptance criteria unmet  
**Evidence:**
- `agent/core.py` is still 2,684 lines (`wc -l`), far above the `<600` goal.  
- `agent/tools.py` sits at 696 lines, exceeding the ≤500 target.  
- The spec promised dedicated tests such as `tests/unit/agent/test_message_manager.py`, but no such files exist; `tests/unit/agent/` still contains the original 30+ monolithic tests.  
- Agent still directly exposes dozens of public methods and continues to import TemplateManager from `good_agent.templating`, meaning the API surface was not slimmed down.  
**Gap:** Continue extracting logic (e.g., fork/context/versioning/tool orchestration) and reorganize the tests before claiming this step complete.

### 2. Refactor `messages.py`
**Status:** ⚠️ Partial  
**Evidence:** The new `messages/` package exists with `base.py`, `roles.py`, etc., but the old 1,800-line module lives on as `src/good_agent/messages.py.bak` and is still tracked (`git ls-files src/good_agent/messages.py.bak`). This file will ship in the wheel because nothing in `pyproject.toml` excludes it, undermining the “single canonical location” goal.  
**Gap:** Remove the `.bak` file (or move it out of the package entirely) and ensure only the package is distributed. Consider adding regression tests that import `good_agent.messages` to confirm it resolves to the package.

### 3. Refactor `model/llm.py`
**Status:** ⚠️ Partial  
**Evidence:** Helper modules (`capabilities.py`, `formatting.py`, `structured.py`, `streaming.py`, `protocols.py`) exist, yet `model/llm.py` is still 939 lines and the original 1,889-line implementation persists as `src/good_agent/model/llm.py.bak` (tracked in git). Shipping both versions negates the refactor’s maintainability benefits and risks stale code paths being imported.  
**Gap:** Delete the `.bak` file, continue slimming `model/llm.py`, and add targeted tests for the new helper classes.

### 4. Document Phase 2 Changes
**Status:** ⚠️ Partial  
**Evidence:** `CHANGELOG.md`, `MIGRATION.md`, and `PHASE2_SUMMARY.md` describe Phase 2, yet they assert “No code changes required” and “313/313 tests passing” without evidence, while the tracked `.bak` files prove the clean-up is incomplete. The migration guide still references the old monoliths implicitly by claiming users “don’t need to change anything,” which becomes untrue once the `.bak` files are finally removed.  
**Gap:** Update the docs to reflect the real state (including any required import adjustments) and note the outstanding work.

## Design & Interface Observations

- **Template ownership is unclear:** Both `core/templating/` and `templating/` export overlapping registries, and Agent still depends on the latter. This contradicts the spec’s design decision to make `core/` canonical.
- **`.bak` artifacts pollute the distributable:** Keeping full copies of the old monoliths inside `src/good_agent` means users receive two divergent implementations and might unknowingly import the wrong one. It also bloats the wheel and confuses tooling.
- **Agent API remains unwieldy:** Even after extracting managers, the Agent class still exposes dozens of public methods/properties and spans thousands of lines, so the cognitive-load goal has not been realized.
- **New tests focus on internals:** Utility tests validate private helpers and never assert on the user-facing logging/printing behavior, limiting their usefulness.

## Recommended Next Steps

1. Finish Phase 1 Step 6 by relocating `TemplateManager` (and related injection logic) into the chosen canonical package, then delete the redundant module.
2. Remove `messages.py.bak` and `model/llm.py.bak` from the package, add regression tests that import the public APIs, and update MIGRATION.md to explain any required changes.
3. Continue breaking down `agent/core.py` and `agent/tools.py` until they meet the size targets, and restructure `tests/unit/agent/` to cover the new manager classes explicitly.
4. Expand the new test suites to exercise public behaviors (pool concurrency, logging output, retry backoff) and capture actual coverage metrics to prove the “>80%” claim.
5. Clarify documentation: add the missing CLAUDE.md entry (or update the spec to remove that requirement) and ensure status summaries stop marking incomplete work as ✅.
