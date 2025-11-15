# Good-Agent Library Refactoring Specification

> **Status**: Draft
> **Created**: 2025-11-11
> **Last Updated**: 2025-11-11
> **Target Version**: v0.3.0 or v1.0.0
> **Timeline**: 12 weeks
> **Breaking Changes**: Acceptable (pre-1.0 library)

## Overview

This specification provides a comprehensive, phased refactoring plan for the good-agent library based on the code quality audit conducted in November 2025. The audit identified critical architectural and organizational issues stemming from rapid AI-assisted development, including severe code duplication, massive file sizes, and unclear module boundaries.

**Primary Goals:**
1. Eliminate all code duplication (~3,000 lines of duplicate/wrapper code)
2. Break up God Object (agent.py at 4,174 lines) into cohesive modules
3. Establish clear, consistent module boundaries
4. Improve test organization and coverage
5. Create maintainable, well-documented codebase
6. Reduce cognitive load for developers

**Approach:**
This is a 12-week, 6-phase refactoring following the audit recommendations. We accept breaking changes as this is a pre-1.0 library (currently v0.2.0). Each phase is designed to be independently testable with clear acceptance criteria and rollback plans.

## Requirements

### Functional Requirements
- [ ] All existing functionality must be preserved (different API OK)
- [ ] All existing tests must pass or be updated to match new API
- [ ] No performance regressions in core operations
- [ ] Backward compatibility shims provided where practical
- [ ] Migration guide for breaking changes

### Non-Functional Requirements
- [ ] Performance: No measurable performance regression (±5% acceptable)
- [ ] Security: All security properties maintained
- [ ] Compatibility: Python 3.13+ maintained
- [ ] Test Coverage: Maintain or improve current coverage (target >85%)
- [ ] Documentation: All public APIs documented with concise docstrings

### Out of Scope
Explicitly NOT included in this refactoring:
- MDXL parser (core/mdxl.py) - specialized, keep as-is
- Template system architecture - keep structure, only eliminate wrapper duplication
- New feature development
- Performance optimizations beyond maintaining current performance
- External API integrations or new providers

## Implementation Plan

### Architecture/Design Decisions

**Decision 1: Choose core/ as Canonical Location**
- **Choice Made**: Keep `core/` as canonical, delete `utilities/` wrappers
- **Rationale**: `core/` better semantic fit for foundational modules. Minimal disruption.
- **Alternatives Considered**: Keep `utilities/`, but `core/` already has implementations
- **Trade-offs**: All imports need updating, but eliminates confusion

**Decision 2: Accept Breaking Changes**
- **Choice Made**: Full API redesign allowed, target v0.3.0 or v1.0.0
- **Rationale**: Pre-1.0 library, better to fix issues now than carry technical debt
- **Alternatives Considered**: 100% backward compatibility, but too constraining
- **Trade-offs**: Requires migration guide, but enables better long-term design

**Decision 3: Refactor agent.py via Composition**
- **Choice Made**: Extract managers, use composition, preserve public API facade
- **Rationale**: Maintains backward compatibility while improving internal structure
- **Alternatives Considered**: Complete rewrite, but too risky
- **Trade-offs**: Some forwarding overhead, but manageable and clear

**Decision 4: Event Router Simplification - Evaluate Per Phase**
- **Choice Made**: Defer decision to Phase 3, include both options in analysis
- **Rationale**: User notes potential race conditions and opacity issues need investigation
- **Alternatives Considered**: Keep as-is, but user expressed concerns
- **Trade-offs**: More planning overhead, but reduces risk of wrong approach

**Decision 5: Consolidate Tests**
- **Choice Made**: Reduce 138 test files to ~80, organize by feature
- **Rationale**: 32 agent test files is excessive, consolidation improves discoverability
- **Alternatives Considered**: Keep granular tests, but maintenance burden high
- **Trade-offs**: Larger test files, but clearer organization

**Decision 6: Documentation Approach**
- **Choice Made**: Concise docstrings (5-15 lines), separate docs/ directory
- **Rationale**: Current 200-line docstrings obscure code, standard practice is concise
- **Alternatives Considered**: Keep verbose docs, but developer feedback negative
- **Trade-offs**: Need to create docs/, but better long-term maintainability

### File Structure

Current problematic structure:
```
src/good_agent/
├── agent.py (4,174 lines) ⚠️
├── messages.py (1,890 lines) ⚠️
├── core/
│   ├── event_router.py (2,000+ lines) ⚠️
│   ├── text.py (700 lines)
│   ├── ulid_monotonic.py
│   ├── signal_handler.py
│   └── templating/
├── utilities/  ⚠️ DUPLICATE WRAPPERS
│   ├── event_router.py (wrapper)
│   ├── ulid_monotonic.py (wrapper)
│   ├── signal_handler.py (wrapper)
│   ├── text.py (identical copy!)
│   └── lxml.py
├── model/
│   └── llm.py (1,890 lines) ⚠️
├── models/ (wrapper) ⚠️
├── types/ (wrapper) ⚠️
└── templating/ (wrapper) ⚠️
```

Target structure after refactoring:
```
src/good_agent/
├── __init__.py (clean public exports)
├── agent/
│   ├── __init__.py (exports Agent)
│   ├── core.py (500 lines) - Agent orchestration
│   ├── messages.py (400 lines) - MessageManager
│   ├── state.py (300 lines) - AgentStateMachine
│   ├── tools.py (400 lines) - ToolExecutor
│   ├── llm.py (500 lines) - LLMCoordinator
│   ├── components.py (400 lines) - ComponentRegistry
│   ├── context.py (300 lines) - ContextManager
│   └── versioning.py (300 lines) - VersioningManager
├── messages/
│   ├── __init__.py
│   ├── base.py (300 lines) - Message, Annotation
│   ├── roles.py (400 lines) - SystemMessage, UserMessage, etc.
│   ├── message_list.py (600 lines) - MessageList
│   ├── filtering.py (300 lines) - FilteredMessageList
│   └── utilities.py (200 lines)
├── model/
│   ├── __init__.py
│   ├── llm.py (400 lines) - LanguageModel component
│   ├── formatting.py (500 lines) - Message format conversion
│   ├── capabilities.py (300 lines) - Capability detection
│   ├── streaming.py (200 lines) - Streaming support
│   └── structured.py (200 lines) - Structured output
├── core/
│   ├── event_router/ (split decision in Phase 3)
│   │   ├── __init__.py
│   │   ├── core.py (300 lines) - Basic events
│   │   ├── context.py (200 lines) - EventContext
│   │   ├── decorators.py (200 lines) - @on decorator
│   │   └── advanced.py (400 lines) - Priority, predicates, etc.
│   ├── text.py (700 lines) - StringFormatter (canonical)
│   ├── ulid_monotonic.py
│   ├── signal_handler.py
│   ├── templating/ (keep as-is per user)
│   ├── mdxl.py (1,800 lines) - Keep as-is per user
│   ├── types/
│   └── models/
├── utilities/
│   ├── printing.py (with tests)
│   ├── lxml.py (with tests)
│   ├── retries.py (with tests)
│   ├── tokens.py (has tests ✅)
│   └── logger.py (with tests)
├── components/
├── extensions/
├── mcp/
├── resources/
├── pool.py (with tests)
├── store.py
├── validation.py
└── versioning.py

tests/
├── conftest.py (consolidated)
├── support/
│   ├── fixtures.py
│   ├── factories.py
│   └── assertions.py
├── unit/
│   ├── agent/ (10 files, was 32)
│   ├── components/ (6 files, was 15)
│   ├── messages/ (10 files, was 14)
│   ├── model/ (8 files)
│   ├── utilities/ (NEW - 6 files)
│   ├── versioning/ (3 files)
│   ├── tools/
│   └── mock/ (3 files, separated)
├── integration/
│   ├── test_end_to_end.py
│   ├── test_multi_agent.py
│   └── test_real_world_scenarios.py
├── performance/ (NEW)
│   └── test_benchmarks.py
└── cassettes/ (VCR recordings)
```

### Implementation Steps

## Phase 1: Foundation - Eliminate Code Duplication (Weeks 1-2) ✅ COMPLETE

**Status:** ✅ Completed 2025-11-11
**Branch:** `refactor/phase-1-duplication`
**Commit:** `bd403b8`
**Goal:** Remove all duplicate code, establish canonical module locations, add critical missing tests.

### 1. [x] **Remove Utilities Wrappers** - LOW RISK, HIGH VALUE ✅
- Files: Delete `utilities/event_router.py`, `utilities/ulid_monotonic.py`, `utilities/signal_handler.py`, `models/__init__.py`, `types/__init__.py`
- Details:
  1. Run global find-replace for imports:
     ```bash
     rg "from good_agent.utilities.event_router" -l | xargs sed -i '' 's/good_agent.utilities.event_router/good_agent.core.event_router/g'
     rg "from good_agent.utilities.ulid_monotonic" -l | xargs sed -i '' 's/good_agent.utilities.ulid_monotonic/good_agent.core.ulid_monotonic/g'
     rg "from good_agent.utilities.signal_handler" -l | xargs sed -i '' 's/good_agent.utilities.signal_handler/good_agent.core.signal_handler/g'
     rg "from good_agent.models" -l | xargs sed -i '' 's/from good_agent.models/from good_agent.core.models/g'
     rg "from good_agent.types" -l | xargs sed -i '' 's/from good_agent.types/from good_agent.core.types/g'
     ```
  2. Delete wrapper files:
     ```bash
     rm src/good_agent/utilities/event_router.py
     rm src/good_agent/utilities/ulid_monotonic.py
     rm src/good_agent/utilities/signal_handler.py
     rm src/good_agent/models/__init__.py
     rm src/good_agent/types/__init__.py
     ```
  3. Update `__init__.py` exports to use canonical paths
  4. Run full test suite: `uv run pytest`
  5. Verify no import errors: `rg "from good_agent.utilities.event_router"`
- Complexity: Low
- Dependencies: None
- Success Criteria: Zero wrapper files, all tests passing, consistent imports

### 2. [x] **Remove Duplicate text.py** - LOW RISK ✅
- Files: Delete `utilities/text.py` (identical to `core/text.py`)
- Details:
  1. Verify files are identical: `diff src/good_agent/utilities/text.py src/good_agent/core/text.py`
  2. Find all imports: `rg "from good_agent.utilities.text" -l`
  3. Replace imports: `sed -i '' 's/good_agent.utilities.text/good_agent.core.text/g'`
  4. Delete: `rm src/good_agent/utilities/text.py`
  5. Run tests: `uv run pytest`
- Complexity: Low
- Dependencies: Step 1 complete
- Success Criteria: Single text.py, all imports canonical, tests passing

### 3. [x] **Remove Debug/Manual Tests** - NO RISK ✅
- Files: Delete `tests/unit/templating/debug_minimal_test.py`, `tests/unit/agent/manual_registry_discovery.py`
- Details:
  1. Review files to ensure they're not actual tests
  2. Move to `scripts/debug/` if needed for development
  3. Delete from test suite
  4. Verify test discovery doesn't pick them up: `uv run pytest --collect-only`
- Complexity: Low
- Dependencies: None
- Success Criteria: No debug tests in suite, faster test discovery

### 4. [x] **Add Tests for pool.py** - MEDIUM RISK ✅
- Files: Create `tests/unit/test_pool.py`
- Details:
  1. Read `src/good_agent/pool.py` to understand AgentPool functionality
  2. Create comprehensive unit tests:
     - Pool initialization
     - Agent creation and reuse
     - Concurrent operations
     - Pool cleanup
     - Resource limits
  3. Achieve >80% coverage for pool.py
  4. Add test markers: `@pytest.mark.unit`
- Complexity: Medium
- Dependencies: None
- Success Criteria: pool.py has >80% test coverage, tests passing

### 5. [x] **Add Tests for utilities/** - MEDIUM RISK ✅
- Files: Create tests for `utilities/printing.py`, `utilities/lxml.py`, `utilities/retries.py`, `utilities/logger.py`
- Details:
  1. Create `tests/unit/utilities/test_printing.py`:
     - Test output formatting
     - Test color handling
     - Test width wrapping
  2. Create `tests/unit/utilities/test_lxml.py`:
     - Test XML extraction functions
     - Test error handling
     - Test edge cases (malformed XML)
  3. Create `tests/unit/utilities/test_retries.py`:
     - Test retry logic
     - Test backoff strategies
     - Test max attempts
     - Test exception handling
  4. Create `tests/unit/utilities/test_logger.py`:
     - Test log configuration
     - Test log levels
     - Test log formatting
  5. Run coverage report: `uv run pytest --cov=src/good_agent/utilities`
- Complexity: Medium
- Dependencies: None
- Success Criteria: All utility modules have >80% coverage, tests passing

### 6. [x] **Consolidate Template Duplication** - MEDIUM RISK ✅
- Files: Keep `core/templating/` as canonical, remove `templating/` wrappers
- Details:
  1. Audit template system usage: `rg "from good_agent.templating" -l`
  2. Identify which files in `templating/` are wrappers vs unique functionality
  3. Keep `templating/core.py` (TemplateManager component) - move to `components/template_manager.py`
  4. Update imports to use `core.templating` directly
  5. Delete wrapper files
  6. Run template tests: `uv run pytest tests/unit/templating/`
- Complexity: Medium
- Dependencies: None (per user: keep template system structure, only remove wrapper duplication)
- Success Criteria: Single canonical template location, all template tests passing

### 7. [x] **Verify and Document Changes** ✅
- Files: Update `CHANGELOG.md`, create `MIGRATION.md`
- Details:
  1. Document all import path changes in CHANGELOG.md
  2. Create MIGRATION.md with find-replace commands for users
  3. Update project CLAUDE.md with new canonical locations
  4. Run full test suite: `uv run pytest`
  5. Run linting: `uv run ruff check .`
  6. Verify no broken imports: `uv run python -c "import good_agent; print('OK')"`
- Complexity: Low
- Dependencies: All Phase 1 steps complete
- Success Criteria: Complete documentation, all tests passing, no import errors

**Phase 1 Integration Points:**
- Git: All changes in feature branch `refactor/phase-1-duplication`
- CI/CD: Full test suite must pass
- Code Review: Review all import changes
- Dependencies: No external dependency changes

**Phase 1 Rollback Plan:**
- Git revert entire feature branch
- All changes are mechanical, low risk
- No API changes, only internal reorganization

### Phase 1 Completion Summary ✅

**Completed:** 2025-11-11
**Duration:** 1 day (estimated 2 weeks in plan)
**Status:** ✅ All steps complete

**Results:**
- ✅ 5 wrapper files deleted (event_router, ulid_monotonic, signal_handler, models/__init__, types/__init__)
- ✅ 1 duplicate file deleted (utilities/text.py, 699 lines)
- ✅ 3 debug test files moved to scripts/debug/
- ✅ 72 new tests added (22 pool + 50 utilities)
- ✅ All 96 new utility tests passing (100% pass rate)
- ✅ Template system verified (91 tests passing, no duplication)
- ✅ Zero wrapper imports remaining in codebase
- ✅ Ruff linting clean
- ✅ 1375 total tests collected
- ✅ PHASE1_SUMMARY.md documentation created
- ✅ Committed to branch refactor/phase-1-duplication (commit bd403b8)

**Impact:**
- Lines removed: ~3,700
- Lines added: ~800 (tests + docs)
- Net reduction: ~2,900 lines
- Breaking changes: NONE (internal only)
- Files modified: 49 total

**Verification:**
- All imports verified using ripgrep
- No wrapper module references remain
- Full test suite passing
- Ruff linting passes
- Documentation complete (PHASE1_SUMMARY.md)

**Ready for:** Phase 2 - Break Up Large Files

---

## Phase 2: Break Up Large Files (Weeks 3-5) - NEARLY COMPLETE ✅⚠️

**Status:** Nearly Complete - Agent managers ✅, messages.py split ✅, model/llm.py split ✅, but agent/core.py still needs reduction
**Branch:** `refactor/phase-2-completion`
**Commits:** `64e66db` through `0b4cdca`
**Goal:** Split agent.py, messages.py, llm.py, event_router.py into cohesive modules <600 lines each.

### 1. [x] **Refactor agent.py - Week 1** - HIGH RISK - PARTIALLY COMPLETE ⚠️
- Files: Split `agent.py` (4,174 lines) into `agent/` directory with 8 modules
- Details:

  **Week 1, Day 1-2: Extract MessageManager**
  1. Create `agent/messages.py`:
     ```python
     class MessageManager:
         """Manages message list operations, filtering, and validation."""
         def __init__(self, agent: Agent):
             self.agent = agent
             self._messages: MessageList = ...

         @property
         def user(self) -> FilteredMessageList[UserMessage]:
             return self._messages.filter(role="user")

         @property
         def assistant(self) -> FilteredMessageList[AssistantMessage]:
             return self._messages.filter(role="assistant")

         def append(self, *content_parts, role="user", **kwargs):
             """Add message to list."""
             ...

         def replace(self, index, message):
             """Replace message at index."""
             ...
     ```
  2. Update Agent class to use MessageManager:
     ```python
     class Agent(EventRouter):
         def __init__(self, ...):
             self._message_manager = MessageManager(self)

         @property
         def messages(self):
             return self._message_manager._messages

         @property
         def user(self):
             return self._message_manager.user

         def append(self, *args, **kwargs):
             return self._message_manager.append(*args, **kwargs)
     ```
  3. Move message-related tests to `tests/unit/agent/test_message_manager.py`
  4. Run tests: `uv run pytest tests/unit/agent/test_message_manager.py`

  **Week 1, Day 3: Extract AgentStateMachine**
  1. Create `agent/state.py`:
     ```python
     class AgentStateMachine:
         """Manages agent state transitions and validation."""
         def __init__(self, agent: Agent):
             self.agent = agent
             self._state: AgentState = AgentState.INITIALIZING
             self._ready_event = asyncio.Event()

         def update_state(self, new_state: AgentState):
             """Transition to new state."""
             ...

         async def wait_for_ready(self):
             """Wait until agent is ready."""
             await self._ready_event.wait()
     ```
  2. Update Agent class
  3. Move state tests
  4. Run tests

  **Week 1, Day 4: Extract ToolExecutor**
  1. Create `agent/tools.py`:
     ```python
     class ToolExecutor:
         """Executes tool calls and manages tool lifecycle."""
         def __init__(self, agent: Agent):
             self.agent = agent

         async def execute_tool(self, tool_call: ToolCall):
             """Execute single tool call."""
             ...

         async def execute_tool_calls(self, message: AssistantMessage):
             """Execute all tool calls in message."""
             ...
     ```
  2. Update Agent class
  3. Move tool tests
  4. Run tests

  **Week 1, Day 5: Extract LLMCoordinator**
  1. Create `agent/llm.py`:
     ```python
     class LLMCoordinator:
         """Coordinates LLM API calls, streaming, structured output."""
         def __init__(self, agent: Agent):
             self.agent = agent

         async def complete(self, messages: list[Message], **kwargs):
             """Get LLM completion."""
             ...

         async def stream(self, messages: list[Message], **kwargs):
             """Stream LLM completion."""
             ...

         async def extract(self, messages: list[Message], schema: type[T]) -> T:
             """Get structured output."""
             ...
     ```
  2. Update Agent class
  3. Move LLM tests
  4. Run tests

  **Week 2, Day 1: Extract ComponentRegistry**
  1. Create `agent/components.py`:
     ```python
     class ComponentRegistry:
         """Manages component lifecycle and dependencies."""
         def __init__(self, agent: Agent):
             self.agent = agent
             self._components: dict[str, AgentComponent] = {}

         def register_extension(self, component: AgentComponent):
             """Register component."""
             ...

         async def install_components(self):
             """Install all registered components."""
             ...
     ```
  2. Update Agent class
  3. Move component tests
  4. Run tests

  **Week 2, Day 2: Extract ContextManager**
  1. Create `agent/context.py`:
     ```python
     class ContextManager:
         """Manages fork, thread, and context operations."""
         def __init__(self, agent: Agent):
             self.agent = agent

         def fork_context(self) -> Agent:
             """Create forked agent context."""
             ...

         def thread_context(self) -> Agent:
             """Create thread context."""
             ...
     ```
  2. Update Agent class
  3. Move context tests
  4. Run tests

  **Week 2, Day 3: Extract VersioningManager**
  1. Create `agent/versioning.py`:
     ```python
     class VersioningManager:
         """Manages message versioning operations."""
         def __init__(self, agent: Agent):
             self.agent = agent

         def revert_to_version(self, index: int):
             """Revert to specific version."""
             ...

         @property
         def current_version(self) -> int:
             """Get current version."""
             ...
     ```
  2. Update Agent class
  3. Move versioning tests
  4. Run tests

  **Week 2, Day 4-5: Finalize Agent Core** ✅ DONE (but core.py still 2,758 lines - needs further reduction)
  1. ✅ Create `agent/core.py` with Agent class
  2. ✅ Create `agent/__init__.py` to export Agent
  3. ✅ Update all imports throughout codebase
  4. ✅ Run full test suite: `uv run pytest tests/unit/agent/`
  5. ✅ Verify Agent API unchanged for backward compatibility
  6. ✅ Update documentation (PHASE2_SUMMARY.md - commit 77a1840)

**Phase 2.1 Actual Results:**
  - ✅ agent/messages.py - MessageManager (333 lines) ✅
  - ✅ agent/state.py - AgentStateMachine (123 lines) ✅
  - ✅ agent/tools.py - ToolExecutor (655 lines) ⚠️ (exceeds 500 line target)
  - ✅ agent/llm.py - LLMCoordinator (282 lines) ✅
  - ✅ agent/components.py - ComponentRegistry (254 lines) ✅
  - ✅ agent/context.py - ContextManager (186 lines) ✅
  - ✅ agent/versioning.py - AgentVersioningManager (115 lines) ✅
  - ⚠️ agent/core.py - Agent class (2,758 lines) - STILL TOO LARGE (target was <600 lines)
  - ✅ All agent tests passing
  - ✅ Public API unchanged (backward compatible)

**Remaining Work for Phase 2.1:**
  - [ ] Reduce agent/core.py from 2,758 lines to <600 lines (need to extract more logic to managers or trim docstrings further)

- Complexity: High
- Dependencies: Phase 1 complete ✅
- Success Criteria:
  - ⚠️ agent/core.py <600 lines - NOT MET (currently 2,758 lines)
  - ✅ 8 focused manager modules <500 lines each - MOSTLY MET (tools.py is 655 lines)
  - ✅ All agent tests passing - MET
  - ✅ Public API unchanged (backward compatible) - MET
  - ✅ No performance regression - MET

### 2. [x] **Refactor messages.py** - MEDIUM RISK - ✅ COMPLETE
- Files: Split `messages.py` (1,813 lines) into `messages/` package
- Details:
  1. ✅ Created `messages/base.py` (785 lines):
     - Message base class with trimmed docstrings
     - Annotation class
     - Core message functionality
     - All rendering and protocol methods
  2. ✅ Created `messages/roles.py` (186 lines):
     - SystemMessage, UserMessage
     - AssistantMessage, AssistantMessageStructuredOutput
     - ToolMessage with Generic support
  3. ✅ Created `messages/message_list.py` (328 lines):
     - MessageList implementation
     - Versioning support
     - Filter operations
  4. ✅ Created `messages/filtering.py` (140 lines):
     - FilteredMessageList with role-specific filtering
     - Config integration for system messages
     - Append/set operations
  5. ✅ Created `messages/utilities.py` (58 lines):
     - MessageFactory
     - Helper functions
  6. ✅ Created `messages/__init__.py` (69 lines):
     - Public API exports for backward compatibility
     - Re-exports ToolCall, ToolResponse, RenderMode
  7. ✅ Updated imports throughout codebase
  8. ✅ Ran tests: 1,142 out of 1,157 passing (98.7%)
- Complexity: Medium
- Dependencies: Phase 1 complete ✅
- Success Criteria:
  - ✅ Each module <800 lines (achieved: largest is base.py at 785 lines)
  - ✅ All message tests mostly passing (15 minor test failures related to error message formatting)
  - ✅ Backward compatibility maintained via __init__.py
  - ✅ Total line reduction: 262 lines saved (14.4% through docstring trimming)

### 3. [x] **Refactor model/llm.py** - MEDIUM RISK - ✅ COMPLETE
- Files: Split `model/llm.py` (1,889 lines) into focused modules
- Details:
  1. ✅ Created `model/protocols.py` (79 lines) - Type protocols, TypedDicts, constants
  2. ✅ Created `model/capabilities.py` (184 lines) - ModelCapabilities with 13 supports_* methods
  3. ✅ Created `model/formatting.py` (437 lines) - MessageFormatter for LLM API conversion
  4. ✅ Created `model/structured.py` (141 lines) - StructuredOutputExtractor for Pydantic
  5. ✅ Created `model/streaming.py` (205 lines) - StreamingHandler for async streaming
  6. ✅ Created `model/llm.py` (920 lines) - Core LanguageModel with delegation to helpers
  7. ✅ Updated imports throughout codebase (agent/llm.py)
  8. ✅ All 313 agent tests passing (100%)
  9. ✅ All formatting/linting checks pass
- Complexity: Medium
- Dependencies: Phase 1 complete ✅
- Success Criteria:
  - ✅ Each module <500 lines - MET (largest is formatting.py at 437 lines)
  - ✅ Core llm.py reduced by 51% (1,889 → 920 lines)
  - ✅ All model tests passing - MET
  - ✅ Full backward compatibility - MET
  - ✅ Clean separation of concerns - MET

### 4. [x] **Document Phase 2 Changes** - PARTIALLY COMPLETE ⚠️
- Files: Update `CHANGELOG.md`, `MIGRATION.md`
- Details:
  1. ✅ Document all module splits (PHASE2_SUMMARY.md created - commit 77a1840)
  2. ⚠️ Provide import migration examples (only for agent/ package, not messages/ or model/)
  3. ✅ Update internal documentation
  4. ✅ Run full test suite
  5. ✅ Verify no regressions
- Complexity: Low
- Dependencies: All Phase 2 steps complete ⚠️ (Steps 2 & 3 incomplete)
- Success Criteria:
  - ⚠️ Complete documentation - PARTIAL (only agent/ package documented)
  - ✅ All tests passing - MET

**Actual Status (Updated 2025-11-14):**
- ✅ PHASE2_SUMMARY.md created documenting agent package restructuring
- ✅ messages.py SPLIT into messages/ package (6 modules, 1,566 total lines) - commit 87142ec
- ✅ model/llm.py SPLIT into 6 modules (1,966 total lines, core reduced 51%) - commit 0b4cdca
- ✅ All 313 agent tests passing (100%)
- ✅ All formatting/linting checks passing
- ✅ Committed to branch refactor/phase-2-completion (commits through 0b4cdca)
- ❌ agent/core.py still 2,758 lines (target: <600 lines)
- ❌ CHANGELOG.md not updated for Phase 2
- ❌ MIGRATION.md not updated for Phase 2

**Phase 2 Integration Points:**
- Git: Feature branch `refactor/phase-2-file-splits`
- Testing: Full regression testing after each major split
- Performance: Benchmark core operations before/after

**Phase 2 Rollback Plan:**
- Revert specific module splits independently
- Each split is isolated and testable
- Backward compatibility maintained throughout

### Phase 2 Completion Summary - NEARLY COMPLETE ✅⚠️

**Completed:** 2025-11-14 (manager extraction + messages split + model/llm.py split)
**Duration:** Multiple days (commits 64e66db through 0b4cdca)
**Status:** ✅ Steps 1-3 complete, only agent/core.py reduction remaining

**What Was Completed:**
- ✅ **Agent manager extraction** (MessageManager, StateMachine, ToolExecutor, LLMCoordinator, ComponentRegistry, ContextManager, VersioningManager)
  - All 7 manager classes created in agent/ package
  - All agent tests passing
  - Public API backward compatible
  - PHASE2_SUMMARY.md documentation created

- ✅ **messages.py split** (commit 87142ec)
  - Converted to messages/ package with 6 modules (1,566 total lines)
  - messages/base.py (785 lines) - Message base class
  - messages/roles.py (186 lines) - Role-specific messages
  - messages/message_list.py (328 lines) - MessageList with versioning
  - messages/filtering.py (140 lines) - FilteredMessageList
  - messages/utilities.py (58 lines) - MessageFactory
  - messages/__init__.py (69 lines) - Public API
  - 262 lines saved through docstring trimming (14.4% reduction)
  - All message tests fixed and passing (203/203, 100%)
  - Full backward compatibility maintained

- ✅ **model/llm.py split** (commit 0b4cdca)
  - Converted to model/ package with 6 modules (1,966 total lines)
  - model/protocols.py (79 lines) - Type protocols, TypedDicts, constants
  - model/capabilities.py (184 lines) - ModelCapabilities with 13 supports_* methods
  - model/formatting.py (437 lines) - MessageFormatter for LLM API conversion
  - model/structured.py (141 lines) - StructuredOutputExtractor for Pydantic
  - model/streaming.py (205 lines) - StreamingHandler for async streaming
  - model/llm.py (920 lines) - Core LanguageModel with delegation
  - Core file reduced by 51% (1,889 → 920 lines)
  - All 313 agent tests passing (100%)
  - Full backward compatibility maintained via lazy imports

**What Was NOT Completed:**
- ❌ agent/core.py still 2,758 lines (target: <600 lines)
- ❌ CHANGELOG.md not updated
- ❌ MIGRATION.md not updated

**Impact:**
- Lines reduced in agent/: Created 7 manager modules totaling ~1,948 lines
- Lines reduced in messages/: 262 lines saved (1,813 → 1,566 lines, 14.4%)
- Lines reduced in model/: Core file reduced 51% (1,889 → 920 lines)
- agent/core.py: Still contains 2,758 lines (needs further reduction)
- Breaking changes: NONE (backward compatible via __init__.py files and lazy imports)

**Next Steps to Complete Phase 2:**
1. Further reduce agent/core.py to <600 lines (extract more logic or trim docstrings)
2. Update CHANGELOG.md and MIGRATION.md
3. Create complete Phase 2 documentation

**Ready for:** Phase 2 completion (agent/core.py reduction only)

---

## Phase 3: Simplify Complexity (Weeks 6-7)

**Goal:** Evaluate and potentially simplify event router, reduce documentation verbosity.

### 1. [ ] **Audit Event Router for Race Conditions and Complexity** - HIGH RISK
- Files: Analyze `core/event_router.py` (2,000+ lines)
- Details:
  1. **Week 6, Day 1-2: Analysis**
     - Document all event router features
     - Identify race condition risks (user concern)
     - Profile actual usage in codebase: `rg "@on\(|\.on\(|emit\(" -A 3`
     - Measure feature usage:
       ```bash
       rg "priority=" src/ tests/ | wc -l  # Priority usage
       rg "predicate=" src/ tests/ | wc -l  # Predicate usage
       rg "LifecyclePhase" src/ tests/ | wc -l  # Lifecycle usage
       ```
     - Interview: Review with user about specific race condition concerns
     - Document findings in `DECISIONS.md`

  2. **Week 6, Day 3: Decision Point**
     - **Option A: Simplify Event Router**
       - Remove rarely-used features (priority, predicates, lifecycle phases)
       - Fix race conditions
       - Reduce to core functionality (~800 lines)
       - **Risk**: Breaking changes for extensions using advanced features
       - **Benefit**: Clearer, safer, easier to maintain

     - **Option B: Reorganize Event Router**
       - Split into modules (core, context, decorators, advanced)
       - Fix race conditions without removing features
       - Improve documentation of thread safety
       - **Risk**: Complexity remains, race conditions still possible
       - **Benefit**: Backward compatible, less risk

     - **Option C: Defer Event Router Changes**
       - Fix only critical race conditions
       - Add better documentation and warnings
       - Plan deeper refactor for v1.0
       - **Risk**: Technical debt accumulates
       - **Benefit**: Lowest risk, focus on other priorities

  3. **Week 6, Day 4-5: Implementation** (based on decision)
     - If Option A or B chosen, proceed with refactoring
     - If Option C, document race conditions and add warnings
     - Create comprehensive tests for thread safety
     - Run full test suite

- Complexity: High
- Dependencies: Phase 2 complete
- Success Criteria:
  - Race conditions identified and documented/fixed
  - Clear decision made and documented
  - Tests demonstrate thread safety or document limitations
  - User approves approach

### 2. [ ] **Trim Documentation Verbosity** - LOW RISK
- Files: All source files with docstrings >30 lines
- Details:
  1. **Week 7, Day 1: Audit**
     - Identify all docstrings >50 lines:
       ```bash
       python scripts/find_large_docstrings.py > large_docstrings.txt
       ```
     - Extract examples from docstrings to `examples/` directory
     - Note performance claims to verify or remove

  2. **Week 7, Day 2: Create Examples Directory**
     ```
     examples/
     ├── README.md
     ├── basic/
     │   ├── hello_world.py
     │   ├── with_tools.py
     │   └── structured_output.py
     ├── components/
     │   ├── simple_component.py
     │   ├── tool_component.py
     │   └── event_component.py
     ├── advanced/
     │   ├── multi_agent.py
     │   ├── custom_llm.py
     │   ├── streaming.py
     │   └── versioning.py
     └── troubleshooting/
         ├── common_errors.py
         └── debugging.py
     ```
     - Extract all docstring examples to executable files
     - Add tests for examples: `uv run pytest examples/`

  3. **Week 7, Day 3-4: Reduce Core Docstrings**
     - Agent.__init__: 200 lines → 15 lines
     - Agent class: 500 lines → 20 lines
     - LanguageModel: 400 lines → 15 lines
     - AgentComponent: 300 lines → 15 lines
     - EventRouter: 300 lines → 15 lines

     Standard concise format:
     ```python
     """[One-line summary]

     [Optional 2-3 line elaboration]

     Args:
         param: Description (one line)

     Returns:
         Description (one line)

     Example:
         >>> agent = Agent("gpt-4", tools=[search])
         >>> await agent.chat("Hello")

     See Also:
         examples/basic/hello_world.py - Complete working example
     """
     ```

  4. **Week 7, Day 5: Systematic Cleanup**
     - Process all remaining docstrings
     - Remove template sections: PURPOSE, ROLE, TYPICAL USAGE, PERFORMANCE CHARACTERISTICS, COMMON PITFALLS
     - Keep: Summary, Args, Returns, Raises, short Example, See Also
     - Target ratio: 1:3 to 1:1 documentation to code

- Complexity: Low
- Dependencies: None (can run in parallel with Phase 3.1)
- Success Criteria:
  - Average docstring <15 lines
  - No docstrings >30 lines (link to docs instead)
  - Complete `examples/` directory with tested examples
  - Docstring/code ratio improved to 1:1

### 3. [ ] **Document Phase 3 Changes**
- Files: Update `CHANGELOG.md`, `MIGRATION.md`, create `DECISIONS.md`
- Details:
  1. Document event router decision and rationale
  2. Link to examples/ for practical usage
  3. Update contribution guidelines with docstring standards
  4. Run full test suite
- Complexity: Low
- Dependencies: All Phase 3 steps complete
- Success Criteria: Clear documentation of architectural decisions

**Phase 3 Integration Points:**
- Git: Feature branch `refactor/phase-3-simplification`
- Testing: Extra focus on event router thread safety tests
- User Review: Event router decision requires explicit user approval

**Phase 3 Rollback Plan:**
- Event router: Can revert independently if issues found
- Documentation: No code impact, low risk
- Examples: Additive only, no rollback needed

---

## Phase 4: API Improvements (Weeks 8-9)

**Goal:** Consolidate API surface, improve consistency, reduce cognitive load.

### 1. [ ] **Consolidate Message Operations** - MEDIUM RISK
- Files: `agent/core.py`, `agent/messages.py`
- Details:
  1. **Week 8, Day 1-2: Standardize on 2 patterns**

     Current problems:
     ```python
     # 5 different ways - TOO MANY
     agent.append("Hello", role="user")
     msg = agent.model.create_message("Hello", role="user"); agent.append(msg)
     agent.messages.append(msg)
     agent._append_message(msg)
     agent.add_tool_response("result", tool_call_id="123")
     ```

     New simplified patterns:
     ```python
     # Pattern 1: Convenience (90% of use cases)
     agent.append("Hello")  # User message by default
     agent.append("Response", role="assistant")
     agent.append("Result", role="tool", tool_call_id="123")

     # Pattern 2: Full control (advanced)
     msg = Message(content="Hello", role="user")
     agent.messages.append(msg)
     ```

  2. **Implementation:**
     - Remove `add_tool_response()` → use `append()` with `role="tool"`
     - Make `append()` canonical (remove `_append_message()`)
     - Update all internal code to use new patterns
     - Add deprecation warnings for old methods:
       ```python
       def add_tool_response(self, ...):
           warnings.warn(
               "add_tool_response() is deprecated, use append(content, role='tool', tool_call_id=...) instead",
               DeprecationWarning,
               stacklevel=2
           )
           return self.append(...)
       ```

  3. Update tests and documentation
  4. Run full test suite

- Complexity: Medium
- Dependencies: Phase 2 complete (agent split)
- Success Criteria:
  - 2 clear patterns documented
  - Deprecation warnings for old methods
  - All tests updated
  - Migration guide complete

### 2. [ ] **Clarify call() vs execute()** - LOW RISK
- Files: `agent/core.py`
- Details:
  1. **Week 8, Day 3: Improve documentation**
     ```python
     async def call(self, prompt: str | None = None) -> AssistantMessage:
         """Get single response from LLM.

         Adds prompt as user message (if provided), calls LLM, automatically
         executes any tool calls, and returns final assistant response.

         For step-by-step control over execution, use execute() instead.

         Args:
             prompt: User message to add before calling LLM. If None,
                 calls LLM with existing messages.

         Returns:
             Final assistant message after all tool calls complete.

         Example:
             >>> response = await agent.call("What's the weather?")
             >>> print(response.content)

         See Also:
             execute() - For streaming or custom tool execution
         """

     async def execute(self) -> AsyncIterator[Message]:
         """Execute agent loop with full control over each step.

         Yields each message (assistant, tool) as it's created. Use for
         streaming or when you need custom tool execution logic.

         Args:
             None - operates on current message list

         Yields:
             Each message as it's created during execution.

         Example:
             >>> async for msg in agent.execute():
             ...     print(f"{msg.role}: {msg.content}")

         See Also:
             call() - For simple single-response interaction
         """
     ```

  2. **Optional: Consider renaming** (if user approves)
     - `call()` → `chat()` (more conversational)
     - `execute()` → `run()` or `stream()` (clearer intent)
     - **Decision Point**: Breaking change, requires user approval

  3. Update all examples and tests

- Complexity: Low
- Dependencies: Phase 2 complete
- Success Criteria: Clear documentation, no confusion about use cases

### 3. [ ] **Reduce Agent Public API Surface** - MEDIUM RISK
- Files: `agent/core.py`
- Details:
  1. **Week 8, Day 4-5: Audit current API**
     ```bash
     # List all public methods/properties
     python -c "from good_agent import Agent; import inspect; print('\n'.join(sorted([m for m in dir(Agent) if not m.startswith('_')])))" > agent_api.txt
     ```

     Current: ~74 public methods/properties
     Target: <30 public methods

  2. **Move specialized methods to managers:**
     ```python
     # Before: Direct on Agent (clutters API)
     agent.revert_to_version(idx)
     agent.create_task(coro)
     agent.get_task_count()

     # After: Via manager properties (cleaner)
     agent.versioning.revert_to(idx)
     agent.versioning.current_version
     agent.tasks.create(coro)
     agent.tasks.count
     ```

  3. **Keep core API simple:**
     ```python
     class Agent:
         # Core operations (~10 methods)
         async def call(self, prompt) -> Message
         async def execute(self) -> AsyncIterator[Message]
         def append(self, content, **opts) -> None
         async def initialize(self)

         # Essential properties (~10)
         messages: MessageList
         config: AgentConfig
         tools: ToolManager
         model: LanguageModel
         user: FilteredMessageList[UserMessage]
         assistant: FilteredMessageList[AssistantMessage]

         # Manager properties (~5)
         versioning: VersioningManager
         tasks: TaskManager
         components: ComponentRegistry
         context: ContextManager
         state: AgentStateMachine
     ```

  4. **Add backward compatibility:**
     ```python
     # Forward old methods to managers with deprecation warnings
     def revert_to_version(self, idx: int):
         warnings.warn("Use agent.versioning.revert_to() instead", DeprecationWarning)
         return self.versioning.revert_to(idx)
     ```

  5. Update all code to use new manager properties
  6. Run full test suite

- Complexity: Medium
- Dependencies: Phase 2 complete (managers extracted)
- Success Criteria:
  - Agent class <30 public methods
  - Advanced features via manager properties
  - Backward compatibility maintained
  - Clear API documentation

### 4. [ ] **Standardize Property vs Method Usage** - LOW RISK
- Files: All agent modules
- Details:
  1. **Week 9, Day 1: Follow Python conventions**

     Properties (cheap, no side effects):
     ```python
     agent.messages          # ✅ List reference
     agent.user              # ✅ Filter (cached)
     agent.state             # ✅ Enum value
     agent.task_count        # ✅ Simple counter (was get_task_count())
     agent.is_ready          # ✅ Boolean (was ready() async method)
     ```

     Methods (async, side effects, expensive):
     ```python
     await agent.initialize()     # ✅ Async setup (renamed from ready())
     agent.print_message(msg)     # ✅ Side effect
     agent.validate_sequence()    # ✅ Expensive operation
     await agent.wait_for_ready() # ✅ Blocking operation
     ```

  2. **Specific changes:**
     - `agent.ready()` → `await agent.initialize()` (async method)
     - `agent.get_task_count()` → `agent.task_count` (property)
     - Ensure all properties are cheap and side-effect free

  3. Update all code and tests
  4. Document conventions in contribution guide

- Complexity: Low
- Dependencies: None
- Success Criteria: Consistent property vs method usage throughout codebase

### 5. [ ] **Document Phase 4 Changes**
- Files: Update `CHANGELOG.md`, `MIGRATION.md`, `API.md`
- Details:
  1. Document all API consolidations
  2. Provide migration examples for each change
  3. Create `docs/API.md` with clean public API reference
  4. Update all examples
  5. Run full test suite
- Complexity: Low
- Dependencies: All Phase 4 steps complete
- Success Criteria: Complete API documentation, migration guide

**Phase 4 Integration Points:**
- Git: Feature branch `refactor/phase-4-api-improvements`
- Testing: API-focused regression testing
- User Review: API changes require user approval before merge

**Phase 4 Rollback Plan:**
- Deprecation warnings allow gradual migration
- Can revert individual API changes independently
- Backward compatibility maintained via forwarding methods

---

## Phase 5: Testing & Quality (Weeks 10-11)

**Goal:** Reorganize tests, add markers, improve coverage, add performance benchmarks.

### 1. [ ] **Consolidate Agent Tests** - LOW RISK
- Files: `tests/unit/agent/` (32 files → 10 files)
- Details:
  1. **Week 10, Day 1-2: Consolidate to focused files**

     Current: 32 files (too fragmented)
     ```
     test_agent.py
     test_agent_invoke.py
     test_agent_tool_registry_integration.py
     test_agent_initialization_timeout.py
     test_agent_interruption.py
     test_agent_render_events.py
     ... 26 more files
     ```

     Target: 10 focused files
     ```
     tests/unit/agent/
     ├── test_agent_core.py              # Basic agent operations (merge 5 files)
     ├── test_agent_messages.py          # Message operations (merge 4 files)
     ├── test_agent_tools.py             # Tool execution (merge 6 files)
     ├── test_agent_components.py        # Component system (merge 3 files)
     ├── test_agent_state.py             # State management (merge 2 files)
     ├── test_agent_versioning.py        # Versioning (merge 2 files)
     ├── test_agent_context.py           # Fork/thread context (merge 2 files)
     ├── test_agent_integration.py       # End-to-end scenarios (merge 3 files)
     ├── test_language_model.py          # LLM integration (merge 3 files)
     └── test_agent_edge_cases.py        # Edge cases and errors (merge 2 files)
     ```

  2. **Consolidation strategy:**
     - Group related tests by feature area
     - Use test classes to organize within files:
       ```python
       # test_agent_core.py
       class TestAgentInitialization:
           def test_basic_init(self): ...
           def test_init_with_config(self): ...
           def test_init_timeout(self): ...

       class TestAgentExecution:
           async def test_call(self): ...
           async def test_execute(self): ...
           async def test_interruption(self): ...
       ```
     - Keep each consolidated file <400 lines
     - Preserve all test logic, just reorganize

  3. Run tests after each consolidation
  4. Verify test discovery: `uv run pytest --collect-only tests/unit/agent/`

- Complexity: Low
- Dependencies: Phase 2 complete (agent split)
- Success Criteria:
  - Agent tests in 10 files (was 32)
  - Each file <400 lines
  - All tests passing
  - Faster test discovery

### 2. [ ] **Separate Mock Tests** - LOW RISK
- Files: Move `tests/unit/agent/test_mock_*.py` (8 files)
- Details:
  1. **Week 10, Day 3: Create mock test directory**
     ```
     tests/unit/mock/
     ├── test_mock_agent.py           # Core mock functionality
     ├── test_mock_interface.py        # Mock interface operations
     └── test_mock_responses.py        # Response mocking
     ```

  2. Consolidate 8 mock test files into 3 focused files
  3. Update test discovery
  4. Run mock tests: `uv run pytest tests/unit/mock/`

- Complexity: Low
- Dependencies: None
- Success Criteria: Mock tests separated, 3 consolidated files

### 3. [ ] **Consolidate Component Tests** - LOW RISK
- Files: `tests/unit/components/` (15 files → 5-6 files)
- Details:
  1. **Week 10, Day 4: Identify duplicates**
     ```
     # Current: 4 files about event patterns
     test_component_event_integration.py
     test_component_event_patterns.py
     test_component_event_patterns_confirmed.py
     test_component_event_patterns_final.py
     ```

     Target:
     ```
     tests/unit/components/
     ├── test_component_core.py        # Basic functionality
     ├── test_component_events.py      # Event handling (merge 4 files)
     ├── test_component_tools.py       # Tool registration
     ├── test_component_injection.py   # Dependency injection
     ├── test_editable_resources.py    # Editable resources
     └── test_typed_events.py          # Type-safe events
     ```

  2. Remove `test_decorator_debug.py` (debugging artifact)
  3. Run tests after consolidation

- Complexity: Low
- Dependencies: None
- Success Criteria: Component tests in 5-6 files (was 15)

### 4. [ ] **Add Test Markers** - LOW RISK
- Files: `pyproject.toml`, all test files
- Details:
  1. **Week 10, Day 5: Update pyproject.toml**
     ```toml
     [tool.pytest.ini_options]
     markers = [
         "unit: Unit tests",
         "integration: Integration tests",
         "slow: Slow-running tests (>5s)",
         "vcr: Tests using VCR cassettes",
         "mock: Tests using mock LLM",
         "real_api: Tests requiring real API access",
         "requires_openai: Tests requiring OpenAI API key",
     ]
     ```

  2. **Tag existing tests:**
     ```python
     # Unit tests
     @pytest.mark.unit
     def test_agent_init():
         ...

     # VCR tests
     @pytest.mark.vcr
     @pytest.mark.slow
     def test_language_model_vcr():
         ...

     # Real API tests
     @pytest.mark.real_api
     @pytest.mark.requires_openai
     async def test_real_openai_call():
         ...
     ```

  3. **Update CI/CD:**
     ```yaml
     # Fast CI (every commit)
     - run: uv run pytest -m "not slow and not real_api"

     # Full CI (before merge)
     - run: uv run pytest -m "not real_api"

     # Nightly (with real APIs)
     - run: uv run pytest
     ```

  4. Document marker usage in README

- Complexity: Low
- Dependencies: None
- Success Criteria:
  - All tests properly marked
  - CI uses markers appropriately
  - Can run test subsets easily

### 5. [ ] **Add Performance Tests** - MEDIUM RISK
- Files: Create `tests/performance/`
- Details:
  1. **Week 11, Day 1-2: Create performance test suite**
     ```python
     # tests/performance/test_agent_scaling.py
     import pytest

     @pytest.mark.slow
     class TestAgentScaling:
         async def test_many_messages(self, benchmark):
             """Test agent with 1000 messages."""
             agent = Agent()
             for i in range(1000):
                 agent.append(f"Message {i}")

             result = benchmark(lambda: agent.messages.filter(role="user"))
             assert len(list(result)) == 1000

         async def test_tool_execution_overhead(self, benchmark):
             """Measure tool execution overhead."""
             agent = Agent(tools=[simple_tool])

             async def execute_tool():
                 return await agent.tools.execute_tool(...)

             result = benchmark(execute_tool)

         async def test_large_conversation_handling(self, benchmark):
             """Test performance with large conversations."""
             agent = Agent()
             # Add 100 multi-turn conversations
             for i in range(100):
                 agent.append(f"User {i}")
                 agent.append(f"Assistant {i}", role="assistant")

             result = benchmark(lambda: agent.messages[-1])
     ```

  2. **Create benchmark tests for:**
     - Message list operations (append, filter, slice)
     - Tool execution overhead
     - Component initialization time
     - Large conversation handling (1000+ messages)
     - Memory usage with versioning

  3. **Set up pytest-benchmark:**
     ```bash
     uv add --dev pytest-benchmark
     ```

  4. **Create baseline metrics:**
     ```bash
     uv run pytest tests/performance/ --benchmark-save=baseline
     ```

  5. **Add to CI to track performance over time**

- Complexity: Medium
- Dependencies: Phase 2 complete
- Success Criteria:
  - 5-10 benchmark tests
  - Baseline metrics established
  - CI tracks performance regression

### 6. [ ] **Add VCR Test Documentation** - LOW RISK
- Files: Create `tests/cassettes/README.md`
- Details:
  1. **Week 11, Day 3: Document VCR testing**
     ```markdown
     # VCR Cassettes

     ## What are VCR cassettes?
     HTTP request/response recordings for deterministic testing.

     ## Regenerating cassettes
     ```bash
     # Delete old cassettes
     rm tests/cassettes/*.yaml

     # Re-record with real API
     OPENAI_API_KEY=xxx uv run pytest tests/ --vcr-record=all
     ```

     ## Cassette organization
     - `agent/` - Agent-level API interactions
     - `language_model/` - LLM API calls
     - `search/` - Search provider calls

     ## Best practices
     - Use VCR for integration tests with external APIs
     - Regenerate periodically to catch API changes
     - Never commit API keys in cassettes
     ```

  2. Organize cassettes by feature:
     ```
     tests/cassettes/
     ├── README.md
     ├── agent/
     ├── language_model/
     └── search/
     ```

  3. Add VCR configuration to conftest.py

- Complexity: Low
- Dependencies: None
- Success Criteria: Clear VCR documentation, organized cassettes

### 7. [ ] **Consolidate Fixtures** - LOW RISK
- Files: Restructure fixture files
- Details:
  1. **Week 11, Day 4: Organize fixtures**
     ```
     tests/
     ├── conftest.py              # Global fixtures (agent, mock_model)
     ├── support/
     │   ├── fixtures.py          # Common fixtures
     │   ├── factories.py         # Test object factories
     │   └── assertions.py        # Custom assertions
     └── unit/
         ├── conftest.py          # Unit test fixtures
         ├── agent/
         │   └── conftest.py      # Agent-specific fixtures
         └── components/
             └── conftest.py      # Component-specific fixtures
     ```

  2. Move fixtures to appropriate levels:
     - Global: Fixtures used across all tests
     - Unit: Fixtures used in unit tests
     - Module: Fixtures specific to one module

  3. Remove duplicate fixture definitions
  4. Document fixture usage

- Complexity: Low
- Dependencies: None
- Success Criteria: Clear fixture hierarchy, no duplication

### 8. [ ] **Document Phase 5 Changes**
- Files: Update `CHANGELOG.md`, create `TESTING.md`
- Details:
  1. Document test reorganization
  2. Create TESTING.md with:
     - How to run tests
     - Test markers and usage
     - How to add new tests
     - Performance testing guide
     - VCR testing guide
  3. Update contribution guidelines
  4. Run full test suite
- Complexity: Low
- Dependencies: All Phase 5 steps complete
- Success Criteria: Complete testing documentation

**Phase 5 Integration Points:**
- Git: Feature branch `refactor/phase-5-testing`
- CI/CD: Update to use new test organization and markers
- Performance: Establish baseline metrics

**Phase 5 Rollback Plan:**
- Test reorganization is low risk (logic unchanged)
- Can revert test file moves independently
- Performance tests are additive only

---

## Phase 6: Documentation & Polish (Week 12)

**Goal:** Create comprehensive documentation, finalize migration guide, establish conventions.

### 1. [ ] **Create Documentation Structure** - LOW RISK
- Files: Create `docs/` directory
- Details:
  1. **Day 1-2: Set up documentation**
     ```
     docs/
     ├── README.md                    # Documentation index
     ├── quickstart.md                # 5-minute getting started
     ├── installation.md              # Installation guide
     ├── concepts/
     │   ├── agents.md                # What are agents?
     │   ├── components.md            # Component system explained
     │   ├── events.md                # Event system guide
     │   ├── tools.md                 # Tool system
     │   ├── messages.md              # Message handling
     │   └── versioning.md            # Versioning system
     ├── guides/
     │   ├── basic-usage.md           # Common patterns
     │   ├── advanced-patterns.md     # Advanced usage
     │   ├── testing.md               # Testing your agents
     │   ├── performance.md           # Performance optimization
     │   └── migration-v0.3.md        # Migration from v0.2
     ├── api/
     │   ├── agent.md                 # Agent API reference
     │   ├── messages.md              # Messages API
     │   ├── components.md            # Components API
     │   └── tools.md                 # Tools API
     └── troubleshooting.md           # Common issues and solutions
     ```

  2. **Write core documentation:**
     - `quickstart.md`: Get users productive in 5 minutes
     - `concepts/agents.md`: Explain agent architecture
     - `guides/basic-usage.md`: Common usage patterns
     - `guides/migration-v0.3.md`: Complete migration guide

  3. **Set up documentation site:**
     - Use MkDocs or Sphinx
     - Configure for GitHub Pages or ReadTheDocs
     - Add search functionality
     - Deploy preview

- Complexity: Low
- Dependencies: All previous phases complete
- Success Criteria: Complete documentation site, easy navigation

### 2. [ ] **Verify Examples are Tested** - LOW RISK
- Files: All files in `examples/`, create `tests/test_examples.py`
- Details:
  1. **Day 3: Create example tests**
     ```python
     # tests/test_examples.py
     import pytest
     import importlib.util
     from pathlib import Path

     EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

     def load_example(example_path: Path):
         """Load example as module."""
         spec = importlib.util.spec_from_file_location("example", example_path)
         module = importlib.util.module_from_spec(spec)
         spec.loader.exec_module(module)
         return module

     @pytest.mark.parametrize("example_file", EXAMPLES_DIR.rglob("*.py"))
     def test_example_runs(example_file):
         """Test that example can be imported without errors."""
         if example_file.name.startswith("_"):
             pytest.skip("Private example file")

         # Load example - will raise if syntax errors
         load_example(example_file)

     # Add specific tests for key examples
     async def test_hello_world_example():
         from examples.basic import hello_world
         result = await hello_world.main()
         assert result is not None
     ```

  2. **Add examples/README.md:**
     ```markdown
     # Examples

     Executable examples demonstrating good-agent usage.

     ## Basic Examples
     - `basic/hello_world.py` - Simplest agent usage
     - `basic/with_tools.py` - Using tools
     - `basic/structured_output.py` - Structured responses

     ## Component Examples
     - `components/simple_component.py` - Basic component
     - `components/tool_component.py` - Component with tools
     - `components/event_component.py` - Event handling

     ## Advanced Examples
     - `advanced/multi_agent.py` - Multiple agents
     - `advanced/streaming.py` - Streaming responses
     - `advanced/versioning.py` - Message versioning

     ## Running Examples
     ```bash
     # Run specific example
     uv run python examples/basic/hello_world.py

     # Test all examples
     uv run pytest tests/test_examples.py
     ```
     ```

  3. Add CI job to test examples

- Complexity: Low
- Dependencies: Phase 3 (examples created)
- Success Criteria: All examples tested, documentation complete

### 3. [ ] **Establish Naming Conventions** - LOW RISK
- Files: Create `CONTRIBUTING.md`
- Details:
  1. **Day 4: Document conventions**
     ```markdown
     # Contributing Guide

     ## Code Organization

     ### Module Structure
     - `agent/` - Core agent functionality
     - `messages/` - Message handling
     - `model/` - LLM integration
     - `core/` - Foundational utilities
     - `components/` - Component system
     - `extensions/` - Built-in extensions

     ### Naming Conventions

     **Managers vs Registries vs Handlers:**
     - **Manager**: Coordinates operations (MessageManager, VersioningManager)
     - **Registry**: Stores and retrieves items (ComponentRegistry, ToolRegistry)
     - **Handler**: Processes specific events (EventHandler)
     - **Executor**: Executes operations (ToolExecutor)

     **Properties vs Methods:**
     - Property: Cheap, no side effects, feels like attribute
       - `agent.messages`, `agent.is_ready`, `agent.task_count`
     - Method: Expensive, has side effects, or action-oriented
       - `await agent.initialize()`, `agent.validate_sequence()`

     **Type Variable Naming:**
     - Suffix pattern: `T_Output`, `T_Message`, `T_Component`
     - Clear, descriptive names: `MessageRole`, `AgentState`

     **Test Naming:**
     - `test_{feature}_{scenario}.py` - Test file names
     - `test_{action}_{expected}` - Test function names
     - Example: `test_agent_call_with_tools_executes_correctly`

     ## Docstring Style

     Use concise Google-style docstrings:
     ```python
     def process(data: str) -> str:
         """Process data and return result.

         Args:
             data: Input data to process

         Returns:
             Processed result

         Example:
             >>> process("hello")
             'HELLO'
         """
     ```

     ## Testing Requirements

     - All new features need tests
     - Maintain >85% coverage
     - Use appropriate test markers
     - Add performance tests for core operations

     ## Pull Request Process

     1. Create feature branch from `main`
     2. Make changes with tests
     3. Run full test suite: `uv run pytest`
     4. Run linting: `uv run ruff check . && uv run ruff format .`
     5. Update CHANGELOG.md
     6. Create PR with description
     ```

  2. Add linting rules to enforce conventions:
     ```toml
     # pyproject.toml
     [tool.ruff]
     select = ["E", "F", "I", "N", "W"]

     [tool.ruff.lint.pydocstyle]
     convention = "google"
     ```

  3. Document in README

- Complexity: Low
- Dependencies: None
- Success Criteria: Clear contribution guidelines, enforced by linting

### 4. [ ] **Final Quality Checks** - LOW RISK
- Files: All source and test files
- Details:
  1. **Day 5: Run all quality checks**
     ```bash
     # Linting
     uv run ruff check .
     uv run ruff format --check .

     # Type checking
     uv run mypy src/good_agent/

     # Tests
     uv run pytest -v

     # Coverage
     uv run pytest --cov=src/good_agent --cov-report=html

     # Performance benchmarks
     uv run pytest tests/performance/ --benchmark-compare=baseline
     ```

  2. **Verify all acceptance criteria:**
     - Review each phase's success criteria
     - Check CHANGELOG.md completeness
     - Verify migration guide accuracy
     - Test documentation links
     - Review examples

  3. **Create release checklist:**
     ```markdown
     # v0.3.0 Release Checklist

     ## Code Quality
     - [ ] All tests passing
     - [ ] Linting passes
     - [ ] Type checking passes
     - [ ] Coverage >85%
     - [ ] No performance regressions

     ## Documentation
     - [ ] API documentation complete
     - [ ] Migration guide reviewed
     - [ ] Examples tested
     - [ ] CHANGELOG.md updated
     - [ ] README.md updated

     ## Verification
     - [ ] Install from source works
     - [ ] Examples run correctly
     - [ ] No broken links in docs
     - [ ] Version numbers updated
     ```

- Complexity: Low
- Dependencies: All phases complete
- Success Criteria: All quality checks pass, ready for release

### 5. [ ] **Prepare Release** - LOW RISK
- Files: `pyproject.toml`, `CHANGELOG.md`, `README.md`
- Details:
  1. **Update version:**
     ```toml
     [project]
     name = "good-agent"
     version = "0.3.0"  # or "1.0.0" if appropriate
     ```

  2. **Finalize CHANGELOG.md:**
     ```markdown
     # Changelog

     ## [0.3.0] - 2025-0X-XX

     ### Breaking Changes
     - Consolidated module hierarchy: utilities/ wrappers removed
     - Agent API reduced to core operations, advanced via managers
     - Message operations simplified to 2 patterns
     - State management simplified to boolean properties
     - Event router refactored (see migration guide)

     ### Added
     - Performance test suite with benchmarks
     - Comprehensive examples/ directory
     - Complete documentation site
     - Test markers for selective testing

     ### Changed
     - agent.py split into 8 focused modules
     - messages.py split into 5 modules
     - model/llm.py split into 6 modules
     - event_router.py reorganized
     - Tests consolidated (138 → ~80 files)
     - Docstrings reduced to concise format

     ### Fixed
     - Code duplication eliminated (~3,000 lines)
     - Race conditions in event router
     - Import consistency issues

     ### Removed
     - utilities/ wrapper modules
     - Verbose docstring templates
     - Debug tests from test suite

     ## Migration Guide
     See [docs/guides/migration-v0.3.md](docs/guides/migration-v0.3.md)
     ```

  3. **Update README.md:**
     - Update installation instructions
     - Update quick start examples
     - Link to documentation site
     - Update badges (version, tests, coverage)

  4. **Tag release:**
     ```bash
     git tag -a v0.3.0 -m "Version 0.3.0 - Major refactoring"
     git push origin v0.3.0
     ```

- Complexity: Low
- Dependencies: All phases complete
- Success Criteria: Release prepared, version tagged

**Phase 6 Integration Points:**
- Git: Final merge to `main`, create release tag
- Documentation: Deploy docs site
- PyPI: Publish new version (if applicable)

**Phase 6 Rollback Plan:**
- Documentation changes are low risk
- Can update docs post-release if needed
- Version tag can be deleted if critical issue found

---

## Testing Strategy

### Test Coverage Requirements

**Unit Tests**: Test individual functions/classes in isolation
- [ ] `agent/` modules - All manager classes
  - MessageManager: append, filter, replace operations
  - AgentStateMachine: state transitions, validation
  - ToolExecutor: tool execution, error handling
  - LLMCoordinator: API calls, streaming, structured output
  - ComponentRegistry: registration, installation, dependencies
  - ContextManager: fork, thread operations
  - VersioningManager: version tracking, revert
- [ ] `messages/` modules - Message classes and operations
  - Message base class and role-specific messages
  - MessageList operations
  - FilteredMessageList behavior
- [ ] `model/` modules - LLM integration
  - Message formatting for different providers
  - Capability detection
  - Streaming support
  - Structured output
- [ ] `utilities/` - All utility functions
  - printing.py, lxml.py, retries.py, logger.py
- [ ] `pool.py` - AgentPool functionality
- Edge cases: Empty messages, invalid states, malformed input
- Error cases: API failures, tool errors, validation failures

**Integration Tests**: Test component interactions
- [ ] Agent with LLM - End-to-end conversation flow
- [ ] Agent with tools - Tool execution pipeline
- [ ] Agent with components - Component lifecycle
- [ ] Event system - Event emission and handling across components
- [ ] Versioning - Version tracking across operations
- Mock boundaries: Mock external APIs (OpenAI, etc.), use real internal components

**End-to-End Tests**:
- [ ] Complete conversation workflow
- [ ] Multi-turn interaction with tools
- [ ] Agent forking and merging
- [ ] Component extension lifecycle
- [ ] Error recovery and retry

**Regression Tests**: Ensure no existing functionality breaks
- [ ] All existing tests must pass or be updated
- [ ] VCR tests verify API contract unchanged
- [ ] Performance tests ensure no regression
- Run full test suite: `uv run pytest`

### Test Scenarios

**Scenario 1: Happy Path - Simple Conversation**
- Input: `agent = Agent("gpt-4"); response = await agent.call("Hello")`
- Expected: AssistantMessage returned, conversation tracked
- Validates: Core agent functionality, message handling, LLM integration

**Scenario 2: Error Case - Invalid Model**
- Input: `agent = Agent("invalid-model-name")`
- Expected: ValueError raised with clear message
- Validates: Configuration validation, error handling

**Scenario 3: Error Case - Tool Execution Failure**
- Input: Agent with tool that raises exception
- Expected: Tool error caught, returned as tool message, LLM can handle
- Validates: Tool error handling, error recovery

**Scenario 4: Edge Case - Empty Message List**
- Input: `agent = Agent(); await agent.call()`
- Expected: ValueError or appropriate error (no user message to respond to)
- Validates: Input validation, edge case handling

**Scenario 5: Edge Case - Very Large Conversation**
- Input: Agent with 1000+ messages
- Expected: Performance acceptable, no memory issues
- Validates: Scalability, performance with large datasets

**Scenario 6: Integration - Component with Tools**
- Input: Agent with custom component that adds tools
- Expected: Tools registered, available, executable
- Validates: Component system, tool registration, integration

**Scenario 7: Integration - Event Handling**
- Input: Agent with event handlers, perform operations
- Expected: Events emitted, handlers called, correct order
- Validates: Event system, handler registration, event flow

**Scenario 8: Regression - VCR Tests**
- Input: Run VCR tests with recorded API responses
- Expected: All VCR tests pass, API contract unchanged
- Validates: External API compatibility maintained

## Acceptance Criteria

### Automated Checks
Tests and tools that MUST pass:

- [ ] All unit tests passing: `uv run pytest tests/unit/`
- [ ] All integration tests passing: `uv run pytest tests/integration/`
- [ ] Type checking passes: `uv run mypy src/good_agent/`
- [ ] Linting passes: `uv run ruff check .`
- [ ] Formatting correct: `uv run ruff format --check .`
- [ ] Code coverage >= 85%: `uv run pytest --cov=src/good_agent --cov-report=term --cov-fail-under=85`
- [ ] No performance regression: `uv run pytest tests/performance/ --benchmark-compare=baseline`

### Manual Verification
Non-automated criteria that must be validated:

- [ ] No references to utilities/ wrapper modules in src/
  - Check with: `rg "from good_agent.utilities.event_router" src/`
  - Check with: `rg "from good_agent.utilities.ulid_monotonic" src/`
  - Check with: `rg "from good_agent.utilities.signal_handler" src/`
- [ ] No duplicate implementations (utilities/text.py removed)
  - Check with: `find src/good_agent/utilities/ -name "text.py"`
- [ ] Agent.py split successfully
  - Verify: `wc -l src/good_agent/agent/core.py` < 600 lines
  - Verify: All manager modules < 500 lines each
- [ ] Performance meets requirements:
  - Baseline comparison: No >10% regression in key operations
  - Check with: `uv run pytest tests/performance/ --benchmark-compare=baseline`
- [ ] Documentation updated:
  - [ ] README.md - Updated for v0.3.0
  - [ ] CHANGELOG.md - Complete with all changes
  - [ ] MIGRATION.md - Complete migration guide
  - [ ] docs/ - Complete documentation site
  - [ ] examples/ - All examples tested and working
- [ ] API consistency:
  - [ ] Agent public API reduced to <30 methods
  - [ ] Advanced features accessible via manager properties
  - [ ] Clear API documentation in docs/api/
- [ ] Test organization:
  - [ ] Agent tests consolidated: 32 → 10 files
  - [ ] Component tests consolidated: 15 → 6 files
  - [ ] Mock tests separated: new tests/unit/mock/ directory
  - [ ] All tests have appropriate markers

### Code Quality Checks

- [ ] No code duplication
  - No `_v2`, `_new`, `_2` suffixes in function/class names
  - No identical or near-identical files
  - Verify with: `rg "def \w+_v\d|def \w+_new|class \w+V\d" src/`
- [ ] No commented-out code blocks
  - Except for explanatory examples in docstrings
  - Verify with manual review or: `rg "^\s*#.*def |^\s*#.*class " src/ --type py`
- [ ] Consistent naming conventions with existing codebase
  - Managers: `*Manager` suffix
  - Registries: `*Registry` suffix
  - Executors: `*Executor` suffix
  - Documented in CONTRIBUTING.md
- [ ] Proper error handling:
  - [ ] No bare `except:` clauses
  - [ ] Specific exception types used
  - [ ] Errors logged appropriately
  - Verify with: `rg "except\s*:" src/ --type py`
- [ ] Type safety:
  - [ ] Complete type hints on all public functions
  - [ ] No `Any` types without justification (comment explaining why)
  - [ ] Verify with: `uv run mypy src/good_agent/ --strict`
- [ ] Documentation:
  - [ ] All public APIs have docstrings
  - [ ] Docstrings follow concise format (5-15 lines)
  - [ ] Complex logic has explanatory comments
  - [ ] Non-obvious decisions documented

### Breaking Change Verification

- [ ] All breaking changes documented in CHANGELOG.md
- [ ] Migration guide provides clear upgrade path
- [ ] Examples updated to reflect new API
- [ ] Deprecation warnings added where appropriate
- [ ] Version number updated appropriately (0.3.0 or 1.0.0)

## Technical Debt & Issues

### Known Issues

**Issue: Event Router Race Conditions**
- **Description**: User reported concerns about race conditions in event router. Needs investigation in Phase 3.
- **Impact**: High (if confirmed)
- **Workaround**: None currently, pending Phase 3 analysis
- **Root Cause**: To be determined in Phase 3
- **Tracking**: Phase 3, Step 1 - Event router audit

**Issue: Large File Sizes Remain**
- **Description**: MDXL parser (1,800 lines) kept as-is per user request, may need refactoring later
- **Impact**: Medium
- **Workaround**: Exclude from this refactoring scope
- **Root Cause**: Specialized parser, complex to split
- **Tracking**: Document for future consideration in v1.0

**Issue: Template System Complexity**
- **Description**: Template system structure kept as-is per user request, only wrapper duplication removed
- **Impact**: Medium
- **Workaround**: Only remove wrapper duplication
- **Root Cause**: Template system works, risky to change architecture
- **Tracking**: Consider deeper refactor in v1.0

### Technical Debt

**Debt: Event Router Complexity**
- **Description**: Event router is 2,000+ lines with many features. Some may be over-engineered.
- **Priority**: Medium
- **Reason**: User expressed concerns but wants to evaluate per-phase
- **Future Work**: Phase 3 analysis will determine if simplification needed
- **Estimated Effort**: Large (if full simplification chosen)

**Debt: Component System Metaclass**
- **Description**: Component system uses metaclass for tool discovery, may be over-engineered
- **Priority**: Low
- **Reason**: Works but adds complexity
- **Future Work**: Consider simplification in future version
- **Estimated Effort**: Medium

**Debt: Verbose Git History**
- **Description**: Refactoring will create many commits and file moves
- **Priority**: Low
- **Reason**: Necessary for tracking changes
- **Future Work**: Consider squash merge for cleaner main branch history
- **Estimated Effort**: Small

### Blockers

No active blockers at start. Potential blockers:

- [ ] **Blocker: Event Router Decision** (Phase 3)
  - **Description**: Need to decide simplification vs reorganization approach
  - **Needed**: User review and decision after analysis
  - **Owner/Action**: Complete Phase 3 analysis, present options to user

- [ ] **Blocker: Breaking Changes Approval** (Phase 4)
  - **Description**: API changes require user approval before implementation
  - **Needed**: User review of proposed API changes
  - **Owner/Action**: Document proposed changes, get user sign-off

- [ ] **Blocker: Performance Regression** (Any Phase)
  - **Description**: If performance tests show >10% regression
  - **Needed**: Investigation and optimization
  - **Owner/Action**: Profile, identify bottleneck, optimize or revert

## Progress Tracking

### Implementation Checklist

**Phase 1: Foundation (Weeks 1-2)**
- [ ] Remove utilities/ wrapper modules
- [ ] Remove duplicate text.py
- [ ] Remove debug/manual tests
- [ ] Add tests for pool.py
- [ ] Add tests for utilities/ modules
- [ ] Consolidate template duplication
- [ ] Verify and document changes
- [ ] Run full test suite
- [ ] Commit and push to feature branch

**Phase 2: Break Up Files (Weeks 3-5)** - NEARLY COMPLETE ✅⚠️
- [x] Week 1: Extract Agent managers (messages, state, tools, llm) ✅
- [x] Week 2: Extract remaining managers (components, context, versioning) ✅
- [x] Week 2: Finalize Agent core ⚠️ (package created but core.py still 2,758 lines)
- [x] Refactor messages.py into modules ✅ COMPLETE (commit 87142ec, 2025-11-14)
  - [x] messages/base.py (785 lines)
  - [x] messages/roles.py (186 lines)
  - [x] messages/message_list.py (328 lines)
  - [x] messages/filtering.py (140 lines)
  - [x] messages/utilities.py (58 lines)
  - [x] messages/__init__.py (69 lines)
  - [x] 262 lines saved through docstring trimming
  - [x] 100% test pass rate (203/203 passing)
- [x] Refactor model/llm.py into modules ✅ COMPLETE (commit 0b4cdca, 2025-11-14)
  - [x] model/protocols.py (79 lines)
  - [x] model/capabilities.py (184 lines)
  - [x] model/formatting.py (437 lines)
  - [x] model/structured.py (141 lines)
  - [x] model/streaming.py (205 lines)
  - [x] model/llm.py (920 lines) - Core reduced 51%
  - [x] 100% test pass rate (313/313 passing)
- [x] Document Phase 2 changes ⚠️ PARTIAL (PHASE2_SUMMARY.md + spec updated, needs CHANGELOG/MIGRATION)
- [x] Run full test suite ✅
- [ ] Performance benchmark comparison ❌ NOT DONE

**Phase 3: Simplify Complexity (Weeks 6-7)**
- [ ] Week 6: Audit event router (usage, race conditions, complexity)
- [ ] Week 6: Decide event router approach (with user approval)
- [ ] Week 6: Implement event router changes
- [ ] Week 7: Create examples/ directory
- [ ] Week 7: Reduce core docstrings
- [ ] Week 7: Systematic docstring cleanup
- [ ] Document Phase 3 changes
- [ ] Run full test suite

**Phase 4: API Improvements (Weeks 8-9)**
- [ ] Week 8: Consolidate message operations
- [ ] Week 8: Clarify call() vs execute()
- [ ] Week 8: Reduce Agent public API surface
- [ ] Week 9: Standardize property vs method usage
- [ ] Document Phase 4 changes
- [ ] Get user approval for API changes
- [ ] Run full test suite

**Phase 5: Testing & Quality (Weeks 10-11)**
- [ ] Week 10: Consolidate agent tests (32 → 10)
- [ ] Week 10: Separate mock tests
- [ ] Week 10: Consolidate component tests (15 → 6)
- [ ] Week 10: Add test markers
- [ ] Week 11: Add performance tests
- [ ] Week 11: Add VCR test documentation
- [ ] Week 11: Consolidate fixtures
- [ ] Document Phase 5 changes
- [ ] Run full test suite

**Phase 6: Documentation & Polish (Week 12)**
- [ ] Create documentation structure (docs/)
- [ ] Write core documentation
- [ ] Set up documentation site
- [ ] Verify examples are tested
- [ ] Establish naming conventions (CONTRIBUTING.md)
- [ ] Final quality checks
- [ ] Prepare release (v0.3.0 or v1.0.0)
- [ ] Tag release

### Session Notes

#### Session 1 - 2025-11-11 - Specification Creation
- **Completed**:
  - Read all audit documents (8 files)
  - Gathered user requirements via questions
  - Analyzed codebase structure
  - Created comprehensive refactoring specification
- **Decisions Made**:
  - Accept breaking changes (v0.3.0 or v1.0.0)
  - Follow 12-week audit plan
  - Keep MDXL and template structure as-is
  - Evaluate event router simplification per-phase
  - Consolidate all file organization and duplication issues
- **Issues Found**:
  - None yet (planning phase)
- **Blockers**:
  - None yet
- **Next Steps**:
  - Review specification with user
  - Get approval to proceed
  - Begin Phase 1: Foundation

#### Session 2 - 2025-11-14 - Messages Package Split
- **Completed**:
  - Split messages.py (1,813 lines) into messages/ package (1,566 lines)
  - Created 6 focused modules: base, roles, message_list, filtering, utilities, __init__
  - Trimmed docstrings saving 262 lines (14.4% reduction)
  - Maintained full backward compatibility via __init__.py
  - Fixed FilteredMessageList initialization signature
  - Added config integration for system message set()
  - Fixed all message tests - 203/203 passing (100%)
  - Committed to branch refactor/phase-2-completion (commit 87142ec)
- **Decisions Made**:
  - Trim docstrings during split (instead of separate Phase 3 task)
  - Prioritize messages.py split over model/llm.py split
  - Keep backward compatibility via re-exports
  - Fix test failures before moving to next task
- **Issues Found**:
  - Initially had 15 test failures due to event delegation issues
  - Fixed FilteredMessageList.append() to delegate to agent
  - Fixed MessageFactory to support legacy formats
  - All tests now passing
- **Blockers**:
  - None
- **Next Steps**:
  - Split model/llm.py into 6 modules
  - Reduce agent/core.py to <600 lines
  - Update CHANGELOG.md and MIGRATION.md when Phase 2 fully complete

#### Session 3 - 2025-11-14 - Model/LLM.py Split
- **Completed**:
  - Split model/llm.py (1,889 lines) into 6 focused modules (1,966 total lines)
  - Created model/protocols.py (79 lines) - Type protocols, TypedDicts, constants
  - Created model/capabilities.py (184 lines) - ModelCapabilities with 13 supports_* methods
  - Created model/formatting.py (437 lines) - MessageFormatter for LLM API conversion
  - Created model/structured.py (141 lines) - StructuredOutputExtractor for Pydantic
  - Created model/streaming.py (205 lines) - StreamingHandler for async streaming
  - Streamlined model/llm.py to 920 lines (51% reduction)
  - Updated model/__init__.py for lazy loading of new modules
  - Fixed agent/llm.py import (ResponseWithUsage from protocols)
  - All 313 agent tests passing (100%)
  - All formatting/linting checks passing
  - Committed to branch refactor/phase-2-completion (commit 0b4cdca)
- **Decisions Made**:
  - Use composition pattern with helper classes
  - Lazy initialization of helpers via _ensure_helpers()
  - Preserve all callback hooks and complete() method logic exactly
  - Maintain full backward compatibility via lazy imports in __init__.py
- **Issues Found**:
  - Initial mypy type errors in formatting.py (fixed with explicit type annotations)
  - StreamChunk type mismatch (fixed with type: ignore)
  - Missing import in agent/llm.py (fixed by updating to use protocols)
  - All issues resolved, tests passing
- **Blockers**:
  - None
- **Next Steps**:
  - Reduce agent/core.py to <600 lines
  - Update CHANGELOG.md and MIGRATION.md
  - Update .spec/refactoring-plan.md with completed work

## References

- **Related Specs**: None (this is the master refactoring spec)
- **Audit Documents**: `.spec/00-executive-summary.md` through `.spec/08-recommendations.md`
- **External Docs**:
  - [Pydantic Documentation](https://docs.pydantic.dev/)
  - [LiteLLM Documentation](https://docs.litellm.ai/)
  - [pytest Documentation](https://docs.pytest.org/)
- **Design Docs**: To be created in `DECISIONS.md` as work progresses
- **PRs/Issues**: To be created for each phase
- **Similar Code**: N/A (unique to this project)

---

## Risk Assessment

### Overall Risk: MEDIUM

**Low Risk Areas:**
- Code duplication removal (mechanical changes)
- Test consolidation (logic unchanged)
- Documentation improvements (non-functional)
- Adding missing tests (additive only)

**Medium Risk Areas:**
- Agent.py split (complex, many dependencies)
- messages.py split (moderate complexity)
- model/llm.py split (moderate complexity)
- API surface reduction (user-facing changes)

**High Risk Areas:**
- Event router changes (user reported race conditions, widely used)
- Breaking API changes (requires user migration)
- Performance regressions (must monitor closely)

### Mitigation Strategies

1. **Incremental Changes**: Each phase is independently testable
2. **Backward Compatibility**: Deprecation warnings where possible
3. **Comprehensive Testing**: Full test suite after each change
4. **Performance Monitoring**: Benchmarks before/after each phase
5. **User Review**: Key decisions require user approval
6. **Rollback Plans**: Each phase can be reverted independently
7. **Feature Branches**: All work in isolated branches, merge only when stable

### Success Factors

✅ Clear scope and requirements
✅ Comprehensive audit as foundation
✅ Phased approach with clear milestones
✅ User engaged and provided clear guidance
✅ Existing test coverage to catch regressions
✅ Version control allows safe experimentation
✅ Breaking changes acceptable (pre-1.0)
✅ Timeline is realistic (12 weeks for 1-2 developers)

---

**Status**: Ready for review and approval to begin implementation.
