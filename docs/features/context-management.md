# Context Management

Good Agent provides powerful mechanisms to manage execution context, allowing you to isolate configurations, inject variables, and branch conversation history without affecting the main agent state.

## Context Isolation

The `Agent` class offers several context managers to handle isolated configuration overrides and state management.

### Configuration Overrides

Use `agent.config()` to temporarily override configuration parameters like the model, tools, or temperature for a specific block of code.

```python
async with agent.config(model="gpt-4o", temperature=0.7):
    # This call uses the overridden configuration
    await agent.call("Write a creative story")

# Configuration reverts to original settings here
```

### Context Variables

Use `agent.context()` to inject temporary variables into the agent's context. These are accessible to templates and tools during execution.

```python
# Temporarily inject context variables
async with agent.context(user_id="123", environment="prod"):
    await agent.call("Check system status")
```

### Fork Context

Use `agent.fork_context()` (or `agent.context_manager.fork_context()`) to create a **fully isolated copy** of the agent. This is ideal for exploratory queries or side-tasks where you don't want the conversation history to persist in the main agent.

```python
# Create a temporary fork
async with agent.fork_context() as forked_agent:
    # Messages added here exist ONLY in the fork
    await forked_agent.call("Summarize previous conversation")

# Main 'agent' is untouched and doesn't contain the summary
```

### Thread Context

Use `agent.thread_context()` (or `agent.context_manager.thread_context()`) to temporarily modify the conversation view (e.g., truncating history) while preserving new messages. Unlike a fork, new messages generated during this context are merged back into the main agent's history, but the view modifications are reverted.

```python
# Temporarily truncate history to the last 5 messages to save tokens
async with agent.thread_context(truncate_at=5):
    await agent.call("Based on this recent context...")

# Agent history is restored, but the new assistant response is added
```
