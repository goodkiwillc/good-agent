# Agent Modes v2 - Complete Specification

## Executive Summary

This spec defines the v2 modes system with:
- **Agent-centric design**: Mode handlers receive `agent: Agent` via DI (eliminating ModeContext)
- **Pipeline semantics**: Modes are async generators that yield control, then run cleanup
- **Unified DI**: Same FastDepends injection as tools
- **Clear stacking behavior**: LIFO cleanup, scoped state inheritance

---

## 1. Mode Execution Model

### 1.1 Conceptual Model

Modes are **async generator functions** that act like **async context managers**:

```python
@agent.modes('research')
async def research_mode(agent: Agent):
    # === SETUP PHASE ===
    # Runs when mode is entered
    agent.system.append("Research mode active.")
    agent.mode.state['started'] = datetime.now()
    
    # === YIELD CONTROL ===
    # Pauses generator, returns control to caller
    # Mode remains "active" - config/state persists
    yield agent
    
    # === CLEANUP PHASE ===
    # Runs when mode exits (always, even on exception)
    duration = datetime.now() - agent.mode.state['started']
    await agent.call(f"Summarize research session ({duration})")
```

### 1.2 Why Async Generators (Not Pure Context Managers)

| Aspect | Context Manager | Async Generator | Our Choice |
|--------|-----------------|-----------------|------------|
| Setup/Cleanup | `__aenter__`/`__aexit__` | Before/after yield | Generator |
| Exception info | Receives exc_type, exc_val, tb | Via try/except around yield | Generator |
| Suppress exceptions | Return True from `__aexit__` | Catch and don't re-raise | Generator |
| Receive values | No | `send()` method | Generator |
| User ergonomics | Requires class or decorator | Natural function syntax | Generator |

**Decision**: Mode handlers are async generators, wrapped by the framework to provide context manager entry semantics (`async with agent.modes['name']`).

### 1.3 Single-Shot vs Cleanup Modes

```python
# SINGLE-SHOT: No cleanup needed, just return
@agent.modes('simple')
async def simple_mode(agent: Agent):
    agent.system.append("Simple mode.")
    # No yield = no cleanup phase, mode exits after setup
    return

# CLEANUP: Need post-processing, use yield
@agent.modes('research')
async def research_mode(agent: Agent):
    agent.system.append("Research mode.")
    yield agent  # Hold control
    await agent.call("Summarize findings")  # Cleanup
```

**Rule**: If you `yield`, cleanup code after yield ALWAYS runs (even on exception). If you `return`, no cleanup.

---

## 2. Mode Stacking Behavior

### 2.1 Stacking via Context Managers

```python
async with agent.modes['outer']:
    # outer setup runs, yields control
    print(agent.mode.stack)  # ['outer']
    
    async with agent.modes['inner']:
        # inner setup runs, yields control
        print(agent.mode.stack)  # ['outer', 'inner']
        print(agent.mode.name)   # 'inner' (current/top)
        
        await agent.call("Do work")  # Both modes active
    
    # inner cleanup runs (LIFO)
    print(agent.mode.stack)  # ['outer']

# outer cleanup runs
print(agent.mode.stack)  # []
```

### 2.2 Cleanup Order (LIFO)

Cleanup ALWAYS runs in reverse order of entry:

```python
# Entry order:  outer -> middle -> inner
# Cleanup order: inner -> middle -> outer

# Even with exceptions:
async with agent.modes['outer']:
    async with agent.modes['inner']:
        raise ValueError("oops")
    # inner cleanup runs FIRST (despite exception)
# outer cleanup runs SECOND
# Exception propagates after all cleanup completes
```

### 2.3 State Inheritance in Stacks

```python
@agent.modes('outer')
async def outer_mode(agent: Agent):
    agent.mode.state['project'] = 'quantum'
    agent.mode.state['depth'] = 'shallow'
    yield agent

@agent.modes('inner')
async def inner_mode(agent: Agent):
    # READ: inherits from outer
    print(agent.mode.state['project'])  # 'quantum'
    
    # WRITE: shadows (doesn't modify outer)
    agent.mode.state['depth'] = 'deep'
    agent.mode.state['inner_only'] = 'data'
    
    yield agent

# Usage
async with agent.modes['outer']:
    print(agent.mode.state['depth'])  # 'shallow'
    
    async with agent.modes['inner']:
        print(agent.mode.state['depth'])  # 'deep' (shadowed)
        print(agent.mode.state['inner_only'])  # 'data'
    
    # After inner exits:
    print(agent.mode.state['depth'])  # 'shallow' (restored)
    print(agent.mode.state.get('inner_only'))  # None (removed)
```

### 2.4 Agent-Invoked Stacking

When agent calls mode-switching tools, modes stack the same way:

```python
# Agent is in 'research' mode
# Agent calls enter_planning_mode tool
# Result: stack = ['research', 'planning']

# Agent calls exit_current_mode tool
# Result: stack = ['research'] (planning cleanup runs)
```

---

## 3. State Isolation

### 3.1 Isolation Levels

```python
@agent.modes('name', isolation='none')      # Default
@agent.modes('name', isolation='thread')    # ThreadContext semantics
@agent.modes('name', isolation='fork')      # ForkContext semantics  
@agent.modes('name', isolation='config')    # Config only, shared messages
```

### 3.2 Isolation Behavior Matrix

| Aspect | `none` | `thread` | `fork` | `config` |
|--------|--------|----------|--------|----------|
| Messages visible | All | All (temp view) | Snapshot at entry | All |
| New messages kept | Yes | Yes | No (isolated) | Yes |
| Config changes | Shared | Shared | Isolated | Isolated |
| Tool changes | Shared | Shared | Isolated | Isolated |
| Mode state | Scoped | Scoped | Isolated | Scoped |

### 3.3 Thread Isolation Details

```python
@agent.modes('summarizer', isolation='thread')
async def summarizer_mode(agent: Agent):
    # Messages are a temporary view
    # Can truncate/modify freely - original preserved
    
    # Truncate to last 5 messages for summarization
    agent.messages.truncate(5)
    
    yield agent
    
    # After yield, new messages added during mode are KEPT
    # Original messages before truncation are RESTORED
    # Result: original messages + new messages from this mode
```

### 3.4 Fork Isolation Details

```python
@agent.modes('exploration', isolation='fork')
async def exploration_mode(agent: Agent):
    # Complete isolation - working on a copy
    # Nothing persists back to parent
    
    await agent.call("Try risky approach")
    await agent.call("This might fail")
    
    # Can store results in mode.state to pass back
    agent.mode.state['findings'] = extract_findings(agent.messages)
    
    yield agent
    
    # Cleanup can read findings, but messages don't persist
```

### 3.5 Isolation with Stacking

**Rule**: Child modes cannot be LESS isolated than parents.

```python
# VALID: More restrictive
@agent.modes('outer', isolation='thread')
async def outer(agent): yield agent

@agent.modes('inner', isolation='fork')  # fork > thread isolation
async def inner(agent): yield agent

# INVALID: Less restrictive (raises error)
@agent.modes('outer', isolation='fork')
async def outer(agent): yield agent

@agent.modes('inner', isolation='none')  # ERROR: can't reduce isolation
async def inner(agent): yield agent
```

---

## 4. Error Handling

### 4.1 Exception in Setup Phase

```python
@agent.modes('failing_setup')
async def failing_setup(agent: Agent):
    raise ValueError("Setup failed")  # Before yield
    yield agent
    print("Cleanup")  # Never runs - no yield reached

# Usage
async with agent.modes['failing_setup']:  # Raises ValueError
    pass  # Never reached
# Mode never entered, no cleanup needed
```

### 4.2 Exception During Yielded Execution

```python
@agent.modes('research')
async def research_mode(agent: Agent):
    agent.mode.state['started'] = True
    yield agent
    # Cleanup ALWAYS runs, even if exception occurred
    print(f"Cleanup, started={agent.mode.state['started']}")

# Usage
try:
    async with agent.modes['research']:
        raise ValueError("Error during execution")
except ValueError:
    pass  # Cleanup already ran before exception propagated
```

### 4.3 Exception in Cleanup Phase

```python
@agent.modes('failing_cleanup')
async def failing_cleanup(agent: Agent):
    yield agent
    raise ValueError("Cleanup failed")

# Usage
async with agent.modes['failing_cleanup']:
    pass  # Executes fine
# Cleanup runs, raises ValueError
# Exception propagates to caller
```

### 4.4 Stacked Exception Handling

```python
async with agent.modes['outer']:
    async with agent.modes['inner']:
        raise ValueError("Inner error")
    # inner cleanup runs (may also raise)
# outer cleanup runs (regardless of inner's exception)
# First exception propagates (inner's ValueError)
# If cleanup raises, it's logged but doesn't suppress original
```

### 4.5 Exception Access in Cleanup

```python
@agent.modes('error_aware')
async def error_aware_mode(agent: Agent):
    try:
        yield agent
    except Exception as e:
        # Can inspect exception that occurred during yield
        agent.mode.state['error'] = str(e)
        # Re-raise to propagate, or suppress by not re-raising
        raise  # Propagate
```

---

## 5. Mode Transitions

### 5.1 Transition from Within Mode Handler

```python
from good_agent.modes import ModeTransition

@agent.modes('intake')
async def intake_mode(agent: Agent):
    agent.system.append("Determine user needs.")
    
    yield agent
    
    # After yielded execution, decide next mode
    if agent.mode.state.get('needs_research'):
        return ModeTransition.switch('research')
    elif agent.mode.state.get('needs_writing'):
        return ModeTransition.switch('writing')
    else:
        return ModeTransition.exit()  # Exit to parent/none
```

### 5.2 ModeTransition Return Values

```python
class ModeTransition:
    @staticmethod
    def switch(mode_name: str, **params) -> ModeTransition:
        """Exit current mode, enter new mode."""
        
    @staticmethod
    def push(mode_name: str, **params) -> ModeTransition:
        """Keep current mode, push new mode on top."""
        
    @staticmethod
    def exit() -> ModeTransition:
        """Exit current mode, return to parent or none."""
        
    @staticmethod
    def stay() -> ModeTransition:
        """Explicitly stay in current mode (default if no return)."""
```

### 5.3 Scheduled Transitions (for Agent-Invoked)

```python
# Inside a tool (not mode handler)
@tool
async def switch_to_research(agent: Agent) -> str:
    # Schedule for next call (not immediate)
    agent.modes.schedule_switch('research', topic='AI')
    return "Will enter research mode."

@tool  
async def exit_mode(agent: Agent) -> str:
    agent.modes.schedule_exit()
    return f"Will exit {agent.mode.name} mode."
```

---

## 6. Mode Parameters

### 6.1 Via Mode State (Recommended)

```python
# Entry with parameters
async with agent.modes['research'](topic='quantum', depth=3):
    ...

# Or programmatically
await agent.modes.enter('research', topic='quantum', depth=3)

# Access in handler
@agent.modes('research')
async def research_mode(agent: Agent):
    topic = agent.mode.state['topic']  # 'quantum'
    depth = agent.mode.state['depth']  # 3
    yield agent
```

### 6.2 Via DI (Alternative)

```python
@agent.modes('research')
async def research_mode(
    agent: Agent,
    topic: str = ContextValue('topic', default='general'),
    depth: int = ContextValue('depth', default=1),
):
    # Parameters injected from agent.context or mode entry params
    yield agent
```

**Recommendation**: Use mode state for mode-specific params, ContextValue for shared context.

---

## 7. System Prompt Scoping

### 7.1 Auto-Restore on Mode Exit

**Decision**: System prompt changes made during a mode ARE auto-restored on mode exit.

```python
@agent.modes('research')
async def research_mode(agent: Agent):
    agent.system.append("Focus on citations.")
    agent.system.sections['mode'] = "RESEARCH MODE"
    yield agent
    # On exit: append and sections auto-restored to pre-mode state

# Usage
print(agent.system.render())  # Original prompt
async with agent.modes['research']:
    print(agent.system.render())  # Original + "Focus on citations." + section
print(agent.system.render())  # Original (restored)
```

### 7.2 Explicit Persistence

```python
@agent.modes('persistent_change')
async def persistent_mode(agent: Agent):
    # Use persist=True to keep changes after mode exit
    agent.system.append("Always be concise.", persist=True)
    yield agent
```

---

## 8. Events

### 8.1 Mode Events

```python
from good_agent.events import AgentEvents

# Existing events (keep)
AgentEvents.MODE_ENTERED   # When mode setup completes (after yield reached)
AgentEvents.MODE_EXITED    # When mode cleanup completes

# New events
AgentEvents.MODE_ENTERING  # Before mode setup starts
AgentEvents.MODE_EXITING   # Before mode cleanup starts
AgentEvents.MODE_ERROR     # When mode raises exception
AgentEvents.MODE_TRANSITION # When mode requests transition
```

### 8.2 Event Parameters

```python
@agent.on(AgentEvents.MODE_ENTERED)
async def on_mode_entered(ctx):
    print(f"Entered: {ctx.parameters['mode_name']}")
    print(f"Stack: {ctx.parameters['mode_stack']}")
    print(f"Params: {ctx.parameters['parameters']}")

@agent.on(AgentEvents.MODE_ERROR)
async def on_mode_error(ctx):
    print(f"Mode {ctx.parameters['mode_name']} error: {ctx.parameters['error']}")
    print(f"Phase: {ctx.parameters['phase']}")  # 'setup', 'execution', 'cleanup'
```

---

## 9. Testing Strategy

### 9.1 Unit Tests Required

```python
# test_mode_accessor.py
class TestModeAccessor:
    def test_name_returns_current_mode()
    def test_stack_returns_full_stack()
    def test_state_inherits_from_outer()
    def test_state_shadows_on_write()
    def test_duration_tracks_time()
    def test_in_mode_checks_full_stack()
    def test_accessor_outside_mode_returns_none_or_raises()

# test_mode_execution.py
class TestModeExecution:
    def test_setup_runs_before_yield()
    def test_cleanup_runs_after_yield()
    def test_cleanup_runs_on_exception()
    def test_single_shot_mode_no_cleanup()
    def test_mode_receives_agent_via_di()
    def test_mode_can_inject_dependencies()
    def test_mode_can_inject_context_values()

# test_mode_stacking.py
class TestModeStacking:
    def test_modes_stack_correctly()
    def test_cleanup_order_is_lifo()
    def test_state_inheritance()
    def test_state_shadowing()
    def test_nested_exception_cleanup()

# test_mode_isolation.py
class TestModeIsolation:
    def test_isolation_none_shares_all()
    def test_isolation_thread_preserves_new_messages()
    def test_isolation_fork_complete_isolation()
    def test_isolation_config_shares_messages()
    def test_cannot_reduce_isolation_in_child()

# test_mode_transitions.py
class TestModeTransitions:
    def test_switch_exits_and_enters()
    def test_push_stacks_mode()
    def test_exit_returns_to_parent()
    def test_scheduled_switch_applies_next_call()

# test_mode_invokable.py
class TestInvokableModes:
    def test_invokable_generates_tool()
    def test_generated_tool_schedules_switch()
    def test_custom_tool_name()
    def test_tool_includes_description()
```

### 9.2 Integration Tests

```python
# test_modes_integration.py
class TestModesIntegration:
    def test_mode_with_real_llm_call()
    def test_mode_with_tool_execution()
    def test_stacked_modes_with_tools()
    def test_agent_self_switches_mode()
    def test_mode_with_structured_output()
    def test_mode_in_multi_agent_pipe()
```

### 9.3 Test Coverage Requirements

- **Minimum 90% coverage** on modes module
- **100% coverage** on ModeAccessor, ModeTransition
- **Edge cases**: empty stack, max stack depth, rapid enter/exit

---

## 10. Documentation Requirements

### 10.1 Files to Update

| File | Changes |
|------|---------|
| `docs/features/modes.md` | Complete rewrite for v2 API |
| `docs/core/agent.md` | Add `agent.mode` and `agent.system` sections |
| `AGENTS.md` | Update mode examples in quick reference |
| `CHANGELOG.md` | Document breaking changes and migration |

### 10.2 New Documentation

| File | Content |
|------|---------|
| `docs/guides/mode-migration.md` | ModeContext → Agent migration guide |
| `docs/guides/mode-patterns.md` | Common patterns and best practices |
| `examples/modes/v2_*.py` | Updated examples for v2 API |

### 10.3 Example Updates Required

All files in `examples/modes/` and `examples/docs/modes_*.py` must be updated to:
- Remove ModeContext imports
- Use `agent: Agent` parameter
- Use `agent.mode.state` instead of `ctx.state`
- Use `agent.system.append()` instead of `ctx.add_system_message()`

---

## 11. Backwards Compatibility

### 11.1 Deprecation Timeline

| Version | Status |
|---------|--------|
| v0.6.0 | ModeContext deprecated, warnings emitted |
| v0.7.0 | ModeContext removed |

### 11.2 Compatibility Shim

```python
# During deprecation period, ModeContext acts as wrapper
class ModeContext:
    """Deprecated. Use agent: Agent parameter instead."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        warnings.warn(
            "ModeContext is deprecated. Use 'agent: Agent' parameter instead.",
            DeprecationWarning,
            stacklevel=2
        )
    
    @property
    def state(self):
        return self.agent.mode.state
    
    def add_system_message(self, content: str):
        warnings.warn("Use agent.system.append() instead", DeprecationWarning)
        self.agent.system.append(content)
    
    async def call(self, *args, **kwargs):
        warnings.warn("Use agent.call() instead", DeprecationWarning)
        return await self.agent.call(*args, **kwargs)
```

### 11.3 Detection and Auto-Migration

```python
# Framework detects old-style handlers and wraps them
def _wrap_legacy_handler(handler):
    sig = inspect.signature(handler)
    if 'ctx' in sig.parameters and sig.parameters['ctx'].annotation == ModeContext:
        # Legacy handler, wrap it
        @functools.wraps(handler)
        async def wrapper(agent: Agent):
            ctx = ModeContext(agent)  # Emits deprecation warning
            async for value in handler(ctx):
                yield value
        return wrapper
    return handler
```

---

## 12. Acceptance Criteria

### Phase 1: Agent-Centric Handlers ✅ COMPLETE (2024-11-27)
- [x] Mode handlers can declare `agent: Agent` parameter
- [x] Agent is injected directly (handler style detection, not FastDepends)
- [x] `agent.mode` accessor works inside handlers (ModeAccessor class)
- [x] `agent.mode` returns None for name/empty stack outside handlers
- [x] ModeContext still works with deprecation warnings
- [x] All existing tests pass (1455 tests, 23 mode tests)

**Implementation Notes:**
- Created `ModeAccessor` class with `name`, `stack`, `state`, `duration`, `in_mode()`, `switch()`, `push()`, `exit()`
- Added `agent.mode` property returning ModeAccessor
- `HandlerStyle` enum and `_detect_handler_style()` for signature detection
- `ModeManager.execute_handler()` dispatches to correct handler style
- Legacy handlers emit deprecation warning with migration guidance
- Exported `ModeAccessor` from `good_agent` and `good_agent.agent`

### Phase 2: System Prompt Manager ✅ COMPLETE (2024-11-27)
- [x] `agent.prompt` property exists (renamed from `agent.system` to avoid collision)
- [x] `append()`, `prepend()`, `sections` work
- [x] `render()` composes final prompt
- [x] Auto-restore on mode exit via snapshot/restore
- [x] `persist=True` option works
- [x] All 29 mode tests pass (6 new SystemPromptManager tests)

**Implementation Notes:**
- Created `SystemPromptManager` class in `src/good_agent/agent/system_prompt.py`
- Property named `agent.prompt` (not `agent.system`) because `agent.system` already exists for filtering system messages
- `PromptSegment` dataclass tracks content and persist flag
- `SectionsView` provides dict-like access to named sections
- `take_snapshot()` called on mode entry, `restore_snapshot()` called on mode exit
- Snapshot keeps track of prepends/appends/sections state
- Persistent items (persist=True) survive mode exit
- Exported from `good_agent` and `good_agent.agent`

### Phase 3: Isolation Modes ✅ COMPLETE (2024-11-27)
- [x] `isolation` parameter on decorator
- [x] `none`, `thread`, `fork`, `config` all work
- [x] Isolation inheritance rules enforced
- [x] State isolation correct for each level
- [x] All 38 mode tests pass (9 new isolation tests)

**Implementation Notes:**
- Added `IsolationLevel` IntEnum with values: NONE (0), CONFIG (1), THREAD (2), FORK (3)
- Added `isolation` parameter to `@agent.modes()` decorator (accepts enum or string)
- Added `ModeStackEntry` dataclass and `IsolationSnapshot` dataclass
- Updated `ModeStack` to track isolation level per mode entry
- `_create_isolation_snapshot()` creates snapshot based on isolation level
- `_restore_from_isolation_snapshot()` restores on mode exit
- Validation: child mode cannot have lower isolation than parent (raises ValueError)
- Thread isolation: keeps new messages, restores original
- Fork isolation: complete restore (discards all changes)
- Config isolation: restores tool state, shares messages
- Exported `IsolationLevel` from `good_agent` and `good_agent.agent`

### Phase 4: Agent-Invoked Modes
- [ ] `invokable=True` generates tool
- [ ] Tool schedules mode switch
- [ ] Custom tool_name works
- [ ] Tool description from docstring

### Phase 5: Standalone Modes
- [ ] `@mode('name')` decorator works outside agent
- [ ] `agent.modes.register(mode_fn)` works
- [ ] `Agent(modes=[...])` constructor works

### Phase 6: Declarative Tool Invocation
- [ ] `agent.invoke(tool_name, **params)` works
- [ ] `agent.invoke(tool_instance, **params)` works
- [ ] Works inside mode handlers

---

## 13. Implementation Notes

### 13.1 Mode Handler Execution Flow

```
1. agent.modes['name'] accessed
   └─> Returns ModeContextManager

2. async with ModeContextManager:
   └─> __aenter__ called
       ├─> Push mode onto stack
       ├─> Create generator from handler
       ├─> Inject agent via FastDepends
       ├─> Run generator until first yield
       ├─> Emit MODE_ENTERED event
       └─> Return agent to caller

3. Code runs inside `async with` block
   └─> Mode is active, config/state persists

4. Exit `async with` block (normal or exception)
   └─> __aexit__ called
       ├─> Emit MODE_EXITING event
       ├─> Resume generator (send exception if any)
       ├─> Run cleanup code after yield
       ├─> Pop mode from stack
       ├─> Restore system prompt
       ├─> Emit MODE_EXITED event
       └─> Propagate exception if any
```

### 13.2 Key Implementation Classes

```python
# New/Modified
class ModeAccessor         # agent.mode property
class SystemPromptManager  # agent.system property
class ModeHandlerWrapper   # Wraps async generator for context manager

# Modified
class ModeManager          # Add DI support, isolation handling
class Agent                # Add mode, system properties

# Deprecated
class ModeContext          # Compatibility shim only
```
