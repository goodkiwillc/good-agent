# Phase 3 & 4 Audit Plan

## Overview
- Audit the implementation status of Phases 3 and 4 in `.spec/refactoring-plan.md`.
- Compare specification requirements versus the current repository state to identify completed, partial, or missing work.
- Produce an actionable audit document with evidence-backed findings and recommendations.

## Requirements
1. Review every Phase 3 requirement (event router reorg, thread safety, testing, docstring trimming) and Phase 4 requirement (message API, call vs execute docs, API reduction, property/method consistency, documentation tasks).
2. Inspect source code, tests, and documentation artifacts to verify whether each requirement is satisfied.
3. Capture discrepancies with direct references (files, line ranges, commands) proving completion gaps.
4. Summarize recommendations for bringing each outstanding item back on track.
5. Store the final audit in `.spec/phase3-4-audit.md` for future reference.

## Implementation Notes
- Use `rg`, `glob`, and targeted `Read` calls to gather evidence instead of ad-hoc shell commands.
- Treat `.bak` files and missing tests as red flags—call them out explicitly.
- Highlight mismatches between CHANGELOG/summary claims and actual code to prevent status drift.
- Structure the audit similarly to `refactoring-plan-audit.md` (scope, summary, per-task findings, recommendations) for consistency.

## Todo List
- [ ] Extract Phase 3 acceptance criteria from `.spec/refactoring-plan.md`.
- [ ] Compare event router package contents against the spec (locking, SyncBridge usage, tests, docstrings).
- [ ] Evaluate documentation-verbosity tasks (docstring reduction, examples directory).
- [ ] Extract Phase 4 acceptance criteria and validate repository state (API deprecations, public surface, property vs method usage, docs).
- [ ] Draft `.spec/phase3-4-audit.md` with findings & recommendations.
- [ ] Run validators (ruff, mypy, pytest) to ensure repository health after documentation changes.

## Testing Strategy
- No new runtime code, but run the standard validators (`uv run ruff check .`, `uv run mypy`, `uv run pytest`) after writing the audit to comply with repo policy.
