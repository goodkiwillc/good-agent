# .spec/.archive Index

This directory contains archived specification documents, work summaries, and technical documentation from the good-agent project development.

## File Organization

Files are organized using the naming convention: `YYYY-MM-DD_type_description.md`

- **spec** - Specification documents with requirements and implementation plans
- **summary** - Completion summaries and retrospective documents  
- **fix** - Bug fixes and issue resolution documents
- **ref** - Reference documents (proposals, guides, etc.)
- **audit** - Code audit and analysis documents

## Documents by Type

### Phase Summaries
- [2025-11-13_summary_phase1summary.md](2025-11-13_summary_phase1summary.md) - Phase 1 of the good-agent library refactoring focused on eliminating code duplication and establi...
- [2025-11-13_summary_phase2summary.md](2025-11-13_summary_phase2summary.md) - Phase 2 focused on extracting manager classes from the monolithic Agent class and creating a clea...
- [2025-11-16_summary_phase3-4-audit.md](2025-11-16_summary_phase3-4-audit.md) - - Audit the implementation status of Phases 3 and 4 in `.spec/refactoring-plan.md`.
- [2025-11-16_summary_phase3-4-audit.md](2025-11-16_summary_phase3-4-audit.md) - **Date:** 2025-11-16
- [2025-11-16_summary_phase4sessionsummary.md](2025-11-16_summary_phase4sessionsummary.md) - Successfully completed verification of Phase 3, merged to main, created Phase 4 branch, and compl...

### Specifications
- [2025-11-13_spec_missing-goodintel-core-import.md](2025-11-13_spec_missing-goodintel-core-import.md) - Historical citation tests located in `tests/unit/citations/.archive` still depend on the legacy `...
- [2025-11-16_spec_prompts-cli-path-normalization.md](2025-11-16_spec_prompts-cli-path-normalization.md) - Cross-platform users reported failures in the prompts CLI tests where template
- [2025-11-17_spec_citation-typing-cleanup.md](2025-11-17_spec_citation-typing-cleanup.md) - `CitationIndex` and `CitationManager` must satisfy the generic `Index[KeyT, RefT, ValueT]` protoc...
- [2025-11-17_spec_coverage-hardening.md](2025-11-17_spec_coverage-hardening.md) - - Current coverage is 65.73% with `fail_under = 65`, so any regression will break CI.
- [2025-11-17_spec_event-context-mypy-fix.md](2025-11-17_spec_event-context-mypy-fix.md) - EventRouter contexts currently annotate `output` as `T_Return | None` while legacy behavior store...
- [2025-11-17_spec_event-router-pytest-compat.md](2025-11-17_spec_event-router-pytest-compat.md) - Event router regression tests in `tests/unit/event_router` now fail after recent refactors and th...
- [2025-11-17_spec_markdown-extensions-hang.md](2025-11-17_spec_markdown-extensions-hang.md) - - Diagnose why `uv run pytest tests/unit/core/test_markdown_extensions.py` hangs instead of compl...
- [2025-11-17_spec_message-store-async-exists-fix.md](2025-11-17_spec_message-store-async-exists-fix.md) - `tests/unit/messages/test_message_store.py::TestInMemoryMessageStore::test_async_operations_memor...
- [2025-11-17_spec_message-store-redis-fallback-compat.md](2025-11-17_spec_message-store-redis-fallback-compat.md) - Two regressions surfaced in the message subsystem test suite:
- [2025-11-17_spec_model-manager-callback-patching.md](2025-11-17_spec_model-manager-callback-patching.md) - Eliminate the remaining `uv run mypy src --check-untyped-defs` failures in `ModelManager` by repl...
- [2025-11-17_spec_mypy-cleanup.md](2025-11-17_spec_mypy-cleanup.md) - Resolve the current `uv run mypy src --check-untyped-defs` failures blocking CI. Focus on alignin...
- [2025-11-17_spec_mypy-tests-cleanup.md](2025-11-17_spec_mypy-tests-cleanup.md) - `uv run mypy tests --check-untyped-defs` currently surfaces ~500 errors across 75 test modules. T...
- [2025-11-17_spec_pytest-failures.md](2025-11-17_spec_pytest-failures.md) - The current `uv run pytest` invocation reports 11 failures across serialization utilities, templa...
- [2025-11-17_spec_remove-compat-shims.md](2025-11-17_spec_remove-compat-shims.md) - We previously introduced backwards-compatibility shim modules (for `good_agent.config`, `good_age...
- [2025-11-17_spec_sync-bridge-stress-hang.md](2025-11-17_spec_sync-bridge-stress-hang.md) - The `tests/unit/event_router/test_sync_bridge_stress.py` suite intermittently hangs (typically ar...
- [2025-11-18_spec_search-dedup-performance-benchmark.md](2025-11-18_spec_search-dedup-performance-benchmark.md) - `tests/integration/search/test_search_performance.py::TestPerformance::test_deduplication_perform...

### Bug Fixes
- [2025-11-17_fix_streaming-reference.md](2025-11-17_fix_streaming-reference.md) - No, the LLMCoordinator does not actually support streaming responses, despite what the

### Reference Documents
- [2025-11-16_ref_phase4messageapiproposal.md](2025-11-16_ref_phase4messageapiproposal.md) - 

### Audits

## Chronological Index

Files are listed in chronological order (newest first):
- **2025-11-18** [SUMMARY] [2025-11-18_summary_refactoring-plan.md](2025-11-18_summary_refactoring-plan.md)
- **2025-11-18** [SPEC] [2025-11-18_spec_search-dedup-performance-benchmark.md](2025-11-18_spec_search-dedup-performance-benchmark.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_sync-bridge-stress-hang.md](2025-11-17_spec_sync-bridge-stress-hang.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_remove-compat-shims.md](2025-11-17_spec_remove-compat-shims.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_pytest-failures.md](2025-11-17_spec_pytest-failures.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_mypy-tests-cleanup.md](2025-11-17_spec_mypy-tests-cleanup.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_mypy-cleanup.md](2025-11-17_spec_mypy-cleanup.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_model-manager-callback-patching.md](2025-11-17_spec_model-manager-callback-patching.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_message-store-redis-fallback-compat.md](2025-11-17_spec_message-store-redis-fallback-compat.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_message-store-async-exists-fix.md](2025-11-17_spec_message-store-async-exists-fix.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_markdown-extensions-hang.md](2025-11-17_spec_markdown-extensions-hang.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_event-router-pytest-compat.md](2025-11-17_spec_event-router-pytest-compat.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_event-context-mypy-fix.md](2025-11-17_spec_event-context-mypy-fix.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_coverage-hardening.md](2025-11-17_spec_coverage-hardening.md)
- **2025-11-17** [SPEC] [2025-11-17_spec_citation-typing-cleanup.md](2025-11-17_spec_citation-typing-cleanup.md)
- **2025-11-17** [FIX] [2025-11-17_fix_streaming-reference.md](2025-11-17_fix_streaming-reference.md)
- **2025-11-16** [SUMMARY] [2025-11-16_summary_phase4sessionsummary.md](2025-11-16_summary_phase4sessionsummary.md)
- **2025-11-16** [SUMMARY] [2025-11-16_summary_phase3-4-audit.md](2025-11-16_summary_phase3-4-audit.md)
- **2025-11-16** [SUMMARY] [2025-11-16_summary_phase3-4-audit.md](2025-11-16_summary_phase3-4-audit.md)
- **2025-11-16** [SUMMARY] [2025-11-16_summary_migration-guide.md](2025-11-16_summary_migration-guide.md)
- **2025-11-16** [SPEC] [2025-11-16_spec_prompts-cli-path-normalization.md](2025-11-16_spec_prompts-cli-path-normalization.md)
- **2025-11-16** [REF] [2025-11-16_ref_phase4messageapiproposal.md](2025-11-16_ref_phase4messageapiproposal.md)
- **2025-11-13** [SUMMARY] [2025-11-13_summary_readme.md](2025-11-13_summary_readme.md)
- **2025-11-13** [SUMMARY] [2025-11-13_summary_phase2summary.md](2025-11-13_summary_phase2summary.md)
- **2025-11-13** [SUMMARY] [2025-11-13_summary_phase1summary.md](2025-11-13_summary_phase1summary.md)
- **2025-11-13** [SPEC] [2025-11-13_spec_missing-goodintel-core-import.md](2025-11-13_spec_missing-goodintel-core-import.md)

---

*Generated on 2025-11-19 07:42:23. Total documents: 26.*
