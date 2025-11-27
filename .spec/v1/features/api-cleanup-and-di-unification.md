# API Cleanup & Dependency Injection Unification

## Overview

This spec addresses inconsistencies introduced during Agent class refactoring and unifies the dependency injection system across tools, modes, and context providers.

## Problems Identified

### 1. Redundant Facade Properties

The Agent class has facade properties that create duplicate/confusing APIs:

```python
# Current state - two ways to do the same thing:
await agent.invoke(tool, **params)           # Direct (preferred)
await agent.tool_calls.invoke(tool, **params)  # Via facade (verbose)

agent.fork()                                  # Direct 
agent.context_manager.fork()                   # Via facade (verbose)
```

**Worst offender**: `agent.events` - Agent inherits from EventRouter, so all event methods exist directly on Agent. The facade adds nothing but indirection:

```python
# Current absurdity:
async def apply(self, *args, **kwargs):
    """Deprecated wrapper delegating to :attr:`events`."""
    return await self.events.apply(*args, **kwargs)  # self.events delegates back to EventRouter!
```

### 2. Fragmented Dependency Injection

Three incompatible DI patterns exist:

| Pattern | Location | Usage |
|---------|----------|-------|
| `fast_depends.Depends` | `tools/tools.py` | Tool functions |
| `ContextValue()` | `template_manager/injection.py` | Context providers |
| Direct parameter passing | `agent/modes.py` | Mode handlers |

### 3. Naming Confusion

- `Context` (in `agent/config/context.py`) is a data store, not an injection helper
- `ModeContext` was invented for modes when existing patterns would suffice
- `AgentContext` appears in spec examples but doesn't exist as a DI helper

### 4. Incorrect Deprecation Direction

`_LEGACY_ATTRIBUTE_NAMES` marks direct Agent methods as deprecated in favor of facade methods - this is backwards. The direct methods ARE the intended API.

---

## Solution

### Phase 1: Remove Facade Properties (Keep Internal Classes)

**Goal**: Single entry point for all Agent functionality via direct methods.

#### 1.1 Remove EventRouter Facade Entirely

Delete `_events_facade` and `AgentEventsFacade`. Since Agent inherits from EventRouter, use inherited methods directly:

```python
# Before
async def apply(self, *args, **kwargs):
    return await self.events.apply(*args, **kwargs)

# After - just delete the override, EventRouter.apply works directly
```

Files to modify:
- `src/good_agent/agent/core.py` - Remove facade property and delegation methods
- `src/good_agent/agent/events.py` - Delete entire file (AgentEventsFacade)

#### 1.2 Remove Public Facade Properties

Remove these properties from Agent:
- `tool_calls` -> Keep `_tool_executor` internal, methods delegate internally
- `context_manager` -> Keep `_context_manager` internal
- `events` -> Delete entirely (use EventRouter inheritance)

Keep direct Agent methods:
- `agent.invoke()`, `agent.invoke_many()`, `agent.invoke_func()`
- `agent.fork()`, `agent.fork_context()`, `agent.thread_context()`, `agent.copy()`
- `agent.create_task()`, `agent.wait_for_tasks()`
- All EventRouter methods inherited directly

#### 1.3 Remove Attribute Name Lists

Remove or simplify:
- `_PUBLIC_ATTRIBUTE_NAMES` - Just use standard Python visibility (`_` prefix = internal)
- `_LEGACY_ATTRIBUTE_NAMES` - Delete (wrong direction of deprecation)

The Agent class API should be self-documenting via:
- Public methods/properties = public API
- Single underscore prefix = internal
- Docstrings document intended usage

---

### Phase 2: Unified Dependency Injection

**Goal**: Single `Context()` helper that works everywhere.

#### 2.1 Rename Existing Context Class

```python
# Before: src/good_agent/agent/config/context.py
class Context(ConfigStack):
    """Layer local overrides on top of agent config data..."""

# After: 
class AgentContext(ConfigStack):
    """Layer local overrides on top of agent config data..."""
```

Update all imports:
- `agent/core.py`: `from .config import AgentContext`
- `__init__.py`: Export as `AgentContext`

#### 2.2 Create Unified Context() DI Helper

New file: `src/good_agent/injection.py`

```python
"""Unified dependency injection for tools, modes, and context providers."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, TypeVar, overload

from fast_depends import Depends

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.components import AgentComponent

T = TypeVar("T")

# Sentinel for missing values
_MISSING = object()


class _ContextDescriptor:
    """Descriptor that resolves dependencies at call time.
    
    Supports three injection modes:
    1. Type-based: Context() with type hint -> injects Agent or AgentComponent
    2. Named value: Context("key") -> injects from agent.context["key"]  
    3. With default: Context("key", default=X) -> default if key missing
    """
    
    def __init__(
        self,
        name: str | None = None,
        default: Any = _MISSING,
        default_factory: callable | None = None,
    ):
        self.name = name
        self.default = default
        self.default_factory = default_factory
    
    def resolve(self, agent: Agent, param_type: type | None = None) -> Any:
        """Resolve the dependency value."""
        # If name provided, get from agent.context
        if self.name is not None:
            value = agent.context.get(self.name, _MISSING)
            if value is not _MISSING:
                return value
            if self.default is not _MISSING:
                return self.default
            if self.default_factory is not None:
                return self.default_factory()
            raise KeyError(f"Context key '{self.name}' not found")
        
        # Otherwise, resolve by type
        if param_type is None:
            return agent  # Default to Agent if no type hint
        
        # Check if it's Agent
        if param_type.__name__ == "Agent":
            return agent
        
        # Check if it's an AgentComponent subclass
        try:
            from good_agent.components import AgentComponent
            if issubclass(param_type, AgentComponent):
                return agent[param_type]
        except (TypeError, KeyError):
            pass
        
        raise TypeError(f"Cannot inject type: {param_type}")


@overload
def Context() -> Any:
    """Inject based on type annotation (Agent or AgentComponent)."""
    ...

@overload  
def Context(name: str) -> Any:
    """Inject value from agent.context by key name."""
    ...

@overload
def Context(name: str, *, default: T) -> T:
    """Inject from context with default value."""
    ...

@overload
def Context(name: str, *, default_factory: callable) -> Any:
    """Inject from context with default factory."""
    ...

def Context(
    name: str | None = None,
    *,
    default: Any = _MISSING,
    default_factory: callable | None = None,
) -> Any:
    """Universal dependency injection helper.
    
    Usage:
        @tool
        async def my_tool(
            agent: Agent = Context(),           # Inject Agent by type
            model: LanguageModel = Context(),   # Inject component by type
            user_id: str = Context("user_id"),  # Inject from context
            limit: int = Context("limit", default=10),  # With default
        ):
            ...
        
        @agent.modes("research")
        async def research_mode(
            agent: Agent = Context(),
            topic: str = Context("research_topic"),
        ):
            ...
    """
    return _ContextDescriptor(name, default, default_factory)


# Re-export for backwards compatibility during migration
ContextValue = Context  # Alias for existing code
```

#### 2.3 Update Tool Injection

Modify `src/good_agent/tools/tools.py` to recognize `_ContextDescriptor`:

```python
# In Tool.__call__()
for param_name, param in sig.parameters.items():
    if isinstance(param.default, _ContextDescriptor):
        # Get type hint for this parameter
        param_type = hints.get(param_name)
        kwargs[param_name] = param.default.resolve(agent, param_type)
```

#### 2.4 Simplify Mode Handlers

Remove `ModeContext` as a separate class. Mode handlers use standard DI:

```python
# Before - custom ModeContext
@agent.modes('research')
async def research_mode(ctx: ModeContext):
    ctx.add_system_message("Research mode")
    return await ctx.call()

# After - standard DI, Agent access
@agent.modes('research')
async def research_mode(agent: Agent = Context()):
    agent.append("Research mode activated", role="system")
    return await agent.call(__skip_mode_handler__=True)
```

#### 2.5 Mode Scoping Strategy

**Current context managers** (from `thread_context.py`):
- `thread_context`: Message versioning - truncate/restore messages, preserves new messages added
- `fork_context`: Complete isolation - forked agent discarded on exit

**For modes**, we need scoped:
- Config overrides → use `agent.config(...)` context manager
- Tool filtering → use `agent.tools(mode="filter", ...)` context manager
- Context values → use `agent.context(...)` context manager
- System messages → handler responsibility (add/remove explicitly, or use thread_context)

**Design decision**: Mode handlers use existing context managers explicitly rather than magic auto-scoping.

```python
@agent.modes('research')
async def research_mode(
    agent: Agent = Context(),
    depth: str = Context("depth", default="shallow"),  # From mode params
):
    # Handler explicitly manages scoping using existing infrastructure:
    async with agent.config(temperature=0.2):  # Scoped config
        async with agent.tools(mode="filter", filter_fn=lambda n, t: "search" in n):  # Scoped tools
            # System message added here persists (handler's choice)
            agent.append(f"Research mode: {depth} analysis", role="system")
            
            response = await agent.call(__skip_mode_handler__=True)
            return response
```

**Alternative**: If we want automatic system message cleanup, mode entry could use `thread_context`:

```python
# Internal to ModeManager (optional enhancement)
async def _enter_mode(self, mode_name: str, **params):
    # Track message count at entry
    self._mode_entry_message_counts[mode_name] = len(self._agent.messages)
    
    # Scope context values for mode params
    self._agent.context.update({"_mode": mode_name, **params})

async def _exit_mode(self):
    # Optionally: remove system messages added after mode entry
    # Or: leave cleanup to handler (simpler, more explicit)
    pass
```

**Recommendation**: Start with explicit handler-managed scoping. If patterns emerge where auto-scoping would help, add it later.

**Benefits**:
1. No magic - handlers explicitly control what's scoped
2. Leverages existing context managers (`config()`, `tools()`, `thread_context()`)
3. Consistent with how the rest of the Agent API works
4. Mode params accessible via standard `Context()` DI

The `ModeManager` still handles:
- Mode registration (`@agent.modes('name')`)
- Mode lifecycle events (`MODE_ENTERED`, `MODE_EXITED`)
- Scheduled mode switches
- Mode stack tracking (which modes are active)
- Passing mode params to context for DI

---

### Phase 3: Document Context Management

Add clear documentation distinguishing:

| Method | Purpose | State Persistence |
|--------|---------|-------------------|
| `agent.config(...)` | Temporary config overrides | Reverts on exit |
| `agent.context(...)` | Temporary context values | Reverts on exit |  
| `agent.thread_context()` | Isolated execution, results merge back | Messages persist |
| `agent.fork()` | Independent copy | Fully separate |
| `agent.fork_context()` | Isolated execution, results discarded | Nothing persists |

---

## Implementation Checklist

### Phase 1: Facade Cleanup
- [ ] Remove `AgentEventsFacade` class and `_events_facade` property
- [ ] Remove event method delegation - use EventRouter inheritance directly
- [ ] Remove `tool_calls` property (keep `_tool_executor` internal)
- [ ] Remove `context_manager` property (keep `_context_manager` internal)  
- [ ] Remove `events` property entirely
- [ ] Remove `_PUBLIC_ATTRIBUTE_NAMES` and `_LEGACY_ATTRIBUTE_NAMES`
- [ ] Update `__dir__` to use standard visibility conventions
- [ ] Update docstrings to remove facade references
- [ ] Run tests, fix any breaks

### Phase 2: DI Unification
- [ ] Rename `Context` to `AgentContext` in `agent/config/context.py`
- [ ] Update all imports of old `Context` class
- [ ] Create `src/good_agent/injection.py` with unified `Context()` helper
- [ ] Update `tools/tools.py` to recognize `_ContextDescriptor`
- [ ] Update `components/template_manager/injection.py` to use unified helper
- [ ] Simplify mode handlers to use standard DI
- [ ] Deprecate `ModeContext` (keep for backwards compat temporarily)
- [ ] Add `Context` to top-level exports
- [ ] Update existing tools/modes to use new pattern
- [ ] Run tests, fix any breaks

### Phase 3: Documentation
- [ ] Update DESIGN.md with correct DI examples
- [ ] Document context management methods clearly
- [ ] Update AGENTS.md with simplified API
- [ ] Remove facade references from docs/api-reference.md
- [ ] Add examples showing unified DI pattern

---

## Migration Guide

### For Tool Authors

```python
# Before (ContextValue)
from good_agent import ContextValue

@tool
async def my_tool(user_id: str = ContextValue("user_id")):
    ...

# After (Context)
from good_agent import Context

@tool  
async def my_tool(user_id: str = Context("user_id")):
    ...
```

### For Mode Authors

```python
# Before (ModeContext)
@agent.modes('research')
async def research_mode(ctx: ModeContext):
    ctx.add_system_message("Research mode")
    agent = ctx.agent
    return await ctx.call()

# After (direct Agent injection)
@agent.modes('research')
async def research_mode(agent: Agent = Context()):
    agent.append("Research mode", role="system")
    return await agent.call(__skip_mode_handler__=True)
```

### For Facade Users

```python
# Before (facade methods)
await agent.tool_calls.invoke(tool)
agent.context_manager.fork()
await agent.events.apply("event")

# After (direct methods)
await agent.invoke(tool)
agent.fork()
await agent.apply("event")  # Or just agent.do() for fire-and-forget
```

---

## Open Questions

1. ~~**Mode state scope**: Should mode-specific state use `agent.context` scoping or maintain separate `ModeStack` state?~~
   - **RESOLVED**: Use `thread_context` infrastructure for automatic scoping. Mode entry wraps in thread_context, so system messages/config/tools are scoped but conversation persists.

2. **Backwards compatibility period**: How long to keep deprecated patterns?
   - Recommendation: One minor version with deprecation warnings, remove in next minor

3. ~~**`tasks` property**: Keep `agent.tasks` or use direct methods?~~
   - **RESOLVED**: Keep - task management is complex enough to warrant grouping

4. ~~**`versioning` property**: Keep `agent.versioning` or flatten?~~
   - **RESOLVED**: Keep - versioning is a distinct subsystem

5. ~~**`modes` property**: Keep `agent.modes` for registration decorator?~~
   - **RESOLVED**: Keep - `@agent.modes('name')` is clean syntax for registration

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mode scoping | Explicit (handler-managed) | No magic; handlers use existing `config()`, `tools()`, `thread_context()` |
| Keep `tasks` | Yes | Distinct subsystem, complex enough for grouping |
| Keep `versioning` | Yes | Distinct subsystem |
| Keep `modes` | Yes | Clean decorator syntax `@agent.modes('name')` |
| Remove `tool_calls` | Yes | Direct `agent.invoke()` is cleaner |
| Remove `events` | Yes | Agent inherits EventRouter directly |
| Remove `context_manager` | Yes | Direct `agent.fork()` etc. is cleaner |
| Remove `ModeContext` | Yes | Handlers get `Agent` via DI, use existing context managers |
| Keep `ModeStack` | Minimal | Only for tracking which modes are active, not for state |
