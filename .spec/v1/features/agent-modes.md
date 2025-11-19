# Agent Modes - Feature Specification

## Overview

Agent modes enable agents to operate in distinct behavioral states with different tools, context transformations, and capabilities. Modes are **optional, stackable, and composable** - agents can work without modes, enter/exit modes dynamically, and nest modes with scoped state inheritance.

**Core capabilities:**
- Define named operational modes with specialized behavior
- Stack modes with automatic cleanup and state scoping
- Switch modes programmatically or via agent self-direction
- Compose context transformations and tool sets per mode
- Integrate with existing routing, commands, and stateful resources

**Architectural areas impacted:**
- Agent lifecycle and context management
- Tool filtering and registration
- Message history transformation
- Event emission and observability
- Interactive commands and agent-as-tool patterns

## Requirements & Constraints

### Functional Requirements

1. **Optional and Progressive**
   - Agents work without modes defined (backwards compatible)
   - Modes are opt-in, not required for basic operation
   - No default mode - agents start with `current_mode = None`

2. **Stackable and Composable**
   - Support nested mode contexts with automatic cleanup
   - Scoped state: inner modes inherit outer state, writes shadow
   - Exit restores previous mode from stack

3. **Flexible Entry Points**
   - Context manager: `async with agent.modes['research']`
   - Direct entry/exit: `await agent.enter_mode('research')`
   - Agent self-switching via tools (scheduled, not immediate)
   - Mode transitions from within mode handlers

4. **Pythonic API**
   - Decorator registration: `@agent.modes('name')`
   - Subscript access: `agent.modes['research']`
   - Dependency injection for mode handlers
   - Type-safe with Pydantic where applicable

5. **Observable and Testable**
   - Mode entry/exit emits events
   - Mode state visible via `current_mode`, `mode_stack`, `in_mode()`
   - Transcript recording includes mode transitions
   - Mock/replay support for testing

### Constraints

1. **Async-first**: All mode handlers and transitions are async
2. **Context-managed**: Modes integrate with `async with Agent(...)` lifecycle
3. **History-preserving**: Mode transitions recorded in conversation history
4. **Telemetry-aware**: Mode changes visible in observability hooks
5. **Multi-agent compatible**: Modes work with pipe operator and sub-agents

## Current Architecture Hooks

### Agent Lifecycle
- Modes integrate with `async with Agent(...)` context manager
- Mode stack maintained per agent instance
- Mode entry/exit hooks into existing `before_call` / `after_call` lifecycle

### Message Model & History
- Mode transitions can append system/context messages
- Mode-specific context transformations apply before LLM calls
- Typed message access (`agent[-1]`, `agent.assistant`) works within modes

### Tooling System
- Modes can temporarily swap/filter tool sets
- `@tool` decorated methods work in mode contexts
- Tool dependency injection receives mode-aware context
- Agent self-switching via special mode-switching tools

### Context Pipeline
- Modes define context transformation pipelines
- Transformations compose with existing context managers
- Scoped state enables mode-specific context variables

### Stateful Resources
- Modes can enter stateful resource contexts
- Resources (like `EditableYAML`) work within mode scopes
- Mode state separate from resource state

### Event System
- Mode entry/exit emits events: `mode:entered`, `mode:exited`
- Existing `@agent.on()` decorators can listen for mode events
- Telemetry hooks capture mode transitions

### Multi-Agent Patterns
- Each agent in a pipe has independent mode stack
- Mode state not shared between agents (unless explicit)
- Agent-as-tool can expose modes via tool interface

## API Sketches

### Basic Mode Definition

```python
from good_agent import Agent, AgentContext, Context

agent = Agent("You are a helpful assistant.", tools=[...])

# Define a mode
@agent.modes('research')
async def research_mode(ctx: AgentContext):
    """Deep research mode with specialized tools and context."""

    # Add mode-specific context
    ctx.add_system_message("You are in research mode. Focus on finding authoritative sources.")

    # Temporarily swap tools (using existing temporary_tools pattern)
    with ctx.temporary_tools([web_search, arxiv_search, scholar_search]):
        # Call LLM in mode context
        response = await ctx.call()

    # Modes can yield control or return transitions
    return response

# Use mode via context manager
async with agent:
    # Normal operation (no mode)
    await agent.call("Hello!")

    # Enter research mode
    async with agent.modes['research'] as researcher:
        # researcher is agent (same object, now in mode)
        assert researcher is agent
        assert agent.current_mode == 'research'

        await researcher.call("Research quantum computing")

    # Automatically exits mode after context
    assert agent.current_mode is None
```

### Mode Handler Signatures (Dependency Injection)

```python
# Minimal - just need agent
@agent.modes('simple')
async def simple_mode(agent: Agent = Context()):
    await agent.call()

# Full context for mode-specific features
@agent.modes('code-review')
async def code_review_mode(ctx: AgentContext = Context()):
    ctx.state['files_reviewed'] = []

    # Apply context transformations
    ctx.add_system_message(
        "Code review mode: analyze code quality, suggest improvements. "
        "DO NOT modify code."
    )

    response = await ctx.call()
    return response

# With mode parameters
@agent.modes('planning')
async def planning_mode(
    agent: Agent = Context(),
    ctx: AgentContext = Context(),
    topic: str = Context('topic'),
    depth: str = Context('depth', default='shallow'),
):
    """Planning mode with configurable parameters."""

    agent.append(f"Creating a {depth} plan for: {topic}")

    # Mode-specific state
    ctx.state['plan_topic'] = topic
    ctx.state['plan_depth'] = depth

    await agent.call()
```

### Mode Stacking and Scoped State

```python
@agent.modes('outer')
async def outer_mode(ctx: AgentContext):
    """Outer mode establishes base context."""

    # Set state visible to inner modes
    ctx.state['project'] = 'quantum-sim'
    ctx.state['review_level'] = 'thorough'

    # Add system context
    ctx.add_system_message(f"Working on project: {ctx.state['project']}")

    response = await ctx.call()
    return response

@agent.modes('inner')
async def inner_mode(ctx: AgentContext):
    """Inner mode inherits and shadows outer state."""

    # Read inherited state
    project = ctx.state['project']  # 'quantum-sim' (from outer)

    # Shadow outer state (write creates local variable)
    ctx.state['review_level'] = 'detailed'  # Shadows outer
    ctx.state['inner_only'] = 'data'  # Only visible in inner

    response = await ctx.call()
    return response

# Usage
async with agent:
    async with agent.modes['outer']:
        # mode_stack = ['outer']
        # state = {'project': 'quantum-sim', 'review_level': 'thorough'}

        async with agent.modes['inner']:
            # mode_stack = ['outer', 'inner']
            # state = {'project': 'quantum-sim', 'review_level': 'detailed', 'inner_only': 'data'}

            assert agent.current_mode == 'inner'
            assert agent.in_mode('inner')  # True
            assert agent.in_mode('outer')  # True (still in stack)

            await agent.call("Do work")

        # Back to outer: mode_stack = ['outer']
        # state = {'project': 'quantum-sim', 'review_level': 'thorough'}
        # (inner's shadow removed, inner_only gone)

        assert agent.current_mode == 'outer'
        assert not agent.in_mode('inner')  # False (popped)
```

### Mode Inspection and Discovery

```python
# Check current mode
if agent.current_mode == 'research':
    print("In research mode")

if agent.current_mode is None:
    print("No active mode")

# Check if mode is active (anywhere in stack)
if agent.in_mode('research'):
    print("Research mode active")

# View full stack
print(agent.mode_stack)  # ['outer', 'inner'] (bottom to top)

# List available modes
available = agent.modes.list()  # ['research', 'code-review', 'planning']

# Get mode metadata
info = agent.modes['research'].info()
# Returns: {'name': 'research', 'description': '...', 'handler': ...}
```

### Agent Self-Switching via Tools

```python
from good_agent import Agent, tool, Context

# Define mode-switching tool
@tool
async def enter_research_mode(agent: Agent = Context()) -> str:
    """Switch to research mode for deep investigation.

    Use this when you need to:
    - Search academic papers
    - Find authoritative sources
    - Conduct comprehensive research
    """
    # Schedule switch for next call (not immediate)
    agent.schedule_mode_switch('research')
    return "Will enter research mode after this response."

@tool
async def exit_current_mode(agent: Agent = Context()) -> str:
    """Exit the current mode and return to normal operation."""
    if agent.current_mode:
        agent.schedule_mode_exit()
        return f"Will exit {agent.current_mode} mode after this response."
    return "Not in any mode."

# Register tools
agent = Agent(
    "You are a helpful assistant. Use modes when appropriate.",
    tools=[enter_research_mode, exit_current_mode, ...]
)

# Agent decides to switch modes
async with agent:
    response = await agent.call(
        "I need comprehensive research on quantum computing"
    )
    # Agent might call enter_research_mode tool
    # Mode switch happens before next call

    # Next call executes in research mode
    response2 = await agent.call("Continue")
```

### Direct Mode Entry/Exit (Non-Context-Manager)

```python
async with agent:
    # Enter mode directly
    await agent.enter_mode('research', topic='AI safety', depth='deep')

    # Now in research mode
    assert agent.current_mode == 'research'

    # Make calls in mode
    await agent.call("Research AI alignment")
    await agent.call("What about value learning?")

    # Exit mode
    await agent.exit_mode()

    # Back to no mode
    assert agent.current_mode is None
```

### Mode Transitions from Within Handlers

```python
@agent.modes('research')
async def research_mode(ctx: AgentContext):
    """Research mode that can transition to report writing."""

    # Do research
    ctx.add_system_message("Research mode: find comprehensive information")
    response = await ctx.call()

    # Check if ready to write report
    if ctx.state.get('research_complete'):
        # Transition to report-writing mode
        return ctx.switch_mode('write-report')

    return response

@agent.modes('write-report')
async def write_report_mode(ctx: AgentContext):
    """Write report based on research."""

    # Access research results from previous mode
    research_data = ctx.state.get('research_results')

    ctx.add_system_message("Write a comprehensive report based on research.")
    response = await ctx.call()

    # Return to normal after writing
    return ctx.exit_mode()
```

### Integration with Stateful Resources

```python
from good_agent import Agent
from good_agent.resources import EditableYAML, PlanningDocument

@agent.modes('document-editor')
async def document_editor_mode(
    ctx: AgentContext,
    document_path: str = Context('document_path'),
):
    """Multi-turn document editing mode."""

    # Load document as stateful resource
    doc = EditableYAML.open(document_path)

    # Enter resource context within mode
    async with doc(ctx.agent, context_mode='delta'):
        # Now has document editing tools

        ctx.add_system_message(
            f"Editing document: {document_path}\n"
            "Use provided tools to modify the document."
        )

        # Multi-turn editing
        while not doc.is_done:
            response = await ctx.call()

            # Check if user wants to exit
            if ctx.should_exit:
                break

        # Save if changes made
        if doc.has_changes:
            await doc.save()

    return ctx.exit_mode()

# Usage
async with agent:
    async with agent.enter_mode('document-editor', document_path='config.yaml')

    await agent.call("Update the timeout setting to 30 seconds")
    await agent.call("Add a new section for logging configuration")
    await agent.call("Save and exit")
```

### Mode Context Transformations (Pipeline)

```python
@agent.modes('rag-enhanced')
async def rag_mode(ctx: AgentContext):
    """Mode with RAG context injection."""

    # Define context transformation
    async def inject_rag_context(ctx: AgentContext) -> AgentContext:
        """Inject relevant context from vector store."""
        last_message = ctx.agent[-1]
        relevant_docs = await vector_store.search(last_message.content)

        ctx.add_context_message(
            f"# Relevant Context\n{relevant_docs}",
            section="rag-context"
        )
        return ctx

    async def truncate_old_messages(ctx: AgentContext) -> AgentContext:
        """Keep only recent messages if context is large."""
        if ctx.estimated_tokens > 8000:
            # Keep system, first 2, and last 10 messages
            ctx.set_llm_messages([
                ctx.agent.system_message,
                *ctx.agent.messages[0:2],
                *ctx.agent.messages[-10:]
            ])
        return ctx

    # Apply pipeline before LLM call
    ctx.pipeline(inject_rag_context, truncate_old_messages)

    response = await ctx.call()
    return response
```

### Multi-Agent with Modes

```python
# Each agent has independent mode stack
researcher = Agent("Research assistant", tools=[web_search])
writer = Agent("Technical writer", tools=[formatting_tools])

@researcher.modes('deep-research')
async def deep_research(ctx: AgentContext):
    ctx.add_system_message("Conduct thorough research with citations.")
    return await ctx.call()

@writer.modes('technical-writing')
async def technical_writing(ctx: AgentContext):
    ctx.add_system_message("Write clear, technical documentation.")
    return await ctx.call()

# Use together with pipe operator
async with (researcher | writer) as conversation:
    # Enter mode on researcher only
    async with researcher.modes['deep-research']:
        researcher.append("Research AI frameworks", role='assistant')

        async for message in conversation.execute():
            match message:
                case Message(agent=researcher):
                    print(f"[Researcher in {researcher.current_mode}]: {message.content}")
                case Message(agent=writer):
                    print(f"[Writer in {writer.current_mode}]: {message.content}")
```

### Commands and Mode Integration

```python
from good_agent import Agent, command

agent = Agent("You are a helpful assistant.")

# Command that enters a mode
@command(name='research', description='Enter research mode')
async def research_command(
    agent: Agent = Context(),
    query: str = Context('query', default=None)
):
    """Enter research mode with optional initial query."""

    await agent.enter_mode('research')

    if query:
        response = await agent.call(query)
        return response
    else:
        return "Entered research mode. What would you like to research?"

# Command to exit mode
@command(name='exit-mode', description='Exit current mode')
async def exit_mode_command(agent: Agent = Context()):
    """Exit the current mode."""

    if agent.current_mode:
        mode_name = agent.current_mode
        await agent.exit_mode()
        return f"Exited {mode_name} mode."
    else:
        return "Not in any mode."

# Usage in chat
"""
User: /research quantum computing
Agent: Entered research mode. [research response]

User: /exit-mode
Agent: Exited research mode.
"""
```

## Lifecycle & State

### Mode Lifecycle

```
1. Registration (decorator)
   @agent.modes('name')
   async def handler(...): ...

2. Entry
   - Context manager: async with agent.modes['name']
   - Direct: await agent.enter_mode('name')
   - Tool: agent.schedule_mode_switch('name')

3. Active
   - Mode handler executes
   - Mode-specific tools, context, state active
   - Calls to agent.call() use mode context

4. Exit
   - Context manager: auto-exit on context exit
   - Direct: await agent.exit_mode()
   - Handler return: ctx.exit_mode() or ctx.switch_mode()

5. Cleanup
   - Pop mode from stack
   - Restore previous mode (if any)
   - Remove shadowed state
   - Emit mode:exited event
```

### State Scoping Rules

```python
# State inheritance and shadowing
mode_stack = ['outer', 'middle', 'inner']

# Read order: inner -> middle -> outer (first match wins)
value = ctx.state['key']  # Checks inner, then middle, then outer

# Write always creates/updates in current mode scope
ctx.state['key'] = 'value'  # Sets in inner scope only

# On exit, inner scope removed:
# - Inner's keys deleted
# - Shadowed keys from outer scopes restored
# - Outer scopes unaffected
```

### Mode Stack Management

```python
class ModeStack:
    """Manages mode stack with scoped state."""

    def __init__(self):
        self._stack: list[tuple[str, dict]] = []  # [(mode_name, state)]

    def push(self, mode_name: str, state: dict = None):
        """Push new mode onto stack."""
        self._stack.append((mode_name, state or {}))

    def pop(self) -> tuple[str, dict] | None:
        """Pop mode from stack."""
        if self._stack:
            return self._stack.pop()
        return None

    @property
    def current(self) -> str | None:
        """Current mode (top of stack)."""
        if self._stack:
            return self._stack[-1][0]
        return None

    def in_mode(self, mode_name: str) -> bool:
        """Check if mode is anywhere in stack."""
        return any(name == mode_name for name, _ in self._stack)

    def get_state(self, key: str, default=None):
        """Get state with scoped lookup (inner to outer)."""
        for _, state in reversed(self._stack):
            if key in state:
                return state[key]
        return default

    def set_state(self, key: str, value):
        """Set state in current scope."""
        if self._stack:
            _, state = self._stack[-1]
            state[key] = value
```

### Event Emissions

```python
# Mode entry
agent.emit('mode:entered', {
    'mode_name': 'research',
    'mode_stack': agent.mode_stack,
    'parameters': {...},
    'timestamp': datetime.now()
})

# Mode exit
agent.emit('mode:exited', {
    'mode_name': 'research',
    'mode_stack': agent.mode_stack,
    'duration': timedelta(...),
    'timestamp': datetime.now()
})

# Listen for mode events
@agent.on('mode:entered')
async def on_mode_entered(event):
    print(f"Entered mode: {event['mode_name']}")

@agent.on('mode:exited')
async def on_mode_exited(event):
    print(f"Exited mode: {event['mode_name']}, duration: {event['duration']}")
```

### Integration with Agent.call()

```python
class Agent:
    async def call(self, message: str = None, **kwargs):
        """Make LLM call with mode context."""

        # Check for pending mode switch (from tool)
        if self._pending_mode_switch:
            await self._apply_pending_mode_switch()

        # Get current mode handler
        if self.current_mode:
            mode_handler = self.modes[self.current_mode]

            # Create mode context
            ctx = AgentContext(
                agent=self,
                mode_name=self.current_mode,
                mode_stack=self.mode_stack.copy(),
                state=self.mode_stack.get_all_state(),
            )

            # Execute mode handler
            result = await mode_handler(ctx)

            # Handle mode transitions
            if isinstance(result, ModeTransition):
                await self._handle_transition(result)

            return result
        else:
            # Normal operation (no mode)
            return await self._call_llm(message, **kwargs)
```

## Testing Strategy

### Unit Testing Modes

```python
import pytest
from good_agent import Agent, AgentContext, MockAgent

@pytest.mark.asyncio
async def test_mode_registration():
    """Test mode registration via decorator."""
    agent = Agent("Test agent")

    @agent.modes('test-mode')
    async def test_mode_handler(ctx: AgentContext):
        return "test response"

    assert 'test-mode' in agent.modes.list()
    info = agent.modes['test-mode'].info()
    assert info['name'] == 'test-mode'

@pytest.mark.asyncio
async def test_mode_context_manager():
    """Test entering/exiting mode via context manager."""
    agent = Agent("Test agent")

    @agent.modes('research')
    async def research_mode(ctx: AgentContext):
        return await ctx.call()

    async with agent:
        assert agent.current_mode is None

        async with agent.modes['research'] as researcher:
            assert researcher is agent
            assert agent.current_mode == 'research'
            assert agent.in_mode('research')

        assert agent.current_mode is None
        assert not agent.in_mode('research')

@pytest.mark.asyncio
async def test_mode_stacking():
    """Test nested mode contexts."""
    agent = Agent("Test agent")

    @agent.modes('outer')
    async def outer_mode(ctx: AgentContext):
        ctx.state['outer_var'] = 'outer'
        return await ctx.call()

    @agent.modes('inner')
    async def inner_mode(ctx: AgentContext):
        ctx.state['inner_var'] = 'inner'
        # Should see outer_var
        assert ctx.state['outer_var'] == 'outer'
        return await ctx.call()

    async with agent:
        async with agent.modes['outer']:
            assert agent.current_mode == 'outer'
            assert agent.mode_stack == ['outer']

            async with agent.modes['inner']:
                assert agent.current_mode == 'inner'
                assert agent.mode_stack == ['outer', 'inner']
                assert agent.in_mode('outer')
                assert agent.in_mode('inner')

            assert agent.current_mode == 'outer'
            assert agent.mode_stack == ['outer']
            assert not agent.in_mode('inner')

@pytest.mark.asyncio
async def test_scoped_state():
    """Test state scoping and shadowing."""
    agent = Agent("Test agent")

    @agent.modes('outer')
    async def outer_mode(ctx: AgentContext):
        ctx.state['x'] = 'outer'
        ctx.state['y'] = 'only-outer'
        return await ctx.call()

    @agent.modes('inner')
    async def inner_mode(ctx: AgentContext):
        # Read inherited state
        assert ctx.state['x'] == 'outer'
        assert ctx.state['y'] == 'only-outer'

        # Shadow outer state
        ctx.state['x'] = 'inner'
        ctx.state['z'] = 'only-inner'

        return await ctx.call()

    async with agent:
        async with agent.modes['outer']:
            # Outer state
            # x='outer', y='only-outer'

            async with agent.modes['inner']:
                # Inner state (with shadowing)
                # x='inner' (shadowed), y='only-outer' (inherited), z='only-inner'
                pass

            # Back to outer - shadow removed
            # x='outer' (restored), y='only-outer', z removed
```

### Transcript Recording

```python
# Modes should be recorded in transcripts
from good_agent import Agent, TranscriptRecorder

async with Agent("Test agent") as agent:
    recorder = TranscriptRecorder(agent)

    @agent.modes('research')
    async def research_mode(ctx: AgentContext):
        return await ctx.call()

    # Record session with modes
    async with recorder.record('test-session'):
        await agent.call("Hello")

        async with agent.modes['research']:
            await agent.call("Research AI")

        await agent.call("Thanks")

    # Transcript includes mode transitions
    transcript = recorder.get_transcript('test-session')
    assert transcript.events[1]['type'] == 'mode:entered'
    assert transcript.events[1]['mode_name'] == 'research'
    assert transcript.events[3]['type'] == 'mode:exited'

# Replay transcripts with modes
async with Agent("Test agent") as agent:
    @agent.modes('research')
    async def research_mode(ctx: AgentContext):
        return await ctx.call()

    # Replay automatically enters/exits modes at correct times
    await agent.replay_transcript('test-session')
```

### Mock Mode Handlers

```python
# Mock mode handlers for testing
@pytest.mark.asyncio
async def test_with_mock_mode():
    """Test agent behavior with mocked mode."""
    agent = Agent("Test agent")

    # Mock mode handler
    mock_handler = AsyncMock(return_value="mock response")

    # Register mock
    agent.modes._registry['test-mode'] = mock_handler

    async with agent:
        async with agent.modes['test-mode']:
            response = await agent.call("test")

    # Verify mock called
    mock_handler.assert_called_once()

    # Verify mode entered/exited
    assert agent.current_mode is None
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_mode_with_tools():
    """Test mode with tool filtering."""

    @tool
    async def research_tool() -> str:
        return "research result"

    @tool
    async def write_tool() -> str:
        return "write result"

    agent = Agent("Test agent", tools=[research_tool, write_tool])

    @agent.modes('research-only')
    async def research_mode(ctx: AgentContext):
        # Only expose research_tool in this mode
        ctx.filter_tools(['research_tool'])
        return await ctx.call()

    async with agent:
        # Normal: both tools available
        assert len(agent.available_tools) == 2

        async with agent.modes['research-only']:
            # Research mode: only research_tool
            assert len(agent.available_tools) == 1
            assert 'research_tool' in agent.available_tools

        # Back to normal: both tools again
        assert len(agent.available_tools) == 2

@pytest.mark.asyncio
async def test_mode_self_switching():
    """Test agent switching modes via tool."""

    @tool
    async def enter_special_mode(agent: Agent = Context()) -> str:
        agent.schedule_mode_switch('special')
        return "Switching to special mode"

    agent = Agent("Test agent", tools=[enter_special_mode])

    @agent.modes('special')
    async def special_mode(ctx: AgentContext):
        return await ctx.call()

    async with agent:
        # Agent calls enter_special_mode tool
        # (Simulate LLM deciding to call tool)
        await agent.invoke(enter_special_mode)

        # Mode switch pending
        assert agent._pending_mode_switch == 'special'

        # Next call applies switch
        response = await agent.call("continue")

        # Now in special mode
        assert agent.current_mode == 'special'
```

## Implementation Phases

### Phase 1: Core Infrastructure (MVP)

**Goal**: Basic mode registration, entry/exit, single mode at a time

- [ ] `ModeManager` class with decorator and subscript access
- [ ] `ModeContext` for state and mode-specific operations
- [ ] Mode registration: `@agent.modes('name')`
- [ ] Mode access: `agent.modes['name']` returns context manager
- [ ] Basic mode entry/exit: `async with agent.modes['name']`
- [ ] `agent.current_mode` property
- [ ] `agent.in_mode(name)` method
- [ ] Mode lifecycle events: `mode:entered`, `mode:exited`
- [ ] Basic AgentContext with `call()`, `state`, `add_system_message()`
- [ ] Integration with `Agent.call()` - check current mode
- [ ] Unit tests for core functionality

**Success Criteria**:
- Can define and enter/exit modes
- Mode state isolated per mode
- Events emitted correctly
- Tests pass

### Phase 2: Mode Stacking and Scoped State

**Goal**: Support nested modes with state inheritance

- [x] `ModeStack` class for stack management
- [x] Scoped state: read inheritance, write shadowing
- [x] `agent.mode_stack` property
- [x] Updated `in_mode()` to check entire stack
- [x] Automatic cleanup on mode exit
- [x] State restoration when popping modes
- [x] Tests for nested modes and state scoping

**Success Criteria**:
- Nested modes work correctly
- State scoping follows variable scope semantics
- Mode stack visible and correct
- Cleanup automatic and complete

### Phase 3: Mode Transitions and Self-Switching

**Goal**: Support programmatic mode switching and agent self-direction

- [x] `agent.schedule_mode_switch(name)` for tool-based switching
- [x] `agent.enter_mode(name, **params)` direct entry
- [x] `agent.exit_mode()` direct exit
- [x] `ctx.switch_mode(name)` from within handlers
- [x] `ctx.exit_mode()` from within handlers
- [x] Mode-switching tools interface
- [x] Pending mode switch handling in `call()`
- [x] Mode transition events
- [x] Tests for all transition methods

**Success Criteria**:
- Agents can switch modes via tools
- Direct entry/exit works
- Transitions from handlers work
- No mid-execution state corruption

### Phase 4: Dependency Injection and Parameters

**Goal**: Flexible mode handler signatures with parameter injection

- [ ] FastDepends integration for mode handlers
- [ ] Support `Agent = Context()` injection
- [ ] Support `AgentContext = Context()` injection
- [ ] Support mode parameters: `param = Context('param_name')`
- [ ] Parameter passing: `agent.enter_mode('name', param=value)`
- [ ] Parameter validation with Pydantic
- [ ] Tests for various handler signatures

**Success Criteria**:
- Multiple handler signature patterns work
- Parameters injected correctly
- Type safety maintained

### Phase 5: Context Transformations and Pipelines

**Goal**: Mode-specific context and message transformations

- [ ] `ctx.pipeline(*transforms)` for transformation chains
- [ ] `ctx.add_context_message(content, section)` for ephemeral context
- [ ] `ctx.set_llm_messages(messages)` for history filtering
- [ ] `ctx.temporary_tools(tools)` for mode-specific toolsets
- [ ] `ctx.filter_tools(names)` for tool filtering
- [ ] Built-in transformations: truncate, RAG injection, etc.
- [ ] Tests for transformations

**Success Criteria**:
- Context transformations compose correctly
- Mode-specific tools work
- Message filtering doesn't corrupt history

### Phase 6: Discovery and Observability

**Goal**: Introspection and debugging capabilities

- [ ] `agent.modes.list()` returns all mode names
- [ ] `agent.modes['name'].info()` returns metadata
- [ ] Rich mode metadata: description, tools, parameters
- [ ] Telemetry hooks for mode transitions
- [ ] Transcript recording includes modes
- [ ] Replay transcripts with mode transitions
- [ ] Tests for observability features

**Success Criteria**:
- Modes discoverable programmatically
- Metadata accurate and useful
- Transcripts capture full mode lifecycle

### Phase 7: Advanced Integration

**Goal**: Integration with existing advanced features

- [ ] Stateful resources work within modes
- [ ] Multi-agent pipe operator with independent modes
- [ ] Commands that enter/exit modes
- [ ] Agent-as-tool exposes modes
- [ ] Sub-agent modes integration
- [ ] Tests for all integrations

**Success Criteria**:
- Modes compose with all existing features
- No conflicts or unexpected interactions
- Multi-agent scenarios work correctly

### Phase 8: Documentation and Examples

**Goal**: Comprehensive documentation and real-world examples

- [ ] API reference documentation
- [ ] Tutorial: basic modes
- [ ] Tutorial: mode stacking
- [ ] Tutorial: agent self-switching
- [ ] Example: code review mode
- [ ] Example: research mode with RAG
- [ ] Example: multi-turn document editor
- [ ] Example: time-bounded operations
- [ ] Migration guide (if breaking changes)

**Success Criteria**:
- Docs clear and complete
- Examples runnable and realistic
- Users can learn modes incrementally

## Open Questions

### 1. Mode Handler Return Values

What can/should mode handlers return?

**Options:**
- a) Response string (like current agent.call())
- b) ModeTransition object (for explicit transitions)
- c) None (implicit stay in mode)
- d) Any of the above

**Current thinking**: Support all (d) for flexibility

### 2. Mode State Persistence

Should mode state persist across calls or reset each time?

**Options:**
- a) Persist for duration of mode context
- b) Reset on each call
- c) Configurable per mode

**Current thinking**: (a) Persist - modes are stateful

### 3. Mode Conflicts

What happens if you try to enter a mode that's already active?

**Options:**
- a) Error
- b) No-op (already in mode)
- c) Re-enter (reset state)

**Current thinking**: (b) No-op - idempotent

### 4. Mode Metadata

What metadata should modes expose?

**Current thinking:**
- Name
- Description (from docstring)
- Handler function reference
- Parameters (from signature)
- Tools (if specified)
- Entry count / last entered timestamp?

### 5. Tool Visibility in Modes

How do modes control tool visibility?

**Options:**
- a) Explicit tool list in mode definition
- b) Tool filtering in mode handler
- c) Tool affordances/permissions
- d) All of the above

**Current thinking**: Start with (b), add (a) as convenience

### 6. Mode Exit Behavior

When mode handler completes, what happens?

**Options:**
- a) Stay in mode (explicit exit required)
- b) Exit automatically
- c) Configurable

**Current thinking**: (a) for context manager, (b) for direct call

### 7. Error Handling in Modes

If mode handler raises exception, what happens to mode stack?

**Options:**
- a) Auto-exit mode (cleanup)
- b) Stay in mode (let caller handle)
- c) Pop entire stack (full reset)

**Current thinking**: (a) Auto-exit for safety

### 8. Multi-Agent Mode Coordination

Should there be patterns for coordinating modes across agents?

**Examples:**
- Shared mode state
- Mode synchronization
- Mode triggers (one agent entering mode triggers another)

**Current thinking**: Start simple (independent modes), add if needed

### 9. Mode Composition Patterns

Should we support mode composition/inheritance?

**Example:**
```python
@agent.modes('base-research')
async def base_research(ctx): ...

@agent.modes('deep-research', extends='base-research')
async def deep_research(ctx): ...
```

**Current thinking**: Defer - can compose via nesting for now

### 10. Mode Analytics

Should modes emit metrics automatically?

**Potential metrics:**
- Time in mode
- Call count per mode
- Mode transition frequency
- Error rate per mode

**Current thinking**: Emit basic events, let users/telemetry handle metrics

## Acceptance Criteria

### Functional Criteria

- [ ] Agents work without modes (backwards compatible)
- [ ] Can define modes via decorator
- [ ] Can enter/exit modes via context manager
- [ ] Can enter/exit modes directly
- [ ] Mode stacking works with automatic cleanup
- [ ] Scoped state: inner inherits outer, writes shadow
- [ ] Agent can switch modes via tools (scheduled)
- [ ] Mode transitions emit events
- [ ] `current_mode`, `mode_stack`, `in_mode()` accurate
- [ ] Mode handlers support flexible signatures (DI)
- [ ] Modes work with stateful resources
- [ ] Modes work in multi-agent scenarios
- [ ] Mode discovery: list modes, get metadata

### Non-Functional Criteria

- [ ] API is Pythonic and intuitive
- [ ] Performance: mode overhead < 5% on call latency
- [ ] Memory: mode stack bounded and cleaned up
- [ ] Type safety: Mypy/Pyright validation passes
- [ ] Documentation: API docs and tutorials complete
- [ ] Testing: >90% coverage on mode system
- [ ] Transcripts: record and replay modes correctly
- [ ] Observability: mode events in telemetry
- [ ] Error messages: clear and actionable

### Integration Criteria

- [ ] Works with existing `Agent` lifecycle
- [ ] Compatible with `@tool` decorators
- [ ] Compatible with `AgentComponent` pattern
- [ ] Compatible with pipe operator (`agent_a | agent_b`)
- [ ] Compatible with agent-as-tool pattern
- [ ] Compatible with stateful resources
- [ ] Compatible with transcript recording/replay
- [ ] Compatible with FastDepends DI system

## Migration Notes

**Breaking Changes**: None expected - modes are purely additive

**Deprecations**: None

**New Requirements**:
- Python 3.10+ (for pattern matching in examples, not required)
- No new external dependencies

**Upgrade Path**:
- Existing agents work unchanged
- Add modes progressively as needed
- No migration required for existing code

## Future Enhancements (Out of Scope)

These are interesting but deferred to future iterations:

1. **Behaviors** (composable mixins) - orthogonal to modes
2. **DAG-based orchestration** - graph execution
3. **Temporal routing** - time-based mode switching
4. **Affordances system** - permission-based mode restrictions
5. **Checkpoint/rollback** - conversation state snapshots
6. **Mode templates** - pre-built common modes
7. **Mode composition** - inherit/extend modes
8. **Reactive modes** - event-driven mode switching
9. **Mode analytics** - automatic metrics and insights
10. **Visual mode editor** - GUI for mode configuration

## References

- `.spec/v1/DESIGN.md` - Core agent design
- `.spec/v1/features/agent-routing-orchestration.md` - Original routing concepts
- `.spec/v1/features/agent-routing-additional-concepts.md` - Advanced patterns
- Existing patterns: stateful resources, agent-as-tool, multi-agent

---

## Changelog

- **2025-01-18**: Initial comprehensive feature specification
  - Naming decision: "Modes" over "Routes"
  - API design: `@agent.modes('name')` and `agent.modes['name']`
  - Scoped state semantics defined
  - Mode stacking support confirmed
  - 8-phase implementation plan
