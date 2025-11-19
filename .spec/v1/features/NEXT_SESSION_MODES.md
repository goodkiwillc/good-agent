# Agent Modes - Next Development Session

## Context: What's Been Completed

**Phase 1 (MVP)** is complete and tested:
- ✅ Core `ModeManager`, `ModeContext`, `ModeStack` classes implemented in `src/good_agent/agent/modes.py`
- ✅ Agent integration: `agent.modes`, `agent.current_mode`, `agent.mode_stack`, `agent.in_mode()`
- ✅ Decorator registration: `@agent.modes('name')` 
- ✅ Context manager entry: `async with agent.modes['name']:`
- ✅ Scoped state with inheritance and shadowing working
- ✅ Events: `MODE_ENTERED`, `MODE_EXITED` emitting correctly
- ✅ 11 unit tests passing in `tests/test_modes.py`
- ✅ Exports in all `__init__.py` files
- ✅ Basic example in `examples/modes/basic_modes.py`

## Next Priority: Phase 3 - Mode Transitions & Self-Switching

### Objective
Enable agents to switch modes programmatically and allow agents to self-direct mode changes via tool calls.

### Tasks

#### 1. Implement Mode Handler Execution During `agent.call()`
**Current state**: Mode handlers are registered but never executed during LLM calls.

**Required changes** to `src/good_agent/agent/core.py`:

```python
# In Agent.call() or Agent._llm_call(), before calling LLM:
async def call(self, *content_parts, **kwargs):
    # Check if in a mode
    if self.current_mode:
        mode_handler = self._mode_manager._registry[self.current_mode].handler
        
        # Create ModeContext with current state
        ctx = ModeContext(
            agent=self,
            mode_name=self.current_mode,
            mode_stack=self.mode_stack.copy(),
            state=self._mode_manager.get_all_state(),
        )
        
        # Execute mode handler (may modify context, add messages, etc.)
        result = await mode_handler(ctx)
        
        # Handle mode transitions if handler returned one
        if isinstance(result, ModeTransition):
            await self._handle_mode_transition(result)
            
    # Continue with normal LLM call
    return await self._llm_call(*content_parts, **kwargs)
```

**Note**: The mode handler should execute **before** the LLM call to allow it to add context, modify tools, etc.

#### 2. Implement `ModeTransition` Return Values
**File**: `src/good_agent/agent/modes.py`

Add support for mode handlers to return transition instructions:

```python
class ModeTransition:
    """Return value from mode handler to request a mode transition."""
    type: Literal["switch", "exit", "push"]
    target_mode: str | None = None
    
class ModeContext:
    def switch_mode(self, mode_name: str) -> ModeTransition:
        """Request switch to a different mode."""
        return ModeTransition(type="switch", target_mode=mode_name)
    
    def exit_mode(self) -> ModeTransition:
        """Request exit from current mode."""
        return ModeTransition(type="exit")
```

#### 3. Implement Scheduled Mode Switching (Tool-Based)
**Current**: Modes can only be entered via context managers or direct calls.  
**Goal**: Allow tools to schedule mode switches that happen before the next `agent.call()`.

**Add to `ModeManager`**:
```python
class ModeManager:
    def __init__(self, agent):
        # ... existing code ...
        self._pending_mode_switch: str | None = None
        self._pending_mode_exit: bool = False
    
    def schedule_mode_switch(self, mode_name: str) -> None:
        """Schedule a mode switch for next call."""
        self._pending_mode_switch = mode_name
    
    def schedule_mode_exit(self) -> None:
        """Schedule mode exit for next call."""
        self._pending_mode_exit = True
```

**Add to `Agent.call()`**:
```python
async def call(self, ...):
    # At the start, check for pending mode switches
    if self._mode_manager._pending_mode_switch:
        mode = self._mode_manager._pending_mode_switch
        self._mode_manager._pending_mode_switch = None
        await self._mode_manager.enter_mode(mode)
    
    if self._mode_manager._pending_mode_exit:
        self._mode_manager._pending_mode_exit = False
        await self._mode_manager.exit_mode()
    
    # ... rest of call logic
```

#### 4. Create Mode-Switching Tools
**File**: Create `examples/modes/mode_switching_tools.py`

```python
from good_agent import Agent, tool
from good_agent.agent.config import Context

@tool
async def enter_research_mode(agent: Agent = Context()) -> str:
    """Switch to research mode for deep investigation."""
    agent.modes.schedule_mode_switch('research')
    return "Will enter research mode after this response."

@tool  
async def exit_current_mode(agent: Agent = Context()) -> str:
    """Exit the current mode."""
    if agent.current_mode:
        agent.modes.schedule_mode_exit()
        return f"Will exit {agent.current_mode} mode."
    return "Not in any mode."
```

#### 5. Testing Requirements

**Add to `tests/test_modes.py`**:
- `test_mode_handler_execution()` - Verify handler runs during call
- `test_mode_transition_switch()` - Test switching between modes from handler
- `test_mode_transition_exit()` - Test exiting from handler
- `test_scheduled_mode_switch()` - Test tool-based mode switching
- `test_scheduled_mode_exit()` - Test tool-based mode exit
- `test_mode_switch_before_call()` - Verify switch happens before LLM call

**Integration test** with actual LLM (optional, can be VCR-based):
- Agent calls tool that schedules mode switch
- Next call uses mode-specific behavior
- System messages properly injected

#### 6. Documentation Updates

**Update**: `examples/modes/basic_modes.py`
- Add section demonstrating handler execution
- Show mode transitions from within handlers

**Create**: `examples/modes/self_switching.py`
- Full example of agent deciding to switch modes
- Demonstrate tool-based mode switching
- Show mode parameter passing

### Acceptance Criteria

- [ ] Mode handlers execute automatically when in a mode during `agent.call()`
- [ ] Mode handlers can return `ModeTransition` to switch/exit modes
- [ ] Tools can schedule mode switches via `agent.modes.schedule_mode_switch()`
- [ ] Scheduled switches apply before next LLM call, not during current one
- [ ] All new functionality has unit tests (90%+ coverage)
- [ ] At least one integration test with real mode switching
- [ ] Examples demonstrate all new capabilities
- [ ] No regression in existing 277 tests
- [ ] All code formatted (ruff) and type-checked (mypy)

### Key Design Decisions to Maintain

1. **Timing**: Mode switches scheduled by tools happen **before** the next call, not immediately
2. **Handler execution**: Mode handlers run **before** LLM call to allow context modification
3. **State persistence**: Mode state persists across calls within the same mode context
4. **Idempotency**: Entering a mode you're already in is a no-op
5. **Cleanup**: Mode exits always clean up properly, even on exceptions

### Files You'll Modify

- `src/good_agent/agent/modes.py` - Add ModeTransition, scheduled switching
- `src/good_agent/agent/core.py` - Integrate handler execution in call()
- `tests/test_modes.py` - Add 6+ new tests
- `examples/modes/basic_modes.py` - Update with new features
- `examples/modes/self_switching.py` - New example (create)
- `.spec/v1/features/agent-modes.md` - Update progress checkboxes

### Testing Strategy

1. **Unit tests first**: Test each component in isolation
2. **Integration tests**: Test full flow with mode switching
3. **Mock LLM calls**: Use `agent.mock` for most tests to avoid API costs
4. **VCR cassettes**: For integration tests that need realistic LLM responses
5. **Edge cases**: Test switching to non-existent modes, recursive switches, etc.

### Common Pitfalls to Avoid

- ❌ Don't execute mode handlers **during** tool execution - this causes recursion
- ❌ Don't modify `agent.messages` directly in handlers without emitting events
- ❌ Don't forget to clear `_pending_mode_switch` after processing it
- ❌ Don't allow mode switches while another switch is pending
- ❌ Don't skip cleanup if mode handler raises an exception

### Reference Files to Study

- `src/good_agent/agent/core.py:1443-1500` - Current `call()` implementation
- `src/good_agent/agent/tools.py` - Tool execution patterns
- `src/good_agent/agent/config/context.py` - Context injection examples
- `tests/unit/agent/test_agent_invoke.py` - Tool invocation test patterns
- `examples/tools/basic_tool.py` - Tool creation examples

### Quick Start Command

```bash
cd /Users/chrisgoddard/Code/goodkiwi/projects/good-agent

# Run existing mode tests to verify baseline
uv run pytest tests/test_modes.py -v

# Start with handler execution in Agent.call()
# 1. Add handler execution logic to Agent.call()
# 2. Write test_mode_handler_execution() 
# 3. Run test to verify: uv run pytest tests/test_modes.py::test_mode_handler_execution -v
# 4. Continue with remaining tasks...

# Final verification
uv run pytest tests/ -x  # All tests should pass
uv run python examples/modes/self_switching.py  # Example should work
```

### Questions to Resolve

1. Should mode handlers be async-only or support sync handlers too?
2. Should we allow multiple pending mode switches (queue) or just one?
3. How to handle circular mode transitions (A → B → A)?
4. Should mode parameters be mutable during the mode or frozen at entry?
5. Event emission: should we emit events for scheduled switches or only on actual switch?

**Recommended answers** (from spec):
1. Async-only for consistency with Agent API
2. Just one - raise error if trying to schedule while one is pending
3. Allow but document - user's responsibility to avoid infinite loops
4. Frozen at entry - mode state separate from mode parameters
5. Only on actual switch - scheduled switches can be cancelled

---

## Future Phases (Not Yet Started)

### Phase 4: Dependency Injection (After Phase 3)
- Integrate FastDepends for mode handler parameters
- Support `param = Context('param_name')` injection
- Parameter validation with Pydantic

### Phase 5: Context Transformations (After Phase 4)
- `ctx.pipeline(*transforms)` for transformation chains
- `ctx.temporary_tools(tools)` for mode-specific tools
- `ctx.filter_tools(names)` to limit tool availability

### Phase 6: Enhanced Observability (After Phase 5)
- Transcript recording with mode transitions
- Replay transcripts with automatic mode switching
- Mode analytics and metrics

### Phase 7: Advanced Integration (After Phase 6)
- Stateful resources within modes
- Multi-agent mode coordination
- Commands that enter/exit modes

---

## Contact & References

- **Spec**: `.spec/v1/features/agent-modes.md` (comprehensive 500+ line spec)
- **Progress**: Phase 1 complete, Phase 2 complete (state scoping), Phase 3 is next
- **Slack**: #good-agent-dev (for questions)
- **Original design doc**: DESIGN.md has architectural context

Good luck! The foundation is solid - Phase 3 builds naturally on what's there. 🚀
