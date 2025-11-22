# Good Agent

> ⚠️ **Under Active Development**
>
> This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

A Pythonic, async-first framework for building composable, stateful AI agents.

Good Agent leverages native Python constructs—context managers, decorators, and strong typing—to give you granular control over agent context, lifecycle, and tool execution.

## Overview

Good Agent is designed for developers who want more than just a wrapper around an LLM API. It treats agents as stateful software components that can be composed, extended, and integrated deeply into your application architecture.

## Install

```bash
pip install good-agent
```

## Design Principles

*   **Pythonic API**: We use Python's native features—context managers for lifecycle, decorators for registration, and type hints for validation—to create an interface that feels natural to Python developers.
*   **Type Safety**: Built for modern Python. Beyond standard type hints, our component system allows type-safe access to extensions. Retrieve any registered component instance using its class as a key (e.g., `agent[MemoryComponent]`), ensuring your IDE always knows exactly what methods are available.
*   **Context Control**: The messages sent to the LLM are a *projection* of the agent's state, not just a raw list. This allows you to manipulate context dynamically without losing history.
*   **Dependency Injection**: Access services, database connections, or configurations exactly where you need them in your tools using our built-in dependency injection system.
*   **Composable Components**: Build complex systems from simple parts. Agents can be composed using pipes (`|`), tools can be shared, and specialized "modes" can be swapped in and out.
*   **Isolated Context**: Use context managers to temporarily override settings, tools, or prompts for specific tasks, ensuring your agent's global state remains clean.
*   **Programmatic Tool Invocation**: Execute tools directly from your code, and have those executions recorded in the agent's memory as if the agent decided to call them itself.

## Quickstart

### 1. Hello World

The `Agent` class is your main entry point. It handles conversation history and LLM interaction within an async context manager.

```python
import asyncio
from good_agent import Agent

async def main():
    async with Agent("You are a helpful assistant.", model="gpt-4o") as agent:
        # Call the LLM directly with your message
        response = await agent.call("Hello! Who are you?")
        print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Tools with Dependency Injection

Define tools using the `@tool` decorator. Use `Depends` to inject dependencies, keeping your function signatures clean.

```python
from good_agent import Agent, tool, Depends

# A mock dependency provider
def get_database():
    return {"user_id": 123, "name": "Alice"}

@tool
async def get_user_info(client: dict = Depends(get_database)):
    """Fetch the current user's information."""
    return f"User: {client['name']} (ID: {client['user_id']})"

async with Agent("System", tools=[get_user_info]) as agent:
    response = await agent.call("Who is the current user?")
    print(response.content)
```

### 3. Structured Output

Extract strongly-typed data using Pydantic models.

```python
from pydantic import BaseModel

class SentimentAnalysis(BaseModel):
    sentiment: str
    confidence: float

async with Agent("Analyze sentiment") as agent:
    # The result will be an instance of SentimentAnalysis
    result = await agent.call(
        "I absolutely love this library! It's fantastic.",
        response_model=SentimentAnalysis
    )

    print(f"Sentiment: {result.output.sentiment}")
    print(f"Confidence: {result.output.confidence}")
```

### 4. Interactive Execution

Use `execute()` to iterate over the agent's thought process in real-time. Good Agent supports structural pattern matching for clean handling of different message types.

```python
from good_agent import Agent, ToolMessage, AssistantMessage

async with Agent("Assistant", model="gpt-4o") as agent:
    # Pass the message directly to execute()
    async for message in agent.execute("Calculate 2 + 2 * 4"):
        match message:
            case ToolMessage(tool_name=name, content=result):
                print(f"Tool {name} output: {result}")

            case AssistantMessage(content=text):
                print(f"Response: {text}")
```

#### Accessing Agent State During Iteration

You can inspect and modify agent state during iteration, enabling dynamic control over the conversation flow.

```python
from good_agent import Agent, ToolMessage, AssistantMessage

@tool
async def get_user_location() -> str:
    """Get the user's approximate location."""
    return "Unknown"

async with Agent("Assistant", tools=[get_user_location]) as agent:
    async for message in agent.execute("What's the weather like?"):
        match message:
            case ToolMessage(tool_name="get_user_location"):
                # Access message history
                print(f"Total messages: {len(agent.messages)}")
                print(f"Last assistant message: {agent.assistant[-1].content}")
                
                # Inject context when location lookup fails
                if "Unknown" in message.content:
                    agent.append(
                        "<system>IP lookup failed. User is in San Francisco, CA.</system>",
                        role="system"
                    )
                    print(f"Injected context: {agent[-1].content}")
            
            case AssistantMessage(content=text):
                print(f"Final response: {text}")
```

#### Common State Access Patterns

```python
# Access typed message views
agent.messages          # All messages
agent.user             # Only user messages
agent.assistant        # Only assistant messages  
agent.tool             # Only tool messages

# Get recent messages
agent[-1]              # Last message (any role)
agent.assistant[-1]    # Last assistant message
agent.user[-1]         # Last user message

# Check message content and metadata
last_msg = agent[-1]
print(f"Role: {last_msg.role}")
print(f"Content: {last_msg.content}")
if hasattr(last_msg, 'tool_calls'):
    print(f"Tool calls: {last_msg.tool_calls}")
```

### 5. Agent Modes & Reusability

You can define an agent and its capabilities upfront, then use it later in your application logic. This allows you to separate agent configuration from execution.

```python
from good_agent import Agent, AgentContext

# 1. Define the agent
agent = Agent("General Assistant")

# 2. Register modes or tools on the instance
@agent.modes('research')
async def research_mode(ctx: AgentContext):
    """A specialized mode for deep research."""
    # Add mode-specific context
    ctx.add_system_message("You are a senior researcher. Be thorough.")

    # Execute within this mode's context
    return await ctx.call()

async def main():
    # 3. Use the agent (and its modes) at runtime
    async with agent.modes['research']:
        response = await agent.call("Investigate quantum computing trends.")
        print(response.content)
```

### 6. Composing Agents

Automatic conversation config. Assistant messages of one agent become user messages of the other.

```python
manager = Agent("manager prompt", model="gpt-4o")
researcher = Agent("researcher prompt", model="gpt-4o", tools=[...])

async with manager | researcher as convo:
    # manager messages from researcher become user messages to writer
    manager.assistant.append("Find key facts about Python 3.12")
    
    async for message in convo.execute():
        match message:
            case Message(agent=agent) if agent = manager:
                print(agent.name, message.content)
            case Message(agent=agent) if agent = researcher:
                print(agent.name, message.content)
        
    
```

### 7. CLI Interface

Run any agent interactively from the terminal without writing Python code each time.

```bash
# Install with CLI extras
pip install good-agent[cli]

# Run a saved agent instance
good-agent run examples.sales:agent

# Run with overrides
good-agent run examples.sales:agent --model gpt-4o --temperature 0.1

# Use built-in agents
good-agent run research
good-agent run good-agent

# Run a factory function with arguments
good-agent run examples.factory:build_support_agent prod us-east
```

The CLI provides an interactive session with:
- Rich markdown rendering for assistant responses
- Visual panels showing tool calls and outputs
- Session controls (`exit`, `clear`, Ctrl+C to cancel)
- Command history (use up-arrow to recall previous inputs)

See the [CLI documentation](docs/cli/run.md) for more details on built-in aliases, troubleshooting, and advanced usage.
