# Good Agent - Core Reference

A condensed overview of common APIs and patterns for the Good Agent library.
Based on `src/good_agent/agent/core.py` and `.spec/v1/DESIGN.md`.

## 1. Agent Initialization

The `Agent` class is the main entry point. It handles LLM interaction, tool execution, and context.

```python
from good_agent import Agent, tool

# Basic Usage
async with Agent("You are a helpful assistant.") as agent:
    response = await agent.call("Hello!")

# Advanced Configuration
async with Agent(
    "You are a data analyst.",           # Positional: System Prompt
    model="gpt-4o",                      # LLM Model
    temperature=0.0,                     # Deterministic output
    tools=[my_tool, "mcp:server"],       # List of tools or MCP servers
    extensions=[MyComponent()],          # Agent components
    context={"env": "prod"},             # Initial context variables
    name="analyst-01",                   # Agent name (optional)
) as agent:
    await agent.call("Analyze this data")
```

## 2. Tools

Tools are Python functions decorated with `@tool`. They support dependency injection via `FastDepends`.

```python
from good_agent import tool, Depends

@tool
async def get_weather(
    location: str, 
    unit: str = "celsius"
) -> str:
    """Get the current weather for a location."""
    return f"25 {unit} in {location}"

# With Dependency Injection
def get_db():
    return Database()

@tool
async def query_db(
    query: str, 
    db: Database = Depends(get_db)
) -> list[dict]:
    return db.execute(query)
```

## 3. Execution & Streaming

Execute agent actions and handle responses.

```python
# Single Turn (Non-streaming)
response = await agent.call("What's the weather in Tokyo?")
print(response.content)

# Streaming Execution (Iterate over events)
from good_agent.messages import AssistantMessage, ToolMessage

agent.append("Check system status")
async for message in agent.execute():
    match message:
        case ToolMessage(tool_name=name, content=result):
            print(f"🛠️ Tool {name}: {result}")
        case AssistantMessage(content=text):
            print(f"🤖 Assistant: {text}")
```

## 4. Structured Output

Extract typed data directly using Pydantic models.

```python
from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    age: int
    interests: list[str]

# Returns a response wrapper with .data containing the instance
response = await agent.call(
    "Extract user info from: John is 30 and likes coding.",
    response_model=UserProfile
)
profile = response.data
print(f"{profile.name} is {profile.age}")
```

## 5. Agent Modes

Switch behaviors and toolsets dynamically using Modes.

```python
from good_agent import Agent

@agent.modes('research')
async def research_mode(agent: Agent):
    """Specialized mode for research tasks."""
    # Add temporary system prompt (auto-restored on mode exit)
    agent.prompt.append("You are a research expert. Be thorough.")
    
    # Access mode state
    agent.mode.state["topic"] = "quantum computing"

# Enter mode
async with agent.modes['research']:
    await agent.call("Research quantum computing")
    print(agent.mode.name)   # "research"
    print(agent.mode.stack)  # ["research"]

# Mode features:
# - isolation: 'none', 'config', 'thread', 'fork'
# - invokable: generate tools for agent self-switching
# - standalone: @mode() decorator for reusable modes
```

## 6. Event System

Hook into the agent lifecycle for logging, monitoring, or custom behavior.

```python
from good_agent.events import AgentEvents, ToolCallAfterParams

@agent.on(AgentEvents.TOOL_CALL_AFTER)
async def on_tool_result(ctx):
    params = ctx.parameters # Typed dict based on event
    print(f"Tool {params.get('tool_name')} returned: {params.get('response')}")

# Manual event emission
await agent.apply("custom:event", payload="data")
```

## 7. Multi-Agent Orchestration

Pipe agents together for sequential workflows.

```python
researcher = Agent("Researcher", tools=[search])
writer = Agent("Writer")

# Researcher output -> Writer input
async with (researcher | writer) as workflow:
    researcher.append("Find latest AI news")
    # Executes researcher, passes output to writer, returns writer's response
    final_response = await writer.call()
```

## 8. Components (Extensions)

Modular functionality using `AgentComponent`.

```python
from good_agent import AgentComponent, tool

class MemoryComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.memory = []

    @tool
    def remember(self, fact: str):
        """Store a fact."""
        self.memory.append(fact)
        return "Stored."

    async def install(self, agent):
        await super().install(agent)
        # Register event listeners or other setup
```

## 9. State & Versioning

Manage conversation history and agent state.

```python
# Message Views
history = agent.messages          # All messages
user_msgs = agent.user            # Only user messages
tool_outputs = agent.tool         # Only tool outputs

# Versioning (Undo/Redo-like capability)
snapshot_id = agent.version_id
await agent.call("Something wrong")
agent.versioning.revert_to_version(snapshot_id)

# Template Variables
agent.vars['user_name'] = 'Alice'
agent.vars['session_id'] = '12345'

# Isolated Session (sandbox - all changes discarded on exit)
async with agent.isolated() as sandbox:
    await sandbox.call("Try something risky")
    # All changes discarded when exiting

# Conversation Branch (new messages preserved on exit)
async with agent.branch(truncate_at=5) as branched:
    response = await branched.call("Summarize the above")
    # After exit: original messages + new response preserved
```

## 10. CLI Configuration

Manage global API keys and settings using the CLI. Values are stored in `~/.good-agent/config.toml`.

```bash
# Set API keys (aliases like 'openai' map to OPENAI_API_KEY)
good-agent config set openai sk-...
good-agent config set anthropic sk-...

# Use Profiles (dev, prod, personal, etc.)
good-agent config set openai sk-dev-key --profile dev
good-agent run --profile dev my_agent.py

# List configuration
good-agent config list
```
