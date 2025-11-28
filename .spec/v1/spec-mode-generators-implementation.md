# Mode Generators Implementation Plan

## Executive Summary

Implement async generator support for mode handlers, enabling setup/cleanup lifecycle semantics where:
- **Setup phase**: Runs on mode entry, before yield
- **Active phase**: Handler paused, main execute() loop runs with mode config
- **Cleanup phase**: Runs on mode exit, after yield (guaranteed, even on exception)

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ COMPLETE | Core generator support (handler detection, setup/cleanup lifecycle) |
| Phase 2 | ✅ COMPLETE | Exception handling (athrow, cleanup guarantees) |
| Phase 3 | ✅ COMPLETE | Exit behavior (ModeExitBehavior enum, set_exit_behavior) |
| Phase 4 | 🔲 PENDING | Execute loop integration |
| Phase 5 | 🔲 PENDING | Documentation & examples update |

### Phase 1 Completion Notes (2024-11-27)
- Added `HandlerType` enum (`SIMPLE`, `GENERATOR`) and `_detect_handler_type()` function
- Added `ActiveModeGenerator` dataclass to track paused generators
- Updated `ModeStackEntry` with `active_generator` and `entered_at` fields
- Implemented `_run_handler_setup()` - runs generator until first yield at mode entry
- Implemented `_run_handler_cleanup()` - resumes generator after yield at mode exit
- Updated `_enter_mode()` with setup phase and error recovery
- Updated `_exit_mode()` with cleanup phase in try/finally block
- 14 new tests in `tests/test_modes_generators.py`

### Phase 2 Completion Notes (2024-11-27)
- Updated `ModeContextManager.__aexit__` to detect exceptions and pass to cleanup
- Implemented `_exit_mode_with_exception()` using `gen.athrow(exception)`
- Generators can catch, suppress, re-raise, or transform exceptions
- Cleanup guaranteed via try/finally blocks even if cleanup raises
- 6 new exception handling tests

### Phase 3 Completion Notes (2024-11-27)
- Added `ModeExitBehavior` enum (CONTINUE, STOP, AUTO)
- Added `agent.mode.set_exit_behavior()` method for handlers
- Updated `_run_handler_cleanup()` to read exit behavior from mode state
- Updated `_exit_mode()` to return `ModeExitBehavior`
- Exported `ModeExitBehavior` from `good_agent` module
- 4 new exit behavior tests
- **Note**: Async generators don't support return values, so handlers set behavior via `agent.mode.set_exit_behavior()` or `agent.mode.state["_exit_behavior"]`

### Test Coverage
- Total tests: 76 (52 original mode tests + 24 generator tests)
- All tests passing

---

## 1. Current State Analysis

### What Exists
- `ModeManager` with mode registration, stack, state scoping
- `ModeContextManager` for `async with agent.modes["name"]` syntax
- `execute_handler()` that simply `await`s the handler
- Handler detection for legacy `ModeContext` vs new `Agent` parameter

### What's Missing
- No async generator detection
- No generator lifecycle management (start, pause, resume)
- No cleanup guarantee on exceptions
- Mode handler runs on every `call()` instead of once at entry/exit

---

## 2. Design Decisions

### 2.1 Handler Types

Support THREE handler styles:

```python
# Style 1: Simple async function (no cleanup needed)
@agent.modes("simple")
async def simple_mode(agent: Agent):
    agent.prompt.append("Simple mode.")
    # No yield = runs once at entry, no cleanup

# Style 2: Generator with cleanup
@agent.modes("research")
async def research_mode(agent: Agent):
    # SETUP
    agent.prompt.append("Research mode.")
    await agent.call("analyze")  # Inner calls OK
    
    yield agent  # PAUSE - mode now active
    
    # CLEANUP (always runs)
    await agent.call("summarize")

# Style 3: Generator with exception handling
@agent.modes("careful")
async def careful_mode(agent: Agent):
    agent.prompt.append("Careful mode.")
    try:
        yield agent
    except Exception as e:
        agent.mode.state["error"] = str(e)
        # Can suppress by not re-raising
        raise  # Or propagate
    finally:
        # Always runs
        await agent.call("cleanup")
```

### 2.2 Mode Exit Triggers

Mode cleanup is triggered by:

1. **Explicit exit**: `async with` block ends, or `agent.modes.exit_mode()` called
2. **Tool-based exit**: Agent calls `exit_current_mode` tool
3. **Transition**: Agent calls tool to switch to different mode
4. **Completion**: Execute loop ends with no pending work (configurable)
5. **Exception**: Error during active phase (cleanup still runs)

### 2.3 Post-Exit LLM Call Decision

After mode cleanup completes, should execute() call LLM again?

```python
class ModeExitBehavior(Enum):
    CONTINUE = "continue"      # Always call LLM after mode exit
    STOP = "stop"              # Never call LLM, return control
    AUTO = "auto"              # Call LLM if conversation is "pending"

# Default at mode registration
@agent.modes("research", on_exit=ModeExitBehavior.AUTO)
async def research_mode(agent: Agent):
    ...

# Override at runtime (from cleanup phase)
@agent.modes("research")
async def research_mode(agent: Agent):
    yield agent
    # Cleanup
    return ModeExitBehavior.STOP  # Don't call LLM after this
```

### 2.4 What "Pending" Means

For `ModeExitBehavior.AUTO`, conversation is "pending" if:
- Last message is from user (needs response)
- Last message is tool result (needs LLM to process)
- Mode cleanup added user/tool messages

Conversation is NOT pending if:
- Last message is assistant without tool calls

---

## 3. Implementation Details

### 3.1 New Data Structures

```python
# In modes.py

class HandlerType(Enum):
    """Type of mode handler."""
    SIMPLE = "simple"           # Regular async function
    GENERATOR = "generator"     # Async generator with yield

@dataclass
class ActiveModeGenerator:
    """Tracks a paused mode generator."""
    mode_name: str
    generator: AsyncGenerator[Agent, None]
    started_at: datetime
    
@dataclass  
class ModeStackEntry:
    """Entry in the mode stack."""
    name: str
    state: dict[str, Any]
    isolation_snapshot: IsolationSnapshot | None
    prompt_snapshot: PromptSnapshot | None
    active_generator: ActiveModeGenerator | None  # NEW: paused generator
    entered_at: datetime

class ModeExitBehavior(Enum):
    """What to do after mode cleanup completes."""
    CONTINUE = "continue"  # Call LLM
    STOP = "stop"          # Don't call LLM
    AUTO = "auto"          # Decide based on conversation state
```

### 3.2 Handler Detection

```python
# In modes.py

def _detect_handler_type(handler: Callable) -> HandlerType:
    """Detect if handler is a simple function or generator."""
    if inspect.isasyncgenfunction(handler):
        return HandlerType.GENERATOR
    elif inspect.iscoroutinefunction(handler):
        return HandlerType.SIMPLE
    else:
        raise TypeError(
            f"Mode handler must be async function or async generator, "
            f"got {type(handler)}"
        )
```

### 3.3 Mode Entry Flow

```python
# In ModeManager

async def _enter_mode(self, mode_name: str, **params: Any) -> None:
    """Enter a mode."""
    info = self._registry.get(mode_name)
    if info is None:
        raise KeyError(f"Mode '{mode_name}' is not registered")
    
    # Validate isolation level
    self._validate_isolation(info.isolation)
    
    # Create snapshots
    isolation_snapshot = self._create_isolation_snapshot(mode_name, info.isolation)
    prompt_snapshot = self._agent.prompt.take_snapshot()
    
    # Initialize state with params
    state = dict(params)
    
    # Create stack entry (generator will be set after setup)
    entry = ModeStackEntry(
        name=mode_name,
        state=state,
        isolation_snapshot=isolation_snapshot,
        prompt_snapshot=prompt_snapshot,
        active_generator=None,
        entered_at=datetime.now(),
    )
    
    # Push onto stack BEFORE running setup (so config is active)
    self._mode_stack.push(entry)
    
    # Run handler setup phase
    try:
        await self._run_handler_setup(mode_name, info, entry)
    except Exception:
        # Setup failed - pop the mode and re-raise
        self._mode_stack.pop()
        self._restore_prompt(prompt_snapshot)
        self._restore_from_isolation_snapshot(isolation_snapshot)
        raise
    
    # Emit event
    self._agent.do(
        AgentEvents.MODE_ENTERED,
        mode_name=mode_name,
        mode_stack=self.mode_stack,
    )

async def _run_handler_setup(
    self, 
    mode_name: str, 
    info: ModeInfo, 
    entry: ModeStackEntry
) -> None:
    """Run handler setup phase (until yield for generators)."""
    handler = info.handler
    handler_type = _detect_handler_type(handler)
    
    if handler_type == HandlerType.SIMPLE:
        # Simple function - just run it
        if info.style == HandlerStyle.AGENT_CENTRIC:
            await handler(self._agent)
        else:
            # Legacy ModeContext style (with deprecation warning)
            ctx = self.create_context()
            await handler(ctx)
        # No generator to track
        entry.active_generator = None
        
    elif handler_type == HandlerType.GENERATOR:
        # Generator - run until first yield
        if info.style == HandlerStyle.AGENT_CENTRIC:
            gen = handler(self._agent)
        else:
            ctx = self.create_context()
            gen = handler(ctx)
        
        # Run setup phase (until yield)
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            # Generator returned without yielding - treat as simple
            entry.active_generator = None
            return
        
        # Generator yielded - store it for later cleanup
        entry.active_generator = ActiveModeGenerator(
            mode_name=mode_name,
            generator=gen,
            started_at=datetime.now(),
        )
```

### 3.4 Mode Exit Flow

```python
# In ModeManager

async def _exit_mode(self) -> ModeExitBehavior:
    """Exit current mode, running cleanup."""
    if not self._mode_stack.current:
        return ModeExitBehavior.STOP
    
    entry = self._mode_stack.current_entry
    mode_name = entry.name
    
    # Emit exiting event
    self._agent.do(AgentEvents.MODE_EXITING, mode_name=mode_name)
    
    exit_behavior = ModeExitBehavior.AUTO  # Default
    
    # Run cleanup if there's an active generator
    if entry.active_generator is not None:
        try:
            exit_behavior = await self._run_handler_cleanup(entry)
        except Exception:
            # Cleanup failed - still need to restore state
            self._cleanup_mode_state(entry)
            raise
    
    # Restore state
    self._cleanup_mode_state(entry)
    
    # Emit exited event
    self._agent.do(
        AgentEvents.MODE_EXITED,
        mode_name=mode_name,
        mode_stack=self.mode_stack,
    )
    
    return exit_behavior

async def _run_handler_cleanup(
    self, 
    entry: ModeStackEntry,
    exception: BaseException | None = None,
) -> ModeExitBehavior:
    """Run handler cleanup phase (after yield)."""
    gen = entry.active_generator.generator
    
    try:
        if exception is not None:
            # Throw exception into generator
            try:
                await gen.athrow(exception)
            except StopAsyncIteration:
                pass
            except type(exception):
                # Generator re-raised - that's expected
                raise
        else:
            # Normal exit - resume generator
            try:
                result = await gen.__anext__()
                # If generator yields again, that's an error
                raise RuntimeError(
                    f"Mode handler '{entry.name}' yielded more than once"
                )
            except StopAsyncIteration as e:
                # Generator completed - check return value
                if e.value is not None:
                    if isinstance(e.value, ModeExitBehavior):
                        return e.value
                    # Could also handle ModeTransition here
    finally:
        # Ensure generator is closed
        await gen.aclose()
    
    return ModeExitBehavior.AUTO

def _cleanup_mode_state(self, entry: ModeStackEntry) -> None:
    """Restore state after mode exit."""
    # Pop from stack
    self._mode_stack.pop()
    
    # Restore prompt
    if entry.prompt_snapshot:
        self._agent.prompt.restore_snapshot(entry.prompt_snapshot)
    
    # Restore isolation
    if entry.isolation_snapshot:
        self._restore_from_isolation_snapshot(entry.isolation_snapshot)
```

### 3.5 Exception Handling in Active Phase

```python
# In ModeContextManager

async def __aexit__(
    self, 
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> bool:
    """Exit the mode, running cleanup."""
    try:
        if exc_val is not None:
            # Exception occurred - pass to cleanup
            await self._manager._exit_mode_with_exception(exc_val)
        else:
            # Normal exit
            await self._manager._exit_mode()
    except Exception:
        # Cleanup raised - let it propagate
        # (original exception is already being propagated)
        if exc_val is None:
            raise
    
    return False  # Don't suppress exceptions

# In ModeManager

async def _exit_mode_with_exception(self, exception: BaseException) -> None:
    """Exit mode when an exception occurred during active phase."""
    if not self._mode_stack.current:
        return
    
    entry = self._mode_stack.current_entry
    
    if entry.active_generator is not None:
        try:
            await self._run_handler_cleanup(entry, exception=exception)
        finally:
            self._cleanup_mode_state(entry)
    else:
        self._cleanup_mode_state(entry)
```

### 3.6 Integration with execute() Loop

The key change: mode handlers are NOT called during execute(). Instead:

1. Mode entry (via tool or context manager) runs setup
2. execute() loop runs normally, using mode's config
3. Mode exit (via tool, completion, or error) runs cleanup

```python
# In Agent.execute()

async def execute(self, *content_parts, **kwargs) -> AsyncIterator[Message]:
    """Main execution loop."""
    
    # Apply any scheduled mode changes FIRST
    await self._mode_manager.apply_scheduled_mode_changes()
    
    # NOTE: We do NOT call mode handlers here anymore!
    # Handlers run at mode entry/exit, not on every execute()
    
    while iterations < max_iterations:
        # ... existing LLM call logic ...
        
        response = await self._get_llm_response()
        yield response
        
        if response.tool_calls:
            # Execute tools (may include mode switch tools)
            async for tool_msg in self._execute_tool_calls(response.tool_calls):
                yield tool_msg
                
                # Check if a mode transition was triggered
                if self._mode_manager.has_pending_transition():
                    await self._mode_manager.apply_scheduled_mode_changes()
        else:
            # No tool calls - check if we should trigger mode exit
            if self._mode_manager.current_mode:
                if self._should_auto_exit_mode():
                    exit_behavior = await self._mode_manager._exit_mode()
                    
                    if exit_behavior == ModeExitBehavior.STOP:
                        return  # Don't call LLM again
                    elif exit_behavior == ModeExitBehavior.CONTINUE:
                        continue  # Call LLM again
                    else:  # AUTO
                        if self._is_conversation_pending():
                            continue
                        else:
                            return
            else:
                # Not in a mode - normal exit
                return
```

### 3.7 Mode Switch Tools (Invokable Modes)

```python
# Generated tool for invokable modes

@tool
async def enter_research_mode(agent: Agent) -> str:
    """Enter research mode for deep investigation."""
    # Schedule the mode switch (will run at start of next execute iteration)
    agent.modes.schedule_mode_switch("research")
    return "Entering research mode..."

@tool  
async def exit_current_mode(agent: Agent) -> str:
    """Exit the current mode."""
    if not agent.mode.name:
        return "Not currently in a mode."
    
    mode_name = agent.mode.name
    agent.modes.schedule_mode_exit()
    return f"Exiting {mode_name} mode..."
```

---

## 4. Test Plan

### 4.1 Unit Tests: Handler Detection

```python
# tests/test_modes_generators.py

class TestHandlerDetection:
    """Test detection of handler types."""
    
    def test_simple_async_function_detected(self):
        async def simple(agent: Agent):
            pass
        assert _detect_handler_type(simple) == HandlerType.SIMPLE
    
    def test_async_generator_detected(self):
        async def generator(agent: Agent):
            yield agent
        assert _detect_handler_type(generator) == HandlerType.GENERATOR
    
    def test_sync_function_raises(self):
        def sync(agent: Agent):
            pass
        with pytest.raises(TypeError, match="async"):
            _detect_handler_type(sync)
    
    def test_regular_generator_raises(self):
        def sync_gen(agent: Agent):
            yield agent
        with pytest.raises(TypeError, match="async"):
            _detect_handler_type(sync_gen)
```

### 4.2 Unit Tests: Simple Handler Lifecycle

```python
class TestSimpleHandlerLifecycle:
    """Test simple (non-generator) mode handlers."""
    
    @pytest.mark.asyncio
    async def test_simple_handler_runs_once_at_entry(self):
        agent = Agent("Test")
        runs = []
        
        @agent.modes("simple")
        async def simple_mode(agent: Agent):
            runs.append("handler")
        
        async with agent:
            async with agent.modes["simple"]:
                assert runs == ["handler"]
                
                with agent.mock("response"):
                    await agent.call("test")
                
                # Handler should NOT have run again
                assert runs == ["handler"]
    
    @pytest.mark.asyncio
    async def test_simple_handler_no_cleanup(self):
        agent = Agent("Test")
        runs = []
        
        @agent.modes("simple")
        async def simple_mode(agent: Agent):
            runs.append("setup")
        
        async with agent:
            async with agent.modes["simple"]:
                runs.append("active")
            runs.append("after")
        
        # No cleanup phase for simple handlers
        assert runs == ["setup", "active", "after"]
```

### 4.3 Unit Tests: Generator Handler Lifecycle

```python
class TestGeneratorHandlerLifecycle:
    """Test async generator mode handlers."""
    
    @pytest.mark.asyncio
    async def test_setup_runs_before_yield(self):
        agent = Agent("Test")
        events = []
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            events.append("setup:start")
            agent.prompt.append("test prompt")
            events.append("setup:end")
            yield agent
            events.append("cleanup")
        
        async with agent:
            events.append("before enter")
            async with agent.modes["gen"]:
                events.append("active")
            events.append("after exit")
        
        assert events == [
            "before enter",
            "setup:start",
            "setup:end",
            "active",
            "cleanup",
            "after exit",
        ]
    
    @pytest.mark.asyncio
    async def test_cleanup_always_runs(self):
        agent = Agent("Test")
        cleanup_ran = False
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            nonlocal cleanup_ran
            cleanup_ran = True
        
        async with agent:
            async with agent.modes["gen"]:
                pass
        
        assert cleanup_ran is True
    
    @pytest.mark.asyncio
    async def test_cleanup_runs_on_exception(self):
        agent = Agent("Test")
        events = []
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            events.append("setup")
            yield agent
            events.append("cleanup")
        
        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["gen"]:
                    events.append("active")
                    raise ValueError("oops")
        
        assert events == ["setup", "active", "cleanup"]
    
    @pytest.mark.asyncio
    async def test_handler_can_catch_exception(self):
        agent = Agent("Test")
        caught = None
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            try:
                yield agent
            except ValueError as e:
                nonlocal caught
                caught = str(e)
                raise  # Re-raise
        
        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["gen"]:
                    raise ValueError("test error")
        
        assert caught == "test error"
    
    @pytest.mark.asyncio
    async def test_handler_can_suppress_exception(self):
        agent = Agent("Test")
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            try:
                yield agent
            except ValueError:
                pass  # Suppress by not re-raising
        
        async with agent:
            # Should NOT raise
            async with agent.modes["gen"]:
                raise ValueError("suppressed")
        
        # If we get here, exception was suppressed
        assert True
    
    @pytest.mark.asyncio
    async def test_multiple_yields_raises_error(self):
        agent = Agent("Test")
        
        @agent.modes("bad")
        async def bad_mode(agent: Agent):
            yield agent
            yield agent  # Second yield - error!
        
        async with agent:
            with pytest.raises(RuntimeError, match="yielded more than once"):
                async with agent.modes["bad"]:
                    pass
```

### 4.4 Unit Tests: Inner Calls During Setup/Cleanup

```python
class TestInnerCalls:
    """Test agent.call() from within mode handlers."""
    
    @pytest.mark.asyncio
    async def test_call_during_setup(self):
        agent = Agent("Test")
        call_results = []
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            with agent.mock("setup response"):
                result = await agent.call("setup call")
                call_results.append(("setup", result.content))
            yield agent
        
        async with agent:
            async with agent.modes["gen"]:
                with agent.mock("active response"):
                    result = await agent.call("active call")
                    call_results.append(("active", result.content))
        
        assert call_results == [
            ("setup", "setup response"),
            ("active", "active response"),
        ]
    
    @pytest.mark.asyncio
    async def test_call_during_cleanup(self):
        agent = Agent("Test")
        call_results = []
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            with agent.mock("cleanup response"):
                result = await agent.call("cleanup call")
                call_results.append(result.content)
        
        async with agent:
            async with agent.modes["gen"]:
                pass
        
        assert call_results == ["cleanup response"]
    
    @pytest.mark.asyncio
    async def test_inner_call_uses_mode_config(self):
        agent = Agent("Test")
        prompts_seen = []
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            agent.prompt.append("MODE PROMPT")
            
            # Inner call should see the mode prompt
            with agent.mock("response"):
                await agent.call("test")
            
            yield agent
        
        # Capture what prompt was sent to LLM
        @agent.on("llm:request")
        async def capture_prompt(ctx):
            prompts_seen.append(ctx.parameters.get("system_prompt", ""))
        
        async with agent:
            async with agent.modes["gen"]:
                pass
        
        assert any("MODE PROMPT" in p for p in prompts_seen)
```

### 4.5 Unit Tests: Nested Modes

```python
class TestNestedModes:
    """Test stacked mode behavior."""
    
    @pytest.mark.asyncio
    async def test_nested_setup_order(self):
        agent = Agent("Test")
        events = []
        
        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            events.append("outer:setup")
            yield agent
            events.append("outer:cleanup")
        
        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            events.append("inner:setup")
            yield agent
            events.append("inner:cleanup")
        
        async with agent:
            async with agent.modes["outer"]:
                events.append("outer:active")
                async with agent.modes["inner"]:
                    events.append("inner:active")
                events.append("outer:after_inner")
        
        assert events == [
            "outer:setup",
            "outer:active",
            "inner:setup",
            "inner:active",
            "inner:cleanup",
            "outer:after_inner",
            "outer:cleanup",
        ]
    
    @pytest.mark.asyncio
    async def test_nested_cleanup_on_exception(self):
        agent = Agent("Test")
        events = []
        
        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            events.append("outer:setup")
            try:
                yield agent
            finally:
                events.append("outer:cleanup")
        
        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            events.append("inner:setup")
            try:
                yield agent
            finally:
                events.append("inner:cleanup")
        
        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["outer"]:
                    async with agent.modes["inner"]:
                        raise ValueError("boom")
        
        # Both cleanups should have run, inner first
        assert events == [
            "outer:setup",
            "inner:setup",
            "inner:cleanup",
            "outer:cleanup",
        ]
    
    @pytest.mark.asyncio
    async def test_inner_mode_sees_outer_state(self):
        agent = Agent("Test")
        inner_saw = None
        
        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            agent.mode.state["outer_value"] = 42
            yield agent
        
        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            nonlocal inner_saw
            inner_saw = agent.mode.state.get("outer_value")
            yield agent
        
        async with agent:
            async with agent.modes["outer"]:
                async with agent.modes["inner"]:
                    pass
        
        assert inner_saw == 42
```

### 4.6 Unit Tests: Mode Exit Behavior

```python
class TestModeExitBehavior:
    """Test post-exit LLM call decision."""
    
    @pytest.mark.asyncio
    async def test_exit_behavior_stop(self):
        agent = Agent("Test")
        llm_calls_after_exit = 0
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            return ModeExitBehavior.STOP
        
        # TODO: Test that execute() doesn't call LLM after mode exit
        # This requires integration with execute() loop
    
    @pytest.mark.asyncio
    async def test_exit_behavior_continue(self):
        agent = Agent("Test")
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            return ModeExitBehavior.CONTINUE
        
        # TODO: Test that execute() calls LLM after mode exit
    
    @pytest.mark.asyncio
    async def test_exit_behavior_auto_pending(self):
        agent = Agent("Test")
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            # Add a user message during cleanup - conversation is pending
            agent.append("Follow-up question", role="user")
            return ModeExitBehavior.AUTO
        
        # TODO: Test that execute() calls LLM because conversation is pending
    
    @pytest.mark.asyncio
    async def test_exit_behavior_auto_complete(self):
        agent = Agent("Test")
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            # No new messages - conversation is complete
            return ModeExitBehavior.AUTO
        
        # TODO: Test that execute() doesn't call LLM
```

### 4.7 Integration Tests: Full Execute Loop

```python
class TestModeExecuteIntegration:
    """Test modes with full execute() loop."""
    
    @pytest.mark.asyncio
    async def test_mode_via_tool_call(self):
        agent = Agent("Test")
        events = []
        
        @agent.modes("research", invokable=True)
        async def research_mode(agent: Agent):
            events.append("research:setup")
            agent.prompt.append("Research mode active.")
            yield agent
            events.append("research:cleanup")
        
        async with agent:
            # Mock LLM to call enter_research_mode tool
            with agent.mock(
                agent.mock.create_tool_call("enter_research_mode"),
                "Now in research mode",
                agent.mock.create_tool_call("exit_current_mode"),
                "Research complete",
            ):
                async for msg in agent.execute("Do some research"):
                    events.append(f"msg:{msg.role}")
        
        assert "research:setup" in events
        assert "research:cleanup" in events
    
    @pytest.mark.asyncio
    async def test_mode_persists_across_llm_calls(self):
        agent = Agent("Test")
        prompts_used = []
        
        @agent.modes("research")
        async def research_mode(agent: Agent):
            agent.prompt.append("RESEARCH_MARKER")
            yield agent
        
        @agent.on("llm:request")
        async def capture(ctx):
            prompts_used.append(ctx.parameters.get("system_prompt", ""))
        
        async with agent:
            async with agent.modes["research"]:
                with agent.mock("response 1", "response 2"):
                    await agent.call("first")
                    await agent.call("second")
        
        # Both calls should have used the mode prompt
        assert all("RESEARCH_MARKER" in p for p in prompts_used)
    
    @pytest.mark.asyncio
    async def test_mode_cleanup_on_execute_exception(self):
        agent = Agent("Test")
        cleanup_ran = False
        
        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            nonlocal cleanup_ran
            cleanup_ran = True
        
        async with agent:
            with pytest.raises(Exception):
                async with agent.modes["gen"]:
                    # Force an error during execute
                    with agent.mock(Exception("LLM error")):
                        await agent.call("test")
        
        assert cleanup_ran is True
```

### 4.8 Integration Tests: Agent-Invoked Mode Switching

```python
class TestAgentInvokedModes:
    """Test agent self-switching modes via tools."""
    
    @pytest.mark.asyncio
    async def test_agent_enters_mode_via_tool(self):
        agent = Agent("Test")
        
        @agent.modes("deep_dive", invokable=True)
        async def deep_dive_mode(agent: Agent):
            agent.prompt.append("Deep dive active.")
            yield agent
        
        async with agent:
            # Agent decides to enter deep_dive mode
            with agent.mock(
                agent.mock.create_tool_call("enter_deep_dive_mode"),
                "Now diving deep into the topic...",
            ):
                response = await agent.call("Analyze this complex topic")
            
            # Should now be in deep_dive mode
            assert agent.mode.name == "deep_dive"
    
    @pytest.mark.asyncio
    async def test_agent_exits_mode_via_tool(self):
        agent = Agent("Test")
        cleanup_ran = False
        
        @agent.modes("research", invokable=True)
        async def research_mode(agent: Agent):
            yield agent
            nonlocal cleanup_ran
            cleanup_ran = True
        
        async with agent:
            async with agent.modes["research"]:
                with agent.mock(
                    agent.mock.create_tool_call("exit_current_mode"),
                    "Exiting research mode",
                ):
                    await agent.call("I'm done researching")
                
                # Mode should have exited
                assert agent.mode.name is None
                assert cleanup_ran is True
    
    @pytest.mark.asyncio
    async def test_agent_switches_between_modes(self):
        agent = Agent("Test")
        mode_sequence = []
        
        @agent.modes("research", invokable=True)
        async def research_mode(agent: Agent):
            mode_sequence.append("research:enter")
            yield agent
            mode_sequence.append("research:exit")
        
        @agent.modes("writing", invokable=True)
        async def writing_mode(agent: Agent):
            mode_sequence.append("writing:enter")
            yield agent
            mode_sequence.append("writing:exit")
        
        async with agent:
            with agent.mock(
                agent.mock.create_tool_call("enter_research_mode"),
                "Researching...",
                agent.mock.create_tool_call("enter_writing_mode"),  # Switch!
                "Now writing...",
                agent.mock.create_tool_call("exit_current_mode"),
                "Done",
            ):
                async for _ in agent.execute("Research then write"):
                    pass
        
        assert mode_sequence == [
            "research:enter",
            "research:exit",  # Cleanup before switch
            "writing:enter",
            "writing:exit",
        ]
```

---

## 5. Migration Notes

### 5.1 Breaking Changes

1. **Mode handlers no longer run on every `call()`**
   - Old: Handler ran at start of each `execute()` iteration
   - New: Handler runs once at entry (setup) and once at exit (cleanup)

2. **Handler return values have new meaning**
   - Old: Could return `ModeTransition` to switch modes
   - New: Can return `ModeExitBehavior` to control post-exit behavior
   - `ModeTransition` still works but is scheduled, not immediate

### 5.2 Backward Compatibility

Simple handlers (no yield) work mostly the same, except:
- They only run once at mode entry, not on every call
- This is likely what users expected anyway

Generator handlers are new functionality.

### 5.3 Documentation Updates Required

1. Update `docs/features/modes.md` with generator syntax
2. Add examples of setup/cleanup patterns
3. Document `ModeExitBehavior` enum
4. Update all example files

---

## 6. Implementation Order

### Phase 1: Core Generator Support ✅ COMPLETE
1. ✅ Add `HandlerType` enum and detection
2. ✅ Add `ActiveModeGenerator` dataclass
3. ✅ Update `ModeStackEntry` to track generators
4. ✅ Implement `_run_handler_setup()` for generators
5. ✅ Implement `_run_handler_cleanup()` for generators
6. ✅ Update `_enter_mode()` and `_exit_mode()`

### Phase 2: Exception Handling ✅ COMPLETE
1. ✅ Update `ModeContextManager.__aexit__` for exception passing
2. ✅ Implement `_exit_mode_with_exception()`
3. ✅ Test cleanup on exceptions
4. ✅ Test exception suppression

### Phase 3: Exit Behavior ✅ COMPLETE
1. ✅ Add `ModeExitBehavior` enum
2. ✅ Update `_exit_mode()` to return behavior
3. ✅ Add `agent.mode.set_exit_behavior()` method
4. 🔲 Integrate with `execute()` loop (moved to Phase 4)
5. 🔲 Add `_is_conversation_pending()` helper (moved to Phase 4)

### Phase 4: Execute Integration 🔲 PENDING
1. Remove mode handler calls from `execute()` loop (if any)
2. Add mode transition handling in tool execution
3. Add auto-exit detection based on `ModeExitBehavior`
4. Add `_is_conversation_pending()` helper for AUTO behavior
5. Test full integration with execute loop

### Phase 5: Documentation & Cleanup 🔲 PENDING
1. Update all documentation with yield syntax
2. Update example files
3. Add migration guide
4. Deprecate old patterns if any

---

## 7. Open Questions

1. **Should simple handlers also have "cleanup" via finally?**
   - Could wrap in try/finally automatically
   - Probably not needed - users can use generators if they need cleanup

2. **What if cleanup raises an exception?**
   - Current plan: Let it propagate
   - Alternative: Log and continue to outer mode cleanup

3. **Should we support `send()` to pass data back to generator?**
   - Spec mentioned this but marked as unnecessary
   - Could be useful: `yield` returns conversation summary
   - Defer for now

4. **Max recursion depth for inner calls?**
   - If handler calls `call()` which somehow triggers same handler...
   - Should be impossible with current design but add guard?
