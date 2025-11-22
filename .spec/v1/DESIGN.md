# Good Agent Design Specification

This document serves as the comprehensive 1-page reference for the Good Agent library, covering core APIs, features, and architectural internals.

## 1. Core Usage

### Basic Initialization & Execution
The `Agent` class is the entry point. It manages conversation history, tools, and LLM interactions.

```python
from good_agent import Agent

async with Agent("You are a helpful assistant.") as agent:
    agent.append("What is 2+2?")

    # Simple non-streaming call
    response = await agent.call()
    assert response.content == "4"

    # Typed Access
    assert agent[-1].role == "assistant"
    assert agent.assistant[-1].content == "4"
```

### Configuration
Configuration can be passed during initialization or loaded from defaults.

```python
async with Agent(
    "System Prompt",
    model="gpt-4o",
    temperature=0.7,
    tools=[...],            # List of functions or Tool objects
    extensions=[...],       # AgentComponent instances
    context={'user': 'me'}, # Initial context variables
    telemetry=True,         # Enable telemetry
    debug=False,            # Enable debug logging
) as agent:
    ...
```

## 2. Key Features

### Structured Output
Extract typed data using Pydantic models (via Instructor integration).

```python
from pydantic import BaseModel

class Analysis(BaseModel):
    sentiment: str
    score: float

result = await agent.call(response_model=Analysis)
print(result.output.sentiment)  # Typed access
```

### Streaming & Iteration
Iterate over the execution lifecycle, useful for capturing tool calls, thoughts, and streaming tokens.

```python
agent.append("Do complex task")
async for message in agent.execute(streaming=True):
    match message:
        case ToolMessage(tool_name=name, content=result):
            print(f"Tool {name}: {result}")
        case AssistantMessage(content=text):
            print(f"Assistant: {text}")
```

### Tools & MCP
Tools support dependency injection (`FastDepends`) and Model Context Protocol (MCP).

```python
from good_agent import tool, Depends

@tool
async def search(query: str, client: SearchClient = Depends(get_client)):
    return await client.search(query)

# MCP Integration
await agent.tools.load_mcp_servers(["filesystem-server"])
```

### Agent Modes
Modes allow agents to switch behaviors, toolsets, and context scopes dynamically.
*See `.spec/v1/features/agent-modes.md` for full specification.*

<!-- add_system_message - that's not the right way to do it - should use context -->
```python
@agent.modes('research')
async def research_mode(ctx: AgentContext):
    """Research mode with specific tools."""
    ctx.add_system_message("You are a researcher.")
    # Mode-specific tools and state
    async with ctx.temporary_tools([search, scrape]):
        return await ctx.call()

# Usage
async with agent.modes['research']:
    await agent.call("Investigate topic")
```

### Multi-Agent Orchestration
Compose agents using the pipe operator `|`.

```python
researcher = Agent("Researcher")
writer = Agent("Writer")

async with (researcher | writer) as convo:
    # Researcher's output becomes Writer's input
    researcher.append("Find data", role="assistant")
    await writer.call()
```

### Stateful Resources (MDXL)
Agents can interact with stateful documents (YAML, Markdown) using resource-scoped tools.

```python
from good_agent.resources import EditableYAML

config = EditableYAML('config.yaml')
async with config(agent):
    await agent.call("Update setting 'timeout' to 60")
```

### Commands (Planned)
Interactive shortcuts for workflows.

```python
@command(name="test")
async def run_tests(agent: Agent, path: str = "."):
    ...
```

### Human-in-the-Loop & Interactive Patterns

Agents can pass control back to the user interface for decisions, data collection, or open-ended clarification. This uses a `handoff` mechanism that suspends execution.

#### 1. Simple Decisions
Suspend for a single value or choice.

```python
# Agent requests input (suspends execution)
await agent.handoff(
    "Approve deployment?",
    options=["Approve", "Reject"]
)

# Host application resumes later
if agent.state == AgentState.WAITING_FOR_INPUT:
    await agent.resume("Approve")
```

#### 2. Structured Wizards (Forms)
Collect complex data using Pydantic models. The host UI can render this as a multi-step form or wizard.

```python
class DeploymentConfig(BaseModel):
    env: Literal["prod", "staging"]
    replicas: int
    confirm_db_migration: bool

# Agent requests full configuration
config = await agent.handoff(
    "Please configure the deployment:",
    response_model=DeploymentConfig
)
```

#### 3. Conversational Handoff
Yield control for an open-ended chat session (e.g., for debugging or brainstorming) before resuming the task.

```python
# Switch to interactive chat mode until user says "continue"
await agent.handoff(
    "I need help understanding the requirements. Let's chat.",
    mode="interactive_chat"
)

# The host system now treats inputs as chat messages,
# not just answers to a specific question.
```

## 3. Architecture & Internals

### Message & History Management

Messages are stored in a typed `MessageList` with role-specific views. Versioning allows you to fork or revert conversation state.

```python
# Access typed message views
user_msgs = agent.user           # FilteredMessageList[UserMessage]
tool_msgs = agent.tool           # FilteredMessageList[ToolMessage]
last_assistant = agent.assistant[-1]

# Versioning
original_version = agent.version_id
agent.append("Mistake", role="user")

# Revert to previous state (undo)
agent.versioning.revert_to_version(0)
assert agent.version_id != original_version # New version created for the revert
```

### State Machine

The agent maintains an internal lifecycle state, which can be inspected or waited upon.

```python
from good_agent.agent.state import AgentState

# Check current state
if agent.state == AgentState.READY:
    print("Agent is ready for input")

# Wait for initialization to complete
await agent.initialize()
assert agent.is_ready
```

### Task Management

Background tasks (like loggers or side-effects) should be managed by the agent to ensure proper cleanup.

```python
async def background_monitor():
    while True:
        await asyncio.sleep(1)
        print("Monitoring...")

# Create a task tied to the agent's lifecycle
task = agent.create_task(
    background_monitor(),
    name="monitor",
    wait_on_ready=False # Don't block agent initialization
)

print(f"Active tasks: {agent.task_count}")
```

### Event System

Subscribe to lifecycle events for logging, debugging, or custom behaviors.

```python
from good_agent.events import AgentEvents, ToolCallAfterParams

@agent.on(AgentEvents.TOOL_CALL_AFTER)
async def log_tool_result(ctx: EventContext[ToolCallAfterParams, None]):
    tool_name = ctx.parameters.get("tool_name")
    success = ctx.parameters.get("success")
    print(f"Tool {tool_name} finished. Success: {success}")

# Trigger an event manually (if needed)
agent.do(AgentEvents.CUSTOM_EVENT, data="payload")
```
