# Changelog

All notable changes to the good-agent library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2: Break Up Large Files (In Progress)

**Status**: Nearly Complete (as of 2025-11-14)

#### Changed

- **Agent Package Restructuring** (Commits: 64e66db through ccddd0a)
  - Converted `agent.py` monolith (4,174 lines) into modular `agent/` package
  - Created 7 focused manager classes:
    - `agent/messages.py` - MessageManager (333 lines)
    - `agent/state.py` - AgentStateMachine (123 lines)
    - `agent/tools.py` - ToolExecutor (655 lines)
    - `agent/llm.py` - LLMCoordinator (282 lines)
    - `agent/components.py` - ComponentRegistry (254 lines)
    - `agent/context.py` - ContextManager (186 lines)
    - `agent/versioning.py` - AgentVersioningManager (115 lines)
  - `agent/core.py` - Main Agent class (2,684 lines)
  - All manager classes use composition pattern with back-references to Agent
  - Public Agent API unchanged - fully backward compatible
  - 313/313 agent tests passing (100%)

- **Messages Package Split** (Commit: 87142ec, 2025-11-14)
  - Converted `messages.py` (1,813 lines) into `messages/` package (1,566 lines)
  - Created 6 focused modules:
    - `messages/base.py` (785 lines) - Message base class, Annotation, core functionality
    - `messages/roles.py` (186 lines) - SystemMessage, UserMessage, AssistantMessage, ToolMessage
    - `messages/message_list.py` (328 lines) - MessageList with versioning support
    - `messages/filtering.py` (140 lines) - FilteredMessageList with role-specific filtering
    - `messages/utilities.py` (58 lines) - MessageFactory and helper functions
    - `messages/__init__.py` (69 lines) - Public API exports for backward compatibility
  - Reduced total lines by 262 (14.4%) through docstring trimming
  - Fixed FilteredMessageList initialization and event delegation
  - 203/203 message tests passing (100%)
  - Full backward compatibility maintained via `__init__.py` re-exports

- **Model/LLM Package Split** (Commit: 0b4cdca, 2025-11-14)
  - Converted `model/llm.py` (1,889 lines) into modular structure (1,966 total lines)
  - Created 6 focused modules:
    - `model/protocols.py` (79 lines) - Type protocols, TypedDicts, constants
    - `model/capabilities.py` (184 lines) - ModelCapabilities with 13 supports_* methods
    - `model/formatting.py` (437 lines) - MessageFormatter for LLM API conversion
    - `model/structured.py` (141 lines) - StructuredOutputExtractor for Pydantic models
    - `model/streaming.py` (205 lines) - StreamingHandler for async streaming
    - `model/llm.py` (920 lines) - Core LanguageModel using helper composition
  - Core LanguageModel reduced by 51% (1,889 → 920 lines)
  - Uses composition pattern with lazy initialization of helpers
  - All callback hooks and complete() logic preserved exactly
  - 313/313 agent tests passing (100%)
  - Full backward compatibility via lazy imports in `model/__init__.py`

- **Design Documentation** (Commit: ccddd0a)
  - Added comprehensive human-in-the-loop interaction design to `.spec/v1/DESIGN.md`
  - Includes InteractionRequest/InteractionResult primitives
  - Agent API for user_input() with typed responses
  - InteractionManager for orchestration
  - Multi-agent orchestration support
  - Non-interactive testing patterns

#### Removed

- Removed 105 lines of commented-out code from `agent/core.py`
  - Old `resolve_pending_tool_calls()` method (moved to ToolExecutor)

#### Fixed

- FilteredMessageList.append() now properly delegates to agent's message manager
- MessageFactory supports legacy message format compatibility
- Updated agent/llm.py import to use ResponseWithUsage from model/protocols

### Phase 1: Foundation - Eliminate Code Duplication (Completed 2025-11-11)

**Status**: ✅ Complete (Commit: bd403b8)

#### Removed

- **Wrapper Modules** - Eliminated ~3,000 lines of duplicate code
  - Deleted `utilities/event_router.py` (wrapper to `core/event_router.py`)
  - Deleted `utilities/ulid_monotonic.py` (wrapper to `core/ulid_monotonic.py`)
  - Deleted `utilities/signal_handler.py` (wrapper to `core/signal_handler.py`)
  - Deleted `utilities/text.py` (699 lines, identical copy of `core/text.py`)
  - Deleted `models/__init__.py` (wrapper to `core/models`)
  - Deleted `types/__init__.py` (wrapper to `core/types`)
  - Moved 3 debug test files to `scripts/debug/`

#### Changed

- **Import Path Updates** - All imports updated to use canonical `core/` locations
  - `good_agent.utilities.event_router` → `good_agent.core.event_router`
  - `good_agent.utilities.ulid_monotonic` → `good_agent.core.ulid_monotonic`
  - `good_agent.utilities.signal_handler` → `good_agent.core.signal_handler`
  - `good_agent.utilities.text` → `good_agent.core.text`
  - `good_agent.models` → `good_agent.core.models`
  - `good_agent.types` → `good_agent.core.types`

#### Added

- **Test Coverage Improvements**
  - Added 22 new tests for `pool.py` (100% coverage)
  - Added 50 new tests for `utilities/` modules:
    - 12 tests for `utilities/printing.py`
    - 15 tests for `utilities/lxml.py`
    - 15 tests for `utilities/retries.py`
    - 8 tests for `utilities/logger.py`
  - All 96 new tests passing (100% pass rate)
  - Total test count increased to 1,375 tests

#### Fixed

- Template system verification (91 tests passing, no duplication found)
- Import consistency across entire codebase

---

## Pre-Refactoring Versions

### [0.2.0] and earlier

See git history for changes prior to the comprehensive Phase 1-6 refactoring initiative.

---

## Breaking Changes Summary

### Phase 2 (Current)
- **None** - All changes are internal reorganization with full backward compatibility maintained

### Phase 1
- **Import Path Changes** - Update imports from `utilities.*` to `core.*`
  - See MIGRATION.md for automated migration script

---

## Migration Notes

For detailed migration instructions, see [MIGRATION.md](MIGRATION.md).

For the complete refactoring plan, see [.spec/refactoring-plan.md](.spec/refactoring-plan.md).
