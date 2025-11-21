# Agent Modes

Agent modes provide a powerful way to give your agents distinct behavioral states, specialized tools, and contextual knowledge. Modes enable agents to switch between different "personalities" or capabilities dynamically, while maintaining state isolation and composability.

## Overview

### Key Concepts

- **Mode Handlers** - Functions that configure agent behavior when entering a mode
- **State Scoping** - Each mode maintains isolated state with inheritance
- **Mode Stacking** - Modes can be nested and composed hierarchically
- **Transitions** - Modes can automatically switch to other modes
- **Scheduling** - Mode changes can be scheduled for future calls
- **Tool Integration** - Tools can trigger mode switches programmatically

### Benefits

- **Behavioral Specialization** - Configure agents for specific tasks or domains
- **Context Isolation** - Keep state and configuration separate between modes
- **Dynamic Adaptation** - Switch agent capabilities based on user needs
- **Workflow Management** - Chain modes together for complex multi-step processes
- **State Persistence** - Maintain mode-specific state across conversations

## Basic Mode Usage

### Defining Modes

Create modes using the `@agent.modes()` decorator:

```python
--8<-- "examples/docs/modes_basic.py:1:37"
```

### Entering Modes

Use modes as context managers to activate specific behaviors:

```python
--8<-- "examples/docs/modes_basic.py:39:60"
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

## Complete Examples

Here's a comprehensive example demonstrating advanced mode usage:

```python
--8<-- "examples/modes/comprehensive_modes.py"
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
- **[Components](../extensibility/components.md)** - Create reusable mode-aware components
