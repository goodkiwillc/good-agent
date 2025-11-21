# Agents

The `Agent` class is the heart of Good Agent. It orchestrates LLM interactions, manages conversation state, executes tools, and provides the foundation for all agent behavior. This page covers the agent lifecycle, state management, versioning, and advanced patterns.

## Agent Basics

### Initialization Patterns

The most common way to use agents is with the async context manager pattern:

```python
--8<-- "examples/docs/agents_basics.py"
```

!!! tip "Context Manager Benefits"
    The `async with` pattern automatically handles:

    - Agent initialization and readiness
    - Resource cleanup and task cancellation
    - Proper error handling and state management
    - Background task termination

### Agent Identity

Each agent has a unique identity and session tracking:

```python
--8<-- "examples/docs/agent_identity.py"
```

### Registry & Retrieval

Agents register themselves globally for debugging and monitoring:

```python
--8<-- "examples/docs/agent_registry.py"
```

## Agent Lifecycle

### State Machine

Agents progress through well-defined states during their lifecycle:

```python
--8<-- "examples/docs/agent_state_machine.py"
```

**State Transitions:**

| State | Description | Next States |
|-------|-------------|-------------|
| `INITIALIZING` | Agent is being set up | `READY` |
| `READY` | Agent is idle, ready for input | `PENDING_RESPONSE`, `PENDING_TOOLS` |
| `PENDING_RESPONSE` | Waiting for LLM response | `PROCESSING`, `READY` |
| `PENDING_TOOLS` | Waiting for tool execution | `PROCESSING`, `READY` |
| `PROCESSING` | Agent is processing/thinking | `READY`, `PENDING_RESPONSE`, `PENDING_TOOLS` |

### Readiness & Initialization

The `@ensure_ready` decorator guarantees agents are initialized before method execution:

```python
--8<-- "examples/docs/agent_readiness.py"
```

### Cleanup & Resource Management

Agents manage background tasks and cleanup automatically:

```python
--8<-- "examples/docs/agent_cleanup.py"
```

## Versioning & State

### Version Tracking

Agents automatically track versions of their conversation state:

```python
--8<-- "tests/unit/agent/test_agent_versioning.py:28:45"
```

**Version Properties:**

- **`version_id`** - Changes every time the agent state is modified
- **`session_id`** - Remains constant for the agent instance lifetime
- **`current_version`** - List of message IDs in the current state

### State Snapshots & Reverting

Create checkpoints and revert to previous states:

```python
--8<-- "examples/docs/agent_revert.py"
```

!!! note "Non-Destructive Reverts"
    `revert_to_version()` doesn't delete history. It creates a new version with the content of the target version. All original messages remain accessible in the internal registry.

### Version Events

Listen for version changes:

```python
--8<-- "examples/docs/agent_version_events.py"
```

## Context Management

### Dynamic Configuration

Use context managers to temporarily override agent settings:

```python
--8<-- "examples/docs/agent_config_context.py"
```

### Context Variables & Templates

Agents support dynamic templating with context variables:

```python
--8<-- "examples/docs/agent_template_variables.py"
```

**Context inheritance and scoping:**

```python
--8<-- "examples/docs/agent_context_scope.py"
```

### Template Functions

Register custom template functions:

```python
--8<-- "examples/docs/agent_template_functions.py"
```

## Agent Composition


### Agent Pools

Coming soon...
<!--
```python
--8<-- "examples/docs/agent_pool_basics.py"
``` -->

### Multi-Agent Workflows
<!-- @TODO: change to basic conversation -->
Chain agents using the pipe operator:

```python
--8<-- "examples/docs/agent_pipeline.py"
```

<!-- @TODO: need to add examples of agent forking/cloning as well as the differnt context isolation -->

## Advanced Patterns

### Custom Agent Classes

Extend agents with domain-specific behavior:

```python
--8<-- "examples/docs/agent_custom_class.py"
```

### Event-Driven Architecture

Build reactive agents with comprehensive event handling:

```python
--8<-- "examples/docs/agent_monitored.py"
```

### Persistent State

Implement state persistence for long-running agents:

```python
--8<-- "examples/docs/agent_persistence.py"
```

## Performance & Monitoring

### Agent Metrics

Monitor agent performance and behavior:

```python
--8<-- "examples/docs/agent_metrics.py"
```

### Memory Management

For long-running agents, manage message history:

```python
--8<-- "examples/docs/agent_memory_management.py"
```

### Debugging & Introspection

Debug agent behavior with built-in tools:

```python
--8<-- "examples/docs/agent_debugging.py"
```

## Best Practices

### Agent Lifecycle

- **Always use context managers** for proper cleanup and resource management
- **Check readiness** before operations if managing lifecycle manually
- **Handle initialization errors** gracefully with appropriate timeouts
- **Monitor task counts** in long-running agents to prevent memory leaks

### State Management

- **Use versioning** for checkpointing complex workflows
- **Implement state persistence** for agents that must survive restarts
- **Clean up message history** periodically in long-running agents
- **Use context scoping** to isolate temporary configuration changes

### Performance

- **Pool agents** for high-concurrency scenarios instead of creating many instances
- **Fork contexts** for parallel processing rather than duplicating agents
- **Monitor version counts** as excessive versioning can consume memory
- **Use background tasks** judiciously and ensure proper cleanup

## Troubleshooting

### Initialization Issues

```python
--8<-- "examples/docs/agent_troubleshooting_init.py"
```

### State Machine Errors

```python
--8<-- "examples/docs/agent_troubleshooting_state.py"
```

### Memory Issues

```python
--8<-- "examples/docs/agent_troubleshooting_memory.py"
```

### Context Problems

```python
--8<-- "examples/docs/agent_troubleshooting_context.py"
```

## Next Steps

- **[Messages & History](messages.md)** - Deep dive into message management and history
- **[Tools](tools.md)** - Add capabilities to your agents with function calling
- **[Events](events.md)** - Build reactive agents with event-driven architecture
- **[Agent Modes](../features/modes.md)** - Dynamic behavior switching and scoped contexts
