# Agents

The `Agent` class is the heart of Good Agent. It orchestrates LLM interactions, manages conversation state, executes tools, and provides the foundation for all agent behavior. This page covers the agent lifecycle, state management, versioning, and advanced patterns.

## Agent Basics

### Initialization Patterns

The most common way to use agents is with the async context manager pattern:

```python
from good_agent import Agent

# Basic initialization
async with Agent("You are a helpful assistant.") as agent:
    response = await agent.call("Hello!")
    print(response.content)
```

For more control over the lifecycle:

```python
# Manual initialization (not recommended for most use cases)
agent = Agent("System prompt")
await agent.initialize()  # Must call before using

try:
    response = await agent.call("Hello!")
finally:
    await agent.close()  # Cleanup resources
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
async with Agent("Assistant") as agent:
    print(f"Agent ID: {agent.id}")           # Unique ULID
    print(f"Session ID: {agent.session_id}") # Conversation session
    print(f"Version ID: {agent.version_id}") # Current state version
    print(f"Name: {agent.name}")             # Optional human-readable name
```

### Registry & Retrieval

Agents register themselves globally for debugging and monitoring:

```python
async with Agent("Assistant", name="support-bot") as agent:
    # Retrieve by ID
    same_agent = Agent.get(agent.id)
    assert same_agent is agent
    
    # Retrieve by name
    named_agent = Agent.get_by_name("support-bot")
    assert named_agent is agent
```

## Agent Lifecycle

### State Machine

Agents progress through well-defined states during their lifecycle:

```python
from good_agent.agent.state import AgentState

async with Agent("Assistant") as agent:
    # During context manager entry
    print(agent.state)  # AgentState.INITIALIZING → AgentState.READY
    
    # During execution
    agent.append("Calculate 2+2")
    async for message in agent.execute():
        print(agent.state)  # READY → PENDING_RESPONSE → PROCESSING → READY
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
from good_agent.agent.core import ensure_ready

# Custom agent extension
class CustomAgent(Agent):
    @ensure_ready
    async def custom_operation(self):
        """This method waits for agent to be ready."""
        return await self.call("Do something")
        
    @ensure_ready(wait_for_tasks=True, timeout=30.0)
    async def careful_operation(self):
        """Wait for agent AND any background tasks."""
        return await self.call("Critical operation")
```

**Manual readiness checking:**

```python
agent = Agent("Assistant")

# Check if ready
if agent.is_ready:
    await agent.call("Hello")
    
# Wait for readiness
await agent.initialize()  # Blocks until READY state
await agent.wait_for_ready(timeout=10.0)  # With timeout
```

### Cleanup & Resource Management

Agents manage background tasks and cleanup automatically:

```python
async with Agent("Assistant") as agent:
    # Create managed task
    task = agent.create_task(
        background_monitor(), 
        name="monitor",
        wait_on_ready=False  # Don't block initialization
    )
    
    print(f"Active tasks: {agent.task_count}")
    await agent.wait_for_tasks(timeout=5.0)  # Wait for completion
    
    # Context manager exit automatically cancels tasks
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
async with Agent("Assistant") as agent:
    agent.append("Original message")
    checkpoint = agent.version_id
    
    # Make changes
    agent.append("Unwanted message") 
    agent.append("Another change")
    
    print(f"Messages before: {len(agent)}")  # 3 messages
    
    # Revert to checkpoint (non-destructive)
    agent.revert_to_version(0)  # Version index, not version_id
    print(f"Messages after: {len(agent)}")   # 1 message
    
    # Version ID changes to indicate new state
    assert agent.version_id != checkpoint
```

!!! note "Non-Destructive Reverts"
    `revert_to_version()` doesn't delete history. It creates a new version with the content of the target version. All original messages remain accessible in the internal registry.

### Version Events

Listen for version changes:

```python
from good_agent.events import AgentEvents

@agent.on(AgentEvents.AGENT_VERSION_CHANGE) 
async def on_version_change(ctx):
    params = ctx.parameters
    print(f"Version changed: {params['old_version']} → {params['new_version']}")
    print(f"Message count: {params['changes']['messages']}")
```

## Context Management

### Dynamic Configuration

Use context managers to temporarily override agent settings:

```python
async with Agent("Assistant", temperature=0.7) as agent:
    # Normal creative temperature
    response1 = await agent.call("Write a story")
    
    # Temporarily more deterministic
    with agent.config(temperature=0.1, max_tokens=100):
        response2 = await agent.call("Summarize the above")
    
    # Back to original settings
    response3 = await agent.call("Continue the story")
```

### Context Variables & Templates

Agents support dynamic templating with context variables:

```python
async with Agent(
    "You are in {{location}} helping with {{task}}", 
    context={"location": "Paris", "task": "travel planning"}
) as agent:
    # System prompt renders as: "You are in Paris helping with travel planning"
    
    agent.append("The weather in {{location}} is {{weather}}", 
                 context={"weather": "sunny"})
    # Message renders as: "The weather in Paris is sunny"
```

**Context inheritance and scoping:**

```python
async with Agent("Base prompt", context={"env": "prod", "user": "alice"}) as agent:
    # Override context temporarily
    with agent.context(env="dev", debug=True):
        agent.append("Debug info for {{user}} in {{env}}: {{debug}}")
        # Renders: "Debug info for alice in dev: True"
    
    # Back to original context
    agent.append("User {{user}} in {{env}}")  
    # Renders: "User alice in prod"
```

### Template Functions

Register custom template functions:

```python
from datetime import datetime

@Agent.context_providers("now")
def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async with Agent("Current time is {{now}}") as agent:
    # System prompt includes current timestamp
    response = await agent.call("What time is it?")
```

## Agent Composition

### Agent Pools

Manage multiple agent instances efficiently:

```python
from good_agent.agent.pool import AgentPool

async with AgentPool(size=5, template=Agent("Worker {{id}}")) as pool:
    # Get available agent
    agent = await pool.get()
    
    try:
        result = await agent.call("Process this task")
    finally:
        await pool.put(agent)  # Return to pool
```

### Multi-Agent Workflows

Chain agents using the pipe operator:

```python
researcher = Agent("You are a researcher. Find facts.")
writer = Agent("You are a writer. Create content from facts.")
editor = Agent("You are an editor. Polish the content.")

# Pipeline composition
async with (researcher | writer | editor) as workflow:
    researcher.append("Research quantum computing")
    
    # Each agent processes the previous agent's output
    final_result = await editor.call()
```

### Thread-Safe Context Forking

Create isolated contexts for concurrent operations:

```python
async with Agent("Base agent") as agent:
    agent.append("Shared context")
    
    # Fork for parallel processing
    async with agent.fork() as fork1, agent.fork() as fork2:
        # Each fork has independent message history
        task1 = asyncio.create_task(fork1.call("Process option A"))
        task2 = asyncio.create_task(fork2.call("Process option B"))
        
        results = await asyncio.gather(task1, task2)
    
    # Original agent unchanged by fork operations
    assert len(agent) == 1  # Still just "Shared context"
```

## Advanced Patterns

### Custom Agent Classes

Extend agents with domain-specific behavior:

```python
from good_agent import Agent, tool
from good_agent.agent.core import ensure_ready

class DataAnalyst(Agent):
    def __init__(self, **config):
        super().__init__(
            "You are a data analyst expert.",
            tools=[self.analyze_data, self.create_chart],
            **config
        )
    
    @tool
    async def analyze_data(self, data: list[dict]) -> dict:
        """Analyze structured data."""
        return {"mean": sum(d["value"] for d in data) / len(data)}
    
    @tool 
    async def create_chart(self, data: dict) -> str:
        """Generate a chart description."""
        return f"Chart showing mean value: {data['mean']}"
    
    @ensure_ready
    async def analyze(self, data: list[dict]) -> str:
        """High-level analysis method."""
        self.append(f"Please analyze this data: {data}")
        return await self.call()
```

### Event-Driven Architecture

Build reactive agents with comprehensive event handling:

```python
from good_agent.events import AgentEvents

class MonitoredAgent(Agent):
    def __init__(self, **config):
        super().__init__(**config)
        self._setup_monitoring()
    
    def _setup_monitoring(self):
        @self.on(AgentEvents.AGENT_INITIALIZE)
        async def on_init(ctx):
            print(f"Agent {self.name} initialized")
        
        @self.on(AgentEvents.TOOL_CALL_BEFORE)  
        async def on_tool_start(ctx):
            tool_name = ctx.parameters["tool_name"]
            print(f"Starting tool: {tool_name}")
        
        @self.on(AgentEvents.TOOL_CALL_AFTER)
        async def on_tool_end(ctx):
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            print(f"Tool {tool_name} {'succeeded' if success else 'failed'}")
```

### Persistent State

Implement state persistence for long-running agents:

```python
import json
from pathlib import Path

class PersistentAgent(Agent):
    def __init__(self, state_file: str, **config):
        super().__init__(**config)
        self.state_file = Path(state_file)
        
    async def __aenter__(self):
        agent = await super().__aenter__()
        await self._load_state()
        return agent
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._save_state()
        return await super().__aexit__(exc_type, exc_val, exc_tb)
    
    async def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                # Reconstruct messages from saved data
                for msg_data in data.get("messages", []):
                    self._restore_message(msg_data)
    
    async def _save_state(self):
        data = {
            "session_id": str(self.session_id),
            "messages": [msg.model_dump() for msg in self.messages]
        }
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)
```

## Performance & Monitoring

### Agent Metrics

Monitor agent performance and behavior:

```python
async with Agent("Assistant") as agent:
    # Basic metrics
    print(f"Messages: {len(agent)}")
    print(f"Active tasks: {agent.task_count}")
    print(f"State: {agent.state}")
    print(f"Ready: {agent.is_ready}")
    
    # Version history
    print(f"Version count: {agent._version_manager.version_count}")
    print(f"Current version: {len(agent.current_version)} messages")
```

### Memory Management

For long-running agents, manage message history:

```python
async with Agent("Long-running assistant") as agent:
    # After many interactions...
    if len(agent) > 1000:
        # Keep only recent messages
        recent_messages = agent.messages[-100:]
        
        # Create new agent with recent context
        new_agent = Agent(
            agent[0].content,  # Keep system prompt
            context=agent.context._data.copy()
        )
        
        # Transfer recent messages
        for msg in recent_messages:
            new_agent.append(msg.content, role=msg.role)
```

### Debugging & Introspection

Debug agent behavior with built-in tools:

```python
async with Agent("Assistant", debug=True, print_messages=True) as agent:
    # Enable detailed logging
    agent.config.litellm_debug = True
    agent.config.print_messages_mode = "raw"  # Show raw LLM messages
    
    # Inspect internal state
    print("=== Agent State ===")
    print(f"State: {agent.state}")
    print(f"Version: {agent.version_id}")
    print(f"Messages: {len(agent)}")
    
    # View message history  
    for i, msg in enumerate(agent.messages):
        print(f"{i}: {msg.role} - {msg.content[:50]}...")
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
# ❌ Not waiting for initialization
agent = Agent("Assistant") 
await agent.call("Hello")  # May fail if not ready

# ✅ Proper initialization
async with Agent("Assistant") as agent:
    await agent.call("Hello")
    
# ✅ Manual initialization with error handling
agent = Agent("Assistant")
try:
    await agent.initialize(timeout=10.0)
    await agent.call("Hello")
except TimeoutError:
    print("Agent failed to initialize")
finally:
    await agent.close()
```

### State Machine Errors

```python
# Check current state before operations
if agent.state == AgentState.READY:
    await agent.call("Hello")
else:
    print(f"Agent not ready: {agent.state}")
    await agent.wait_for_ready()
```

### Memory Issues

```python
# Monitor agent size
print(f"Agent has {len(agent)} messages")
print(f"Version count: {agent._version_manager.version_count}")

# Clean up if needed
if len(agent) > 1000:
    # Implement message pruning strategy
    pass
```

### Context Problems

```python
# Check context resolution
print("Current context:", dict(agent.context))

# Debug template rendering
agent.append("Test {{undefined_var}}")  # May warn about undefined variables
```

## Next Steps

- **[Messages & History](messages.md)** - Deep dive into message management and history
- **[Tools](tools.md)** - Add capabilities to your agents with function calling  
- **[Events](events.md)** - Build reactive agents with event-driven architecture
- **[Agent Modes](../features/modes.md)** - Dynamic behavior switching and scoped contexts
