# Context Management

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

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

### Template Variables

Use `agent.vars` to store runtime variables for templates. These are accessible to templates and tools during execution using Jinja2 syntax (`{{variable_name}}`).

```python
# Set initial context
async with Agent("Base prompt", context={"env": "prod", "user": "alice"}) as agent:
    # Override context temporarily
    with agent.vars(env="dev", debug=True):
        agent.append("Debug info for {{user}} in {{env}}: {{debug}}")
        # Renders: "Debug info for alice in dev: True"
        print(agent[-1].content)

    # Back to original context
    agent.append("User {{user}} in {{env}}")
    # Renders: "User alice in prod"
    print(agent[-1].content)
```

### Isolated Sessions

Use `agent.isolated()` to create a **fully isolated copy** of the agent with its own ID and message history. This is ideal for exploratory queries, parallel processing, or side-tasks where you don't want the conversation history to persist in the main agent. All changes are discarded when the context exits.

```python
async with Agent("Base agent") as agent:
    agent.append("Shared context")

    # Isolated sessions for parallel processing
    async with agent.isolated() as fork1, agent.isolated() as fork2:
        # Each fork is a separate agent with independent message history
        task1 = asyncio.create_task(fork1.call("Process option A"))
        task2 = asyncio.create_task(fork2.call("Process option B"))

        results = await asyncio.gather(task1, task2)

    # Original agent unchanged by fork operations
    assert len(agent) == 2  # SystemMessage + "Shared context"
    # Fork messages don't appear in original agent
```

You can also truncate history when creating an isolated session:

```python
async with agent.isolated(truncate_at=5) as sandbox:
    # Sandbox only has the first 5 messages from the original
    await sandbox.call("Based on recent context...")
    # All changes discarded when exiting
```

### Conversation Branches

Use `agent.branch()` to temporarily modify the conversation view (e.g., truncating history) while preserving new messages. Unlike `isolated()`, new messages generated during this context are merged back into the main agent's history, but the view modifications are reverted.

```python
# Temporarily truncate history to the last 5 messages to save tokens
async with agent.branch(truncate_at=5) as branched:
    await branched.call("Based on this recent context...")

# Agent history is restored, but the new assistant response is added
```
