# Agent Modes

!!! warning "Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Agent modes provide a powerful way to give your agents distinct behavioral states, specialized tools, and contextual knowledge. Modes enable agents to switch between different "personalities" or capabilities dynamically, while maintaining state isolation and composability.

## Overview

### Key Concepts

- **Mode Handlers** - Functions that configure agent behavior when entering a mode (receive `agent: Agent` parameter)
- **State Scoping** - Each mode maintains isolated state with inheritance via `agent.mode.state`
- **Mode Stacking** - Modes can be nested and composed hierarchically
- **Transitions** - Modes can automatically switch to other modes via `agent.mode.switch()`
- **Scheduling** - Mode changes can be scheduled for future calls
- **Tool Integration** - Tools can trigger mode switches programmatically
- **Isolation Levels** - Control how much state isolation each mode has (`none`, `config`, `thread`, `fork`)
- **Invokable Modes** - Generate tools that allow the agent to switch modes autonomously
- **Standalone Modes** - Define modes outside the agent class using the `@mode()` decorator

### Benefits

- **Behavioral Specialization** - Configure agents for specific tasks or domains
- **Context Isolation** - Keep state and configuration separate between modes
- **Dynamic Adaptation** - Switch agent capabilities based on user needs
- **Workflow Management** - Chain modes together for complex multi-step processes
- **State Persistence** - Maintain mode-specific state across conversations

## API Reference

### Mode Handler Signature (v2)

Mode handlers receive the agent instance directly:

```python
@agent.modes("research")
async def research_mode(agent: Agent):
    """Handler receives agent: Agent parameter."""
    # Access mode state via agent.mode.state
    agent.mode.state["key"] = "value"
    
    # Add system prompt via agent.prompt.append()
    agent.prompt.append("You are in research mode.")
    
    # Access mode info via agent.mode
    print(agent.mode.name)   # Current mode name
    print(agent.mode.stack)  # Full mode stack
    
    # Transition to another mode
    return agent.mode.switch("writing")
```

### Key Properties

| Property | Description |
|----------|-------------|
| `agent.mode.name` | Current mode name (or `None` if not in a mode) |
| `agent.mode.stack` | List of all active modes (stack) |
| `agent.mode.state` | Dict-like access to current mode's state |
| `agent.mode.in_mode(name)` | Check if a mode is active anywhere in the stack |
| `agent.mode.switch(name)` | Request transition to another mode |
| `agent.mode.exit()` | Request exit from current mode |
| `agent.prompt.append(msg)` | Add to system prompt (auto-restored on mode exit) |

## Basic Mode Usage

### Defining Modes

Create modes using the `@agent.modes()` decorator:

```python
--8<-- "examples/docs/modes_basic.py:1:37"
```

### Entering Modes

Use modes as context managers to activate specific behaviors:

```python
--8<-- "examples/docs/modes_basic.py:38:47"
```

## Mode State Management

### Scoped State

Each mode maintains its own state that persists across calls:

```python
--8<-- "examples/docs/modes_state_scoped.py"
```

### State Inheritance

When modes are nested, inner modes inherit state from outer modes:

```python
--8<-- "examples/docs/modes_state_inheritance.py"
```

## Mode Stacking and Composition

### Nested Modes

Modes can be stacked to combine behaviors:

```python
--8<-- "examples/docs/modes_stacking.py"
```

### Mode Stack Operations

Access and manipulate the mode stack:

```python
--8<-- "examples/docs/modes_stack_ops.py"
```

## Mode Transitions

### Manual Mode Switching

Modes can programmatically switch to other modes:

```python
--8<-- "examples/docs/modes_transitions_manual.py"
```

### Scheduled Mode Changes

Schedule mode changes for future agent calls:

```python
--8<-- "examples/docs/modes_scheduled.py"
```

## Advanced Mode Patterns

### Conditional Mode Logic

Create modes with complex conditional behavior:

```python
--8<-- "examples/docs/modes_conditional.py"
```

### Mode-Specific Tool Access

Provide different tools based on current mode:

```python
--8<-- "examples/docs/modes_tool_access.py"
```

### Workflow Modes

Create complex workflows using mode chains:

```python
--8<-- "examples/docs/modes_workflow.py"
```

## Context Management

### Mode Context Operations

Access and modify conversation context within modes:

```python
--8<-- "examples/docs/modes_context_aware.py"
```

### Dynamic System Messages

Modify system messages based on mode state:

```python
--8<-- "examples/docs/modes_dynamic_system.py"
```

## Event Integration

### Mode Events

Monitor mode changes with the event system:

```python
--8<-- "examples/docs/modes_events.py"
```

### Mode State Events

Monitor mode state changes:

```python
--8<-- "examples/docs/modes_state_events.py"
```

## Testing Modes

### Unit Testing Mode Handlers

Test mode functionality in isolation:

```python
--8<-- "examples/docs/modes_testing_unit.py"
```

### Mock Testing with Modes

Test mode behavior with mocked responses:

```python
--8<-- "examples/docs/modes_testing_mocks.py"
```

## Performance Considerations

### Mode Overhead

Minimize mode overhead for production use:

```python
--8<-- "examples/docs/modes_performance_overhead.py"
```

### State Management Efficiency

Optimize mode state handling:

```python
--8<-- "examples/docs/modes_performance_efficiency.py"
```

## Isolation Levels

Control how much state isolation each mode has:

```python
from good_agent import Agent

async with Agent("Isolated agent") as agent:
    # No isolation (default) - shared state and messages
    @agent.modes("shared", isolation="none")
    async def shared_mode(agent: Agent):
        pass
    
    # Config isolation - tools isolated, messages shared
    @agent.modes("config_isolated", isolation="config")
    async def config_mode(agent: Agent):
        pass
    
    # Thread isolation - messages are a temp view, new ones kept
    @agent.modes("threaded", isolation="thread")
    async def thread_mode(agent: Agent):
        pass
    
    # Fork isolation - complete isolation, nothing persists back
    @agent.modes("forked", isolation="fork")
    async def fork_mode(agent: Agent):
        pass
```

## Invokable Modes

Generate tools that allow the agent to switch modes autonomously:

```python
from good_agent import Agent

async with Agent("Self-switching agent") as agent:
    # Creates a tool called "enter_research_mode"
    @agent.modes("research", invokable=True)
    async def research_mode(agent: Agent):
        """Enter research mode for deep investigation."""
        agent.prompt.append("Focus on research and citations.")
    
    # Custom tool name
    @agent.modes("writing", invokable=True, tool_name="start_writing")
    async def writing_mode(agent: Agent):
        """Start writing mode for drafting content."""
        agent.prompt.append("Focus on clear, concise writing.")
```

## Standalone Modes

Define modes outside the agent class for reusability:

```python
from good_agent import Agent, mode

# Define standalone modes
@mode("research", invokable=True)
async def research_mode(agent: Agent):
    """Reusable research mode."""
    agent.prompt.append("Research mode active.")

@mode("writing", isolation="thread")
async def writing_mode(agent: Agent):
    """Reusable writing mode."""
    agent.prompt.append("Writing mode active.")

# Register with an agent
agent = Agent("My agent", modes=[research_mode, writing_mode])

# Or register after creation
agent.modes.register(research_mode)
```

## Best Practices

### Mode Design Guidelines

- **Single responsibility** - Each mode should have a focused purpose
- **State management** - Use mode state for persistence, not computation
- **Transition logic** - Keep mode transitions predictable and documented
- **Resource cleanup** - Clean up mode state when exiting long-running modes
- **Event integration** - Use events to monitor mode behavior in production

### Production Recommendations

```python
--8<-- "examples/docs/modes_production.py"
```

## Next Steps

- **[Multi-Agent](./multi-agent.md)** - Coordinate modes across multiple agents
- **[Interactive Execution](./interactive-execution.md)** - Use modes in interactive execution contexts
- **[Events](../core/events.md)** - Monitor and respond to mode changes
- **[Tools](../core/tools.md)** - Build tools that interact with agent modes
