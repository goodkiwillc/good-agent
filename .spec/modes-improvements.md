# Agent Modes v2.1 Improvements Spec

## Overview

This spec captures improvements to the Agent Modes feature based on testing, documentation review, and design discussions. The core insight is that modes are **stateful configurations** that persist across calls - they are composable, isolated pipelines that temporarily modify agent behavior.

---

## 1. Remove Simple Handler Pattern (Breaking Change)

### Problem

The current implementation has two handler types with different execution semantics:

| Handler Type | At Mode Entry | On Every `call()` | At Mode Exit |
|--------------|---------------|-------------------|--------------|
| Generator | Setup (before yield) | Nothing | Cleanup (after yield) |
| Simple | Nothing | **Full handler runs** | Nothing |

This was kept "for backward compatibility" but represents an incorrect mental model. Simple handlers running on every `call()` contradicts the concept of modes as persistent states.

### Code Location

```python
# modes.py:900-910
if handler_type == HandlerType.SIMPLE:
    # Simple handlers are NOT run at entry - they run via execute_handler()
    # during the execute() loop for backward compatibility
    entry.active_generator = None
    return
```

```python
# modes.py:860-890
async def execute_handler(self, mode_name: str) -> Any:
    # Skip generator handlers - they run at mode entry/exit
    if handler_type == HandlerType.GENERATOR:
        return None
    # Simple handlers run HERE, every call  <-- THIS IS WRONG
    return await handler(self._agent)
```

### Solution

**Remove the `HandlerType` distinction entirely.** All mode handlers are generators:

```python
@agent.modes("research")
async def research_mode(agent: Agent):
    # SETUP - runs once on mode entry
    agent.prompt.append("Research mode instructions...")
    
    yield agent  # Required - mode is now active
    
    # CLEANUP - runs once on mode exit (optional code after yield)
```

**Changes required:**
1. Remove `HandlerType` enum and `_detect_handler_type()` function
2. Remove `execute_handler()` method (only used for simple handlers)
3. Remove `_run_active_mode_handlers()` from execute loop in core.py
4. All handlers MUST yield - no yield = error
5. Update all tests that use simple handlers
6. Update all examples to use generator pattern

### Migration

Handlers without `yield` will raise an error:
```
ModeHandlerError: Mode handler 'research' must yield. 
All mode handlers are async generators that yield control after setup.
```

---

## 2. Parameterized Mode Entry

### Problem

Currently, passing parameters to modes requires pre-setting state:
```python
agent.mode.state["topic"] = "quantum"
async with agent.modes["research"]:
    ...
```

### Solution

Support callable mode context managers:
```python
async with agent.modes["research"](topic="quantum", depth=3):
    print(agent.mode.state["topic"])  # "quantum"
```

### Implementation

```python
class ModeContextManager:
    def __init__(self, manager: ModeManager, mode_name: str):
        self._manager = manager
        self._mode_name = mode_name
        self._params: dict[str, Any] = {}
    
    def __call__(self, **params) -> "ModeContextManager":
        """Allow parameterized mode entry."""
        self._params = params
        return self
    
    async def __aenter__(self) -> Agent:
        await self._manager._enter_mode(self._mode_name, **self._params)
        return self._manager._agent
```

Parameters are injected into `agent.mode.state` before handler runs.

---

## 3. Mode-Aware System Prompt

### Problem

The LLM has no awareness of the modes system. It doesn't know:
- What modes are available
- What the current mode is
- How to switch modes
- What each mode does

### Solution

Inject mode awareness into system prompt automatically when modes are registered.

#### A. Base Mode Awareness (always present when modes exist)

```python
# Auto-injected when agent has registered modes
MODES_AWARENESS_PROMPT = """
## Operational Modes

You have access to operational modes that change your capabilities and focus.
Modes are persistent states - once entered, you remain in a mode until explicitly exiting.

Current mode: {current_mode or "none"}
Mode stack: {mode_stack or "[]"}

Available modes:
{available_modes_list}

To switch modes, use the appropriate mode entry tool. Stay in a mode until your task is complete.
"""
```

#### B. Dynamic Mode List

```python
def _render_available_modes(self) -> str:
    """Generate available modes list for system prompt."""
    lines = []
    for name, info in self._registry.items():
        if info.invokable:
            status = "(active)" if self.in_mode(name) else ""
            lines.append(f"- {name}: {info.description} {status}")
    return "\n".join(lines)
```

#### C. Integration Point

Add to `SystemPromptManager.render()`:
```python
def render(self) -> str:
    parts = []
    parts.append(self._base_prompt)
    
    # Auto-inject mode awareness if modes exist
    if self._agent.modes.list_modes():
        parts.append(self._render_modes_section())
    
    # ... rest of rendering
```

---

## 4. Improved Invokable Mode Tools

### Problem

Current generated tools are minimal:
```python
@tool(name="enter_research_mode", description="Enter research mode.")
def mode_switch_tool() -> str:
    manager.schedule_mode_switch(mode_name)
    return f"Will enter {mode_name} mode."  # That's it!
```

Issues:
1. No check if mode is already active
2. No information about mode capabilities
3. Redundant `_mode` suffix in tool name
4. Minimal tool response

### Solution

#### A. Tool Naming

Change default from `enter_{name}_mode` to `enter_{name}`:
```python
# Before
tool_name = tool_name or f"enter_{name}_mode"

# After  
tool_name = tool_name or f"enter_{name}"
```

#### B. Dynamic Tool with State Awareness

```python
def _register_invokable_tool(self, mode_info: ModeInfo) -> None:
    mode_name = mode_info.name
    tool_name = mode_info.tool_name or f"enter_{mode_name}"
    manager = self
    
    @tool(name=tool_name, description=self._build_tool_description(mode_info))
    def mode_switch_tool() -> str:
        # Check if already in this mode
        if manager.in_mode(mode_name):
            return f"Already in {mode_name} mode. No action needed."
        
        # Check if mode is available (not blocked by isolation, etc.)
        if not manager._can_enter_mode(mode_name):
            return f"Cannot enter {mode_name} mode from current context."
        
        manager.schedule_mode_switch(mode_name)
        
        # Rich response with mode details
        return manager._build_mode_entry_response(mode_info)
```

#### C. Rich Tool Response

```python
def _build_mode_entry_response(self, mode_info: ModeInfo) -> str:
    return f"""Entering {mode_info.name} mode.

PURPOSE: {mode_info.description}

GUIDELINES:
{self._get_mode_guidelines(mode_info)}

You are now operating in {mode_info.name} mode. Your responses should align with this mode's purpose.
To exit, use exit_current_mode or switch to another mode."""
```

#### D. Exit Mode Tool (Optional)

Generate an exit tool when modes are invokable:
```python
@tool(name="exit_current_mode", description="Exit the current mode and return to normal operation.")
def exit_mode_tool() -> str:
    if not manager.current_mode:
        return "Not in any mode. No action needed."
    
    mode_name = manager.current_mode
    manager.schedule_mode_exit()
    return f"Exiting {mode_name} mode. Returning to normal operation."
```

---

## 5. Additional Mode Events

### Problem

Only `MODE_ENTERED` and `MODE_EXITED` events exist. The spec planned for more.

### Solution

Add events from original spec:

```python
class AgentEvents(StrEnum):
    # Existing
    MODE_ENTERED = "mode:entered"
    MODE_EXITED = "mode:exited"
    
    # New
    MODE_ENTERING = "mode:entering"      # Before setup runs
    MODE_EXITING = "mode:exiting"        # Before cleanup runs
    MODE_ERROR = "mode:error"            # Exception in handler
    MODE_TRANSITION = "mode:transition"  # Handler requested transition
```

### Event Parameters

```python
# MODE_ENTERING / MODE_ENTERED
{
    "mode_name": str,
    "mode_stack": list[str],
    "parameters": dict[str, Any],
    "timestamp": datetime,
}

# MODE_EXITING / MODE_EXITED
{
    "mode_name": str,
    "mode_stack": list[str],
    "duration": timedelta,
    "exit_behavior": ModeExitBehavior,
}

# MODE_ERROR
{
    "mode_name": str,
    "error": Exception,
    "phase": Literal["setup", "active", "cleanup"],
}

# MODE_TRANSITION
{
    "from_mode": str | None,
    "to_mode": str | None,
    "transition_type": Literal["switch", "push", "exit"],
}
```

### Usage for Automatic Console Logging

```python
# In AgentConsole or via extension
@agent.on(AgentEvents.MODE_ENTERED)
async def _on_mode_entered(ctx):
    agent = ctx.parameters["agent"]
    agent.console.mode_enter(
        ctx.parameters["mode_name"],
        ctx.parameters["mode_stack"]
    )

@agent.on(AgentEvents.MODE_EXITED)
async def _on_mode_exited(ctx):
    agent = ctx.parameters["agent"]
    agent.console.mode_exit(
        ctx.parameters["mode_name"],
        ctx.parameters["mode_stack"]
    )
```

---

## 6. Rich CLI Display Improvements

### Problem

Current display doesn't clearly show mode context, nesting, or tool relationships.

### Design Principles

1. **Mode context should be persistent** - Always visible which mode(s) are active
2. **Nesting should be visual** - Indentation shows mode stack depth
3. **Tool calls should be grouped** - Input/output together, collapsible
4. **Transitions should be prominent** - Clear visual break on mode change

### Visual Design

#### A. Mode Context Header (persistent)
```
╔══════════════════════════════════════════════════════════════════════╗
║ MODE: research > analysis                           [tokens: 1.2K/128K] ║
╚══════════════════════════════════════════════════════════════════════╝
```

#### B. Mode Transition
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ▶ ENTERING: research mode
  │ Purpose: Deep investigation and fact-finding
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### C. Nested Content with Mode Indicators
```
│research│ ┌─ User ────────────────────────────────────────────────────┐
│        │ │ Analyze the market trends for Q4                         │
│        │ └───────────────────────────────────────────────────────────┘
│        │
│        │ ┌─ Assistant ───────────────────────────────────────────────┐
│        │ │ I'll analyze the Q4 market trends...                     │
│        │ └───────────────────────────────────────────────────────────┘
│        │
│        │ ┌─ 🔧 Tool: fetch_market_data ──────────────────────────────┐
│        │ │ → {"quarter": "Q4", "year": 2024}                        │
│        │ │ ← {"growth": 12.5, "sectors": [...]}                     │
│        │ └───────────────────────────────────────────────────────────┘
```

#### D. Color Scheme

| Element | Color | Style |
|---------|-------|-------|
| Mode indicator | cyan | bold |
| Mode transition | cyan | bold + rule |
| User message | white | normal |
| Assistant message | green | normal |
| Tool name | yellow | bold |
| Tool input | yellow | dim |
| Tool output | green | dim |
| Error | red | bold |
| System/info | gray | dim |
| Token usage | blue | dim |

---

## 7. Mode History & Navigation

### Problem

No way to track mode history or navigate back to previous modes.

### Solution

#### A. Mode History Tracking

```python
class ModeAccessor:
    @property
    def history(self) -> list[str]:
        """List of all modes entered this session (chronological)."""
        return self._manager._mode_history
    
    @property
    def previous(self) -> str | None:
        """The mode that was active before current (if any)."""
        if len(self._manager._mode_history) < 2:
            return None
        return self._manager._mode_history[-2]
```

#### B. Return to Previous

```python
def return_to_previous(self) -> ModeTransition:
    """Request returning to the previously active mode."""
    if self.previous is None:
        return ModeTransition(transition_type="exit")
    return ModeTransition(
        transition_type="switch",
        target_mode=self.previous
    )
```

---

## 8. Documentation Updates

### Files to Update

| File | Changes |
|------|---------|
| `docs/features/modes.md` | Remove simple handler docs, add parameterized entry |
| `docs/guides/mode-patterns.md` | Update all examples to generator style |
| `AGENTS.md` | Update quick reference |
| `CHANGELOG.md` | Document breaking change |

### New Documentation

| Topic | Content |
|-------|---------|
| Migration guide | How to convert simple handlers to generators |
| Mode design patterns | Best practices for mode architecture |
| CLI output guide | Understanding the visual display |

---

## Implementation Phases

### Phase 1: Core Handler Fix (Breaking)
- [ ] Remove `HandlerType` enum and detection
- [ ] Remove `execute_handler()` method
- [ ] Remove simple handler execution from `_run_active_mode_handlers()`
- [ ] Require all handlers to yield (error if not)
- [ ] Update all tests
- [ ] Update all examples to generator style

### Phase 2: Parameterized Mode Entry
- [ ] Add `__call__` to `ModeContextManager`
- [ ] Pass parameters to `_enter_mode()`
- [ ] Inject parameters into `agent.mode.state`
- [ ] Add tests for parameterized entry

### Phase 3: Mode-Aware System Prompt
- [ ] Add `_render_modes_section()` to `SystemPromptManager`
- [ ] Auto-inject when modes are registered
- [ ] Include current mode, stack, available modes
- [ ] Make configurable (opt-out)

### Phase 4: Improved Invokable Tools
- [ ] Change default tool name to `enter_{name}`
- [ ] Add "already active" check
- [ ] Implement rich tool responses
- [ ] Add optional `exit_current_mode` tool generation
- [ ] Update tool descriptions dynamically

### Phase 5: Additional Events
- [ ] Add `MODE_ENTERING`, `MODE_EXITING` events
- [ ] Add `MODE_ERROR` event
- [ ] Add `MODE_TRANSITION` event
- [ ] Emit events at appropriate lifecycle points
- [ ] Add event parameter typing

### Phase 6: Rich CLI Display
- [ ] Implement mode context header
- [ ] Add mode transition visual breaks
- [ ] Implement nested indentation
- [ ] Improve tool call display
- [ ] Update color scheme

### Phase 7: Mode History
- [ ] Add `_mode_history` list to `ModeManager`
- [ ] Expose via `agent.mode.history`
- [ ] Add `agent.mode.previous`
- [ ] Add `agent.mode.return_to_previous()`

### Phase 8: Documentation
- [ ] Write migration guide for simple → generator handlers
- [ ] Update all doc files
- [ ] Create CLI visual guide
- [ ] Add CHANGELOG entry

---

## Testing Strategy

### Unit Tests Required

```python
# test_modes_generator_only.py
class TestGeneratorHandlers:
    def test_handler_must_yield()  # Error if no yield
    def test_setup_runs_once_at_entry()
    def test_cleanup_runs_once_at_exit()
    def test_no_execution_during_call()  # Verify old behavior removed

# test_modes_parameterized.py
class TestParameterizedEntry:
    def test_callable_context_manager()
    def test_params_in_mode_state()
    def test_params_override_defaults()

# test_modes_system_prompt.py
class TestModeAwarePrompt:
    def test_modes_section_injected()
    def test_current_mode_shown()
    def test_available_modes_listed()

# test_modes_invokable.py
class TestInvokableTools:
    def test_tool_name_no_suffix()
    def test_already_active_check()
    def test_rich_response()
    def test_exit_tool_generated()
```

### Integration Tests

```python
class TestModeIntegration:
    def test_full_mode_lifecycle()
    def test_nested_modes_display()
    def test_mode_transition_events()
    def test_llm_understands_modes()  # With mock responses
```

---

## Open Questions

1. **Yield requirement**: Should we allow handlers that return early (before yield) for conditional mode entry? Or always require yield?

2. **Mode visibility**: Should modes support visibility levels (e.g., some modes only available when inside another mode)?

3. **Mode timeouts**: Should modes support auto-exit after N calls or N minutes of inactivity?

4. **Mode persistence**: Should mode state survive agent serialization/restart?

5. **Mode conflicts**: Should we support declaring that certain modes are mutually exclusive?

---

## References

- `src/good_agent/agent/modes.py` - Core implementation
- `src/good_agent/agent/core.py` - Agent integration
- `src/good_agent/utilities/console.py` - CLI utilities
- `.spec/v1/spec-modes-v2-complete.md` - Original v2 spec
- `tests/test_modes.py` - Current tests
- `tests/test_modes_generators.py` - Generator tests
