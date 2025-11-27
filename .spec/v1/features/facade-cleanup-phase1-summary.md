# Facade Cleanup - Phase 1 Summary

**Date**: 2024-11-27  
**Status**: Complete  
**Related Spec**: `api-cleanup-and-di-unification.md`

## Overview

Phase 1 of the API cleanup focused on removing redundant facade properties from the Agent class and establishing direct methods as the primary API. This simplifies the public interface while maintaining backwards compatibility through deprecated property accessors.

## Goals Achieved

1. **Removed AgentEventsFacade** - Agent now inherits directly from EventRouter, eliminating the need for a separate facade class
2. **Simplified tool_calls and context_manager access** - These are now deprecated properties with warnings, directing users to direct Agent methods
3. **Removed _PUBLIC_ATTRIBUTE_NAMES** - The explicit attribute list mechanism was removed as it added maintenance burden without clear benefit
4. **Updated all tests** - Migrated 100+ test files to use the new direct API

## Technical Decisions

### 1. Events: Return `self` Instead of Facade

**Decision**: `agent.events` now returns `self` (the Agent instance) since Agent inherits from EventRouter.

**Rationale**: 
- Agent already has all EventRouter methods via inheritance
- `agent.events.apply()` and `agent.apply()` are now equivalent
- No behavior change for existing code, just removes indirection

### 2. Deprecated Properties with Warnings

**Decision**: Keep `tool_calls` and `context_manager` as deprecated properties that emit warnings but still work.

**Rationale**:
- Allows gradual migration for existing codebases
- Clear deprecation path with actionable warnings
- One minor version of deprecation before removal (per spec)

### 3. Direct Methods as Primary API

**Decision**: All common operations should be available directly on Agent:

| Deprecated | New Primary API |
|------------|-----------------|
| `agent.tool_calls.invoke()` | `agent.invoke()` |
| `agent.tool_calls.invoke_func()` | `agent.invoke_func()` |
| `agent.tool_calls.invoke_many()` | `agent.invoke_many()` |
| `agent.tool_calls.record_invocation()` | `agent.add_tool_invocation()` |
| `agent.tool_calls.record_invocations()` | `agent.add_tool_invocations()` |
| `agent.context_manager.fork()` | `agent.fork()` |
| `agent.context_manager.copy()` | `agent.copy()` |
| `agent.context_manager.thread_context()` | `agent.thread_context()` |
| `agent.context_manager.fork_context()` | `agent.fork_context()` |
| `agent.context_manager.context_provider()` | `agent.context_provider()` |
| `Agent.context_providers()` | `ContextManager.context_providers()` |

### 4. Internal vs Public Naming

**Decision**: Internal managers use underscore prefix (`_tool_executor`, `_context_manager`) while public methods use clean names.

**Rationale**:
- Clear separation between implementation details and public API
- Tests needing to mock internals explicitly access `_context_manager` etc.
- Discourages external code from depending on internal structure

## Files Changed

### Deleted
- `src/good_agent/agent/events.py` - AgentEventsFacade class (138 lines)
- `tests/unit/agent/test_events_facade.py` - Tests for deleted facade
- `tests/unit/agent/test_agent_public_api_surface.py` - Tests for removed `_PUBLIC_ATTRIBUTE_NAMES`

### Modified (Core)
- `src/good_agent/agent/core.py`
  - Removed `_PUBLIC_ATTRIBUTE_NAMES` and `_LEGACY_ATTRIBUTE_NAMES` (~98 lines)
  - Changed `events` property to return `self`
  - Added deprecated `tool_calls` and `context_manager` properties with warnings
  - Updated all internal references from `self.context_manager.X` to `self._context_manager.X`
  - Updated docstrings to reference direct methods

- `src/good_agent/agent/__init__.py`
  - Removed `AgentEventsFacade` from exports

- `src/good_agent/agent/thread_context.py`
  - Updated docstrings and internal references

- `src/good_agent/agent/context.py`
  - Updated docstrings to show direct method usage

- `src/good_agent/resources/base.py`
  - Changed `agent.context_manager.thread_context()` to `agent.thread_context()`

### Modified (Tests)
- 100+ test files updated via bulk sed replacement
- Key patterns replaced:
  - `agent.tool_calls.X(` → `agent.X(`
  - `agent.context_manager.X(` → `agent.X(`
  - `agent.record_invocation(` → `agent.add_tool_invocation(`
  - `Agent.context_providers(` → `ContextManager.context_providers(`
- Manual fixes for tests mocking internals (use `agent._context_manager`)

## Deprecation Warnings

The following deprecation warnings are now emitted:

```python
# When accessing agent.tool_calls
DeprecationWarning: agent.tool_calls is deprecated. Use agent.invoke(), 
agent.record_invocation(), or agent.record_invocations() instead.

# When accessing agent.context_manager  
DeprecationWarning: agent.context_manager is deprecated. Use agent.fork(), 
agent.fork_context(), agent.thread_context(), or agent.context_provider() instead.

# When using Agent.context_providers()
DeprecationWarning: Agent.context_providers() is deprecated. Use 
ContextManager.context_providers() for global providers or 
agent.context_provider() for instance-specific providers.
```

## Migration Guide

### For Tool Operations

```python
# Before
result = await agent.tool_calls.invoke(my_tool, param="value")
agent.tool_calls.record_invocation(tool, response, params)

# After  
result = await agent.invoke(my_tool, param="value")
agent.add_tool_invocation(tool, response, params)
```

### For Context Operations

```python
# Before
async with agent.context_manager.thread_context() as ctx:
    ...
forked = agent.context_manager.fork()

# After
async with agent.thread_context() as ctx:
    ...
forked = agent.fork()
```

### For Event Operations

```python
# Before
await agent.events.apply("my:event", data=value)

# After (either works, but direct is preferred)
await agent.apply("my:event", data=value)
```

### For Context Providers

```python
# Before (global)
@Agent.context_providers("my_value")
def provider():
    return 42

# After (global)
from good_agent.agent.context import ContextManager

@ContextManager.context_providers("my_value")
def provider():
    return 42

# Instance-specific (unchanged)
@agent.context_provider("my_value")
def provider():
    return 42
```

## Test Results

- **Unit tests**: 1400 passed
- **Mode tests**: 17 passed
- **No deprecation warnings** from our code when running tests

## Next Steps (Phase 2)

Per `api-cleanup-and-di-unification.md`:

1. **Unified DI** - Create `Context()` helper for dependency injection
2. **Rename Context** - Rename `agent/config/context.py:Context` to `AgentContext`
3. **Simplify Mode Handlers** - Update mode handlers to use standard DI patterns
4. **Documentation** - Document differences between `config()`, `thread_context()`, `fork()`, `fork_context()`

## Breaking Changes

None in this phase. All changes are backwards compatible with deprecation warnings.

Planned breaking changes for next minor version:
- Remove `agent.tool_calls` property
- Remove `agent.context_manager` property
- Remove `Agent.context_providers()` static method
