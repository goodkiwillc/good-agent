# Agent v1 Design Audit — 2025-11-14

## Overview

This audit compares the current `Agent` implementation in `src/good_agent/` and associated tests with the expectations laid out in `.spec/v1/DESIGN.md`. The goal is to surface concrete gaps, define the work required to realign code and spec, and flag areas where documentation is too sparse for contributors to make safe changes.

## Requirements

1. **Implement streaming parity with spec** — `Agent.execute(streaming=True)` should actually drive `LanguageModel.stream(...)` and yield streaming-aware message wrappers exposing `message.stream()`, as promised in the spec example. Today the flag is unused (`src/good_agent/agent/core.py::execute`).
2. **Restore the documented `agent.modes` API** — No `modes` registry exists in the refactored package. Either re-introduce the feature (matching the spec contract) or amend the design spec to drop/replace the section.
3. **Restore the documented `agent.commands` API** — The command registration workflow shown in the spec is completely absent from the runtime. As with modes, decide whether to re-implement or explicitly remove it from the design contract.
4. **Complete configuration surface** — The spec calls out keys such as `telemetry`, `telemetry_options`, and `tool_call_timeout`; none are defined in `AgentConfigManager` (`src/good_agent/config.py`). These need implementation (including pass-through to components) or the spec must be corrected.
5. **Clarify context callable semantics** — The design example shows context entries as callables (`lambda ctx: ...`), but `Context`/`TemplateManager` never execute bare callables. Either add support (most naturally via the context resolver) or document the correct pattern (e.g., providers via `@global_context_provider`).
6. **Document / expose versioning & state APIs** — The refactor introduced `AgentVersioningManager`, `AgentStateMachine`, managed task tracking, and warning-producing indexing semantics that are not covered in `.spec/v1/DESIGN.md`. The spec needs an explicit section so users understand current behavior, especially around warnings when `agent[0]` is accessed without a system message (`tests/unit/agent/test_agent.py`).

## Implementation Notes

### Spec-Inconsistent Behavior

- **Streaming flag is ignored** – `Agent.execute(..., streaming=True)` never calls `LanguageModel.stream`; messages also lack a `.stream()` helper. The design sample cannot work as written.
- **Modes & Commands removed** – Searches across `src/good_agent/agent/` show no `modes` or `commands` attributes despite multi-page coverage in the spec. Tests likewise never exercise these APIs.
- **Configuration drift** – `AgentConfigManager` exposes many new toggles (`extract_mode`, `extract_fallbacks`, etc.) but omits spec-listed items (`telemetry`, `telemetry_options`, `tool_call_timeout`, `template_path`). Callers expecting spec parity cannot configure telemetry or tool timeouts today.
- **Context lambda example misleading** – `Context.as_dict()` simply merges ChainMaps; there is no hook that invokes callables stored in the base dict. The spec’s `lambda ctx` example therefore yields the function object, not a computed value.
- **Tool filters not wired** – `include_tool_filters` / `exclude_tool_filters` are defined in config types but unused elsewhere, so spec references to filter-based loading are currently aspirational.

### Under-Documented Areas

- **Versioning lifecycle** – `AgentVersioningManager` and `MessageList` version snapshots underpin numerous tests (`tests/unit/versioning/*`) but the design doc never mentions version rollback, fork semantics, or `agent.current_version`.
- **State machine & managed tasks** – The new `AgentStateMachine` (READY / PENDING_TOOLS / PROCESSING) and `Agent.create_task` bookkeeping are invisible in the spec, leaving future contributors unaware of required state transitions or cleanup guarantees validated in `tests/unit/agent/test_agent_create_task.py`.
- **Component registry & dependency validation** – Initialization now flows through `ComponentRegistry.install_components()` and dependency checks (`src/good_agent/agent/components.py`), yet the spec still describes the monolithic pre-refactor initialization.
- **Tool execution events & validation** – The design doc stops at high-level tool usage, but the implementation fires rich events (`AgentEvents.TOOL_CALL_AFTER`, sequence validation). Tests under `tests/unit/agent/test_agent_message_store_integration.py` rely on these pathways; documenting them would prevent accidental regressions.

## Todo List

- [ ] Decide whether to reintroduce (vs. descope) the `agent.modes` API and update code/spec accordingly.
- [ ] Decide whether to reintroduce (vs. descope) the `agent.commands` API and update code/spec accordingly.
- [ ] Implement a streaming execution pathway on `Agent.execute` backed by `LanguageModel.stream`, including message wrappers that expose chunk iterators.
- [ ] Extend `AgentConfigManager` and downstream components to honor `telemetry`, `telemetry_options`, and `tool_call_timeout`, or update the spec to reflect the supported configuration surface.
- [ ] Add callable-context support (or revise docs to recommend context providers) so the context example in the design doc becomes accurate.
- [ ] Author a documentation update covering agent state/versioning/task lifecycle so future maintainers understand the expectations encoded in the tests.

## Testing Strategy

- Add integration coverage for the restored streaming path (e.g., extending `tests/unit/agent/test_language_model_streaming.py` to go through `Agent.execute(streaming=True)`).
- Introduce regression tests for the resurrected `modes` / `commands` APIs if they are implemented; otherwise remove or adapt any existing hallucinated tests that still assume their presence.
- Extend configuration tests to assert new telemetry and tool timeout behavior once implemented (`tests/unit/agent/test_agent.py` is a good home).
- Add context-behavior tests illustrating callable support or the documented provider pattern to prevent future drift.
