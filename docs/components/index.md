# Agent Components

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent provides a powerful component-based extension system that enables modular, reusable functionality. Components can register tools, handle events, inject content into messages, and integrate seamlessly with the agent lifecycle.

## Component Architecture

### AgentComponent Base Class

All components extend `AgentComponent`, which provides the foundation for extensible agent functionality:

```python
from good_agent import AgentComponent, tool

class MyComponent(AgentComponent):
    """Example component showing core capabilities."""

    def __init__(self):
        super().__init__()
        self.state = {}  # Component-specific state

    @tool
    async def my_tool(self, query: str) -> str:
        """Tools are automatically registered with the agent."""
        return f"Processed: {query}"

    async def install(self, agent):
        """Lifecycle hook for initialization."""
        await super().install(agent)
        # Initialize resources, connect to services, etc.
        print(f"Component installed on {agent.name}")

# Usage
agent = Agent("Assistant", extensions=[MyComponent()])

# Type-safe access to component instance
agent[MyComponent].state['initialized'] = True

```

**Core Capabilities:**

- **Event-driven integration** via EventRouter
- **Tool registration** with automatic binding to component instances
- **Lifecycle management** with setup and install phases
- **State management** with enable/disable support
- **Dependency resolution** between components
- **Tool adaptation** for transparent parameter/response transformation

### Component Lifecycle

Components progress through a defined lifecycle during agent initialization:

```python
from good_agent import Agent, AgentComponent

class MyComponent(AgentComponent):
    async def install(self, agent: Agent):
        """Async initialization - register tools, load resources"""
        await super().install(agent)
        # Custom initialization logic
        print("Component installed successfully")

# Component lifecycle during agent creation
component = MyComponent()
agent = Agent("System prompt", extensions=[component])

# 1. Synchronous setup - called immediately during registration
#    - Sets agent reference
#    - Registers event handlers
#
# 2. Async installation - called during agent.initialize()
#    - Registers component tools
#    - Loads resources, connects to services
#
# 3. Runtime operation - component is active and responding to events

await agent.initialize()  # Component now fully active
```

**Lifecycle Phases:**

1. **Setup** (sync): Agent reference setup, early event handler registration
2. **Install** (async): Tool registration, resource initialization, service connections
3. **Runtime**: Event handling, tool execution, content injection
