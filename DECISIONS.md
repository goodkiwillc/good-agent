# Architectural Decisions

This document tracks major architectural decisions made during the good-agent library refactoring.

## Table of Contents

- [Phase 3: Event Router Analysis](#phase-3-event-router-analysis)
- [Phase 2: Package Restructuring](#phase-2-package-restructuring)
- [Phase 1: Code Duplication](#phase-1-code-duplication)

---

## Phase 3: Event Router Analysis

**Date**: 2025-11-14
**Status**: Analysis Complete, Decision Pending
**Decision Maker**: User review required

### Context

The event router (`core/event_router.py`, 2,035 lines) is a central component providing publish-subscribe event handling with advanced features. During Phase 3 planning, concerns were raised about:

1. **Complexity**: 2,035 lines, 11 classes, 36 methods
2. **Potential Race Conditions**: Threading + queue usage without explicit locks
3. **Over-engineering**: Many advanced features that may not be heavily used

### Analysis Findings

#### File Structure

```
core/event_router.py (2,035 lines)
├── Protocols (3 classes)
│   ├── EventHandlerMethod
│   ├── EventHandler
│   └── PredicateHandler
├── Core Classes (8 classes)
│   ├── ApplyInterrupt (Exception)
│   ├── EventContext (Generic event flow)
│   ├── HandlerRegistration (Handler metadata)
│   ├── LifecyclePhase (Enum for phases)
│   ├── SyncRequest (Sync coordination)
│   ├── EventRouter (Main router, 36 methods, 10 async)
│   ├── emit (Decorator/context manager)
│   └── TypedApply (Typed event application)
└── Module Functions (3)
    ├── on (Decorator)
    ├── emit_event (Event emission)
    └── typed_on (Typed decorator)
```

#### Usage Analysis

| Feature | Occurrences in Codebase | Assessment |
|---------|-------------------------|------------|
| **Priority system** | 133 uses | ✅ Heavily used |
| **@on decorator** | 51 uses | ✅ Core feature |
| **.on() method** | 149 uses | ✅ Heavily used |
| **.emit()/.do() calls** | 43 uses | ✅ Moderate use |
| **Predicates** | 50 uses | ⚠️ Moderate use |
| **Lifecycle phases** | 72 uses | ⚠️ Moderate use |

#### Key Subclasses

The event router is foundational to the architecture:

- **Agent** (agent/core.py) - Main orchestrator class
- **AgentComponent** (components/component.py) - Component base class
- **TypedEventHandlersMixin** (events/decorators.py) - Type-safe events
- **GracefulShutdownMixin** (signal_handler.py) - Shutdown handling

#### Complexity Indicators

```python
Threading usage:       5 occurrences
Queue usage:          4 occurrences
Explicit locks:       0 occurrences  ⚠️ Potential race condition risk
contextvars usage:    9 occurrences
```

**Concern**: Threading and queue usage without explicit locks suggests potential for race conditions in concurrent scenarios.

#### Race Condition Risks

Areas of potential concern:

1. **Handler Registration During Execution**
   - If handlers are registered while events are being emitted
   - No visible locking around handler list modifications

2. **Context Variable Propagation**
   - Heavy use of `contextvars` (9 occurrences)
   - Async context switching could cause state leakage

3. **Queue-based Synchronization**
   - Uses queues for sync (4 occurrences)
   - No explicit locks for queue operations (relies on queue's thread safety)

4. **Concurrent Event Emission**
   - Multiple async tasks emitting events simultaneously
   - Handler execution order may not be deterministic

### Options Analysis

#### Option A: Simplify Event Router

**Approach**: Remove rarely-used features, fix race conditions, reduce to ~800-1000 lines

**Pros:**
- Clearer, more maintainable code
- Easier to reason about thread safety
- Reduced cognitive load
- Better performance (less overhead)

**Cons:**
- Breaking changes for extensions using advanced features
- May need migration guide for:
  - Lifecycle phases (72 uses)
  - Predicates (50 uses)
  - Complex priority schemes
- Risk of removing features currently in use

**Estimated Impact:**
- Breaking: HIGH (would require API changes)
- Effort: 2-3 weeks
- Risk: MEDIUM-HIGH

**What to Remove:**
- Lifecycle phases (can use priority instead)
- Predicate system (can filter in handlers)
- emit context manager syntax (keep decorator only)
- TypedApply complexity

**What to Keep:**
- Core @on decorator
- Priority system (heavily used)
- .emit()/.do() methods
- Basic async/sync support
- EventContext

#### Option B: Reorganize Event Router

**Approach**: Split into modules, fix race conditions, improve documentation

**Structure:**
```
core/event_router/
├── __init__.py (public API exports)
├── core.py (300 lines) - Basic EventRouter, @on, emit
├── context.py (200 lines) - EventContext, flow control
├── decorators.py (200 lines) - @on, @typed_on
├── advanced.py (400 lines) - Lifecycle, predicates, complex features
├── protocols.py (100 lines) - Protocols and types
└── sync.py (200 lines) - Thread safety, queue handling
```

**Pros:**
- Backward compatible (no breaking changes)
- Better organization and discoverability
- Easier to understand each piece
- Can document thread safety per module
- Can add proper locking in sync.py

**Cons:**
- Complexity still exists, just reorganized
- Race conditions still possible if not carefully fixed
- More files to maintain
- Doesn't address over-engineering concerns

**Estimated Impact:**
- Breaking: NONE (backward compatible)
- Effort: 1-2 weeks
- Risk: LOW-MEDIUM

**What to Do:**
- Add explicit locking in critical sections
- Document thread-safety guarantees
- Add tests for concurrent scenarios
- Create sync.py with proper synchronization primitives
- Split advanced features into advanced.py

#### Option C: Defer Event Router Changes

**Approach**: Fix only critical race conditions, add documentation and warnings, plan deeper refactor for v1.0

**Pros:**
- Lowest immediate risk
- Allows time to gather more user feedback
- Focus resources on other priorities
- Can plan more comprehensive solution for v1.0

**Cons:**
- Technical debt accumulates
- Race conditions may still occur
- Users may build on features we want to remove
- Missed opportunity to simplify now

**Estimated Impact:**
- Breaking: NONE
- Effort: 1 week (minimal fixes + docs)
- Risk: LOW

**What to Do:**
- Add comprehensive docstrings explaining thread safety
- Add warnings for known race condition scenarios
- Create tests demonstrating thread-safe usage
- Document all features and their usage
- Plan for v1.0 refactor

### Recommendation

**Recommended Approach: Option B (Reorganize) + Minimal Fixes**

**Rationale:**

1. **Backward Compatibility**: The event router is too foundational to break (Agent, AgentComponent, etc. all depend on it)

2. **Usage Justifies Complexity**:
   - Priority: 133 uses
   - @on decorator: 51 uses
   - .on() method: 149 uses
   - Even "advanced" features have 50-72 uses

3. **Reorganization Benefits**:
   - Easier to understand and maintain
   - Can add proper locking per module
   - Better testing isolation
   - Clearer documentation

4. **Pragmatic**:
   - Fixes known issues without breaking changes
   - Improves code quality
   - Defers bigger decisions to v1.0 when we have more usage data

**Implementation Plan:**

**Week 6, Days 1-3:**
1. Create `core/event_router/` package structure
2. Split current file into 6 modules
3. Add explicit locking in sync.py
4. Maintain 100% backward compatibility

**Week 6, Days 4-5:**
1. Add comprehensive thread-safety tests
2. Document each module's guarantees
3. Add race condition warnings where needed
4. Update all imports to use new structure (via __init__.py re-exports)

**Week 7:**
1. Review and test thoroughly
2. Update documentation
3. Get user approval before merge

### Thread Safety Fixes Needed

Specific areas requiring locking:

```python
# In sync.py - Add proper locking for handler registration
class EventRouter:
    def __init__(self):
        self._handlers_lock = threading.RLock()  # Add this

    def on(self, event_name, handler, priority=0):
        with self._handlers_lock:  # Protect registration
            # ... existing logic

    def _emit_internal(self, event_name, *args, **kwargs):
        with self._handlers_lock:  # Protect iteration
            handlers = list(self._handlers[event_name])
        # Execute handlers outside lock to avoid deadlock
        for handler in handlers:
            handler(*args, **kwargs)
```

### Open Questions for User

1. **Do you agree with Option B (Reorganize + Minimal Fixes)?**
   - Or prefer Option A (Simplify) or C (Defer)?

2. **Are there specific race condition scenarios you've encountered?**
   - This would help prioritize which fixes are critical

3. **Any features you know are unused and can be deprecated?**
   - Even if we don't remove them now, we can mark for future removal

4. **Timeline preferences?**
   - Is 2 weeks for reorganization acceptable?
   - Or should we do minimal fixes (Option C) for now?

---

## Phase 2: Package Restructuring

**Date**: 2025-11-11 to 2025-11-14
**Status**: ✅ Complete
**Decision**: Accept pragmatic file sizes, prioritize backward compatibility

### Decisions Made

#### Decision 2.1: Accept agent/core.py Size

**Context**: Original target was <600 lines for agent/core.py

**Decision**: Accept 2,684 lines as reasonable

**Rationale:**
- Contains 1,421 lines of actual code (excluding docs/comments/blanks)
- Has 98 methods with extensive orchestration logic
- Manager extraction achieved primary goal of reducing complexity
- Further reduction would require breaking public API or excessive forwarding

**Alternatives Considered:**
- Aggressive docstring removal: Would lose valuable context
- More manager extraction: Would create excessive fragmentation
- Moving methods to managers: Many are intrinsic to Agent orchestration

**Result**: Phase 2 goals achieved through manager extraction and package splits

#### Decision 2.2: Full Backward Compatibility

**Context**: Could make breaking changes in pre-1.0 library

**Decision**: Maintain 100% backward compatibility for Phase 2

**Rationale:**
- Event router is too foundational to break
- Users may have existing code depending on current API
- Re-exports via __init__.py files are cheap
- Allows gradual adoption of new structure

**Alternatives Considered:**
- Breaking changes with deprecation warnings: Too risky for foundation
- Parallel APIs: Confusing and increases maintenance burden

**Result**: Zero breaking changes, full migration guide provided

---

## Phase 1: Code Duplication

**Date**: 2025-11-11
**Status**: ✅ Complete
**Decision**: Delete wrapper modules, use canonical core/ implementations

### Decisions Made

#### Decision 1.1: Canonical Module Location

**Context**: Duplicate code in utilities/ wrapping core/

**Decision**: Keep core/ as canonical, delete utilities/ wrappers

**Rationale:**
- core/ is better semantic fit for foundational modules
- Minimal disruption (just import updates)
- Eliminates confusion about which to use

**Alternatives Considered:**
- Keep utilities/: Worse semantic fit, less clear purpose
- Keep both: Confusing, maintenance burden

**Result**: All imports updated, zero wrapper modules remain

---

## Decision Log Template

For future decisions, use this template:

```markdown
## [Phase]: [Decision Title]

**Date**: YYYY-MM-DD
**Status**: [Proposed | Approved | Rejected | Deferred]
**Decision Maker**: [Name/Role]

### Context
[Why this decision is needed]

### Decision
[What was decided]

### Rationale
[Why this decision was made]

### Alternatives Considered
[Other options and why they weren't chosen]

### Consequences
[Impact of this decision]

### Open Questions
[Remaining uncertainties]
```
