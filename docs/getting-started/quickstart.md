# Quickstart

This guide will get you up and running with Good Agent in minutes. You'll learn how to create your first agent, execute simple tasks, and understand the core interaction patterns.

## Prerequisites

- Python 3.11 or higher
- An OpenAI API key (or compatible LLM provider)

Set your API key as an environment variable:

```bash
export OPENAI_API_KEY='your-api-key-here'
```

!!! tip "Alternative LLM Providers"
    Good Agent uses LiteLLM under the hood, so you can use any compatible provider (Anthropic, Google, Azure, etc.). See [Configuration](configuration.md) for details.

## Installation

Install Good Agent using pip or uv:

=== "pip"
    ```bash
    pip install good-agent
    ```

=== "uv"
    ```bash
    uv pip install good-agent
    ```

=== "with CLI extras"
    ```bash
    pip install good-agent[cli]
    ```

## Your First Agent

Let's create a simple agent and have a conversation:

```python title="examples/agent/hello_world.py"
import asyncio
from good_agent import Agent

async def main():
    # Create an agent with a system prompt
    async with Agent("You are a helpful assistant.") as agent:
        # Send a message and get a response
        response = await agent.call("Hello! What can you help me with?")
        print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
```

!!! note "Context Manager Pattern"
    The `async with` statement ensures proper initialization and cleanup. The agent manages its lifecycle automatically, including task cancellation and resource cleanup.

### Understanding the Output

The `call()` method returns an `AssistantMessage` object with:

- `.content` - The text response from the LLM
- `.role` - Always `"assistant"`
- `.tool_calls` - Optional list of tool calls (if any)
- `.metadata` - Additional response metadata

```python
response = await agent.call("What is 2 + 2?")
print(f"Role: {response.role}")        # "assistant"
print(f"Content: {response.content}")  # "4" (or similar)
```

## System Prompts

System prompts define your agent's behavior and personality. They're always the first message in the conversation:

```python
# Positional argument - most concise
async with Agent("You are a data analyst expert.") as agent:
    ...

# No system prompt - minimal agent
async with Agent() as agent:
    ...  # Warning: agent[0] will be None
```

!!! warning "Accessing System Messages"
    If you create an agent without a system prompt, accessing `agent[0]` will return `None` and emit a warning. You can add one later with `agent.set_system_message()`.

### Setting System Prompts Later

You can modify the system prompt after initialization:

```python
--8<-- "tests/unit/agent/test_agent.py:64:75"
```

## Basic Configuration

Configure the model, temperature, and other parameters during initialization:

```python
--8<-- "tests/unit/agent/test_agent.py:48:58"
```

### Common Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"gpt-4o-mini"` | LLM model identifier |
| `temperature` | `float` | `0.7` | Sampling temperature (0.0-2.0) |
| `max_tokens` | `int` | `None` | Maximum tokens in response |
| `top_p` | `float` | `1.0` | Nucleus sampling threshold |
| `tools` | `list` | `[]` | List of tools available to the agent |

See the [Configuration](configuration.md) page for a complete reference.

## Call vs Execute

Good Agent provides two primary ways to interact with your agent:

### `call()` - Simple Request/Response

Use `call()` for straightforward interactions where you want a single response:

```python
--8<-- "examples/agent/basic_chat.py:28:29"
```

**Use `call()` when:**

- You want a single response to a prompt
- You don't need to observe intermediate steps
- You're building a simple chatbot or Q&A system

### `execute()` - Streaming & Iteration

Use `execute()` to observe the agent's thought process, including tool calls and intermediate steps:

```python
--8<-- "examples/agent/basic_chat.py:31:32"
```

**Use `execute()` when:**

- You need to display streaming responses
- You want to log or monitor tool execution
- You're building interactive UIs with real-time feedback
- You need fine-grained control over the execution loop

!!! tip "Pattern Matching"
    Good Agent messages support Python's structural pattern matching for elegant event handling. See [Streaming](../features/streaming.md) for examples.

## Multi-Turn Conversations

Build conversations by appending messages to the agent:

```python
async with Agent("You are a helpful assistant.") as agent:
    # First turn
    agent.append("My name is Alice.")
    response1 = await agent.call()
    print(response1.content)  # "Nice to meet you, Alice!"
    
    # Second turn - agent remembers context
    agent.append("What's my name?")
    response2 = await agent.call()
    print(response2.content)  # "Your name is Alice."
```

### Message History Access

Access the conversation history using array-style indexing:

```python
# Get messages by index
system_msg = agent[0]      # System prompt
first_user = agent[1]      # First user message
last_msg = agent[-1]       # Most recent message

# Get messages by role
user_messages = agent.user          # All user messages
assistant_messages = agent.assistant  # All assistant messages

# Iterate over all messages
for message in agent.messages:
    print(f"{message.role}: {message.content}")
```

See [Messages & History](../core/messages.md) for detailed message management patterns.

## Error Handling

Always handle potential errors when calling LLMs:

```python
from good_agent.exceptions import AgentError

async with Agent("Assistant") as agent:
    try:
        response = await agent.call("Hello!")
    except AgentError as e:
        print(f"Agent error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

!!! note "Common Errors"
    - **Rate limits**: LiteLLM will automatically retry with exponential backoff
    - **Invalid API keys**: Check your environment variables
    - **Network issues**: Consider implementing retry logic in production
    - **Context length exceeded**: Use [message filtering](../core/messages.md#message-filtering) or [context management](../core/agents.md#context-management)

## Next Steps

Now that you have a basic agent running, explore these features:

- **[Configuration](configuration.md)** - Deep dive into agent configuration options
- **[Tools](../core/tools.md)** - Give your agent custom capabilities with function calling
- **[Structured Output](../features/structured-output.md)** - Extract typed data using Pydantic models
- **[Streaming](../features/streaming.md)** - Build real-time interactive experiences
- **[Agent Modes](../features/modes.md)** - Switch agent behaviors dynamically

## Troubleshooting

### Agent won't initialize

```python
# ❌ Don't forget async context manager
agent = Agent("Assistant")
await agent.call("Hello")  # Error: agent not initialized

# ✅ Use async with
async with Agent("Assistant") as agent:
    await agent.call("Hello")
```

### Import errors

```python
# ❌ Old import path
from good_agent.agent import Agent

# ✅ Import from package root
from good_agent import Agent
```

### API key not found

```bash
# Set environment variable
export OPENAI_API_KEY='sk-...'

# Or use litellm format for other providers
export ANTHROPIC_API_KEY='sk-ant-...'
```

Then verify in Python:

```python
import os
print(os.getenv("OPENAI_API_KEY"))  # Should print your key
```

### Type checking issues

If you see type errors with mypy or pyright:

```bash
# Ensure you have type stubs
pip install types-setuptools

# Good Agent is fully typed - enable strict mode
mypy your_script.py --strict
```
