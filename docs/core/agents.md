# Agents

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

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

## Mode Accessor

The `agent.mode` property provides access to the current mode context:

```python
from good_agent import Agent

async with Agent("Assistant") as agent:
    @agent.modes("research")
    async def research_mode(agent: Agent):
        # Access mode state
        agent.mode.state["topic"] = "quantum computing"
        
        # Add to system prompt (auto-restored on exit)
        agent.prompt.append("Focus on research and citations.")
    
    async with agent.mode("research"):
        # Mode properties
        print(agent.mode.name)              # "research"
        print(agent.mode.stack)             # ["research"]
        print(agent.mode.in_mode("research"))  # True
        print(agent.mode.state["topic"])    # "quantum computing"
        
        # Transition to another mode
        # agent.mode.switch("writing")
        # agent.mode.exit()
```

**Key Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `agent.mode.name` | `str \| None` | Current mode name (top of stack) |
| `agent.mode.stack` | `list[str]` | All active modes (LIFO order) |
| `agent.mode.state` | `dict` | Current mode's state dictionary |
| `agent.mode.in_mode(name)` | `bool` | Check if mode is anywhere in stack |
| `agent.mode.switch(name)` | `ModeTransition` | Request transition to another mode |
| `agent.mode.exit()` | `ModeTransition` | Request exit from current mode |

## System Prompt Manager

The `agent.prompt` property manages dynamic system prompts with automatic restoration:

```python
from good_agent import Agent

async with Agent("Assistant") as agent:
    # Render the current system prompt
    print(agent.prompt.render())
    
    @agent.modes("expert")
    async def expert_mode(agent: Agent):
        # Append to system prompt (restored on mode exit)
        agent.prompt.append("You are an expert. Use technical language.")
        
        # Prepend to system prompt
        agent.prompt.prepend("IMPORTANT: Be precise.")
        
        # Named sections
        agent.prompt.sections["context"] = "Current project: AI Research"
        
        # Persist changes beyond mode exit
        agent.prompt.append("Always be helpful.", persist=True)
    
    async with agent.mode("expert"):
        # Prompt includes all additions
        print(agent.prompt.render())
    
    # After mode exit: appends/prepends restored, persist=True kept
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `agent.prompt.append(msg, persist=False)` | Add to end of prompt |
| `agent.prompt.prepend(msg, persist=False)` | Add to start of prompt |
| `agent.prompt.sections[name] = content` | Set named section |
| `agent.prompt.render()` | Get composed prompt string |

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

### Thread Safety & Locking

Agents now serialize all state mutations (message append/replace/system, mode transitions, execute loop bookkeeping, tool emission) with a per-Agent reentrant async lock. Tool execution remains parallel; only their emissions are serialized. Cross-thread callers should use the thread-safe proxy to schedule work onto the Agent's loop while honoring the lock:

```python
from good_agent import Agent

agent = Agent("Assistant")
proxy = agent.threadsafe

# In another thread:
response = proxy.call("Hello from another thread")
```

For custom mutation, wrap work with `await agent.run_state_guarded(coro_fn)` or `async with agent.state_guard(): ...` to avoid races.

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
