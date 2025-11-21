# Agent Components

Good Agent provides a powerful component-based extension system that enables modular, reusable functionality. Components can register tools, handle events, inject content into messages, and integrate seamlessly with the agent lifecycle.

## Component Architecture

### AgentComponent Base Class

All components extend `AgentComponent`, which provides the foundation for extensible agent functionality:

```python
--8<-- "src/good_agent/core/components/component.py:56:69"
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
