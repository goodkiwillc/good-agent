# Agent Components

Good Agent provides a powerful component-based extension system that enables modular, reusable functionality. Components can register tools, handle events, inject content into messages, and integrate seamlessly with the agent lifecycle.

## Component Architecture

### AgentComponent Base Class

All components extend `AgentComponent`, which provides the foundation for extensible agent functionality:

--8<-- "src/good_agent/core/components/component.py:56:69"

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

## Creating Custom Components

### Basic Component Structure

```python
from good_agent import AgentComponent, tool
from good_agent.core.event_router import on
from good_agent.events import AgentEvents

class SearchComponent(AgentComponent):
    """Example component with tools and event handling."""
    
    def __init__(self):
        super().__init__()
        self.search_history = []  # Component state
        self.cache = {}
    
    @tool
    async def search(self, query: str, limit: int = 10) -> list[str]:
        """Search for information and return results."""
        # Access component state
        self.search_history.append(query)
        
        # Access agent reference
        context = self.agent.context
        
        # Check cache
        if query in self.cache:
            return self.cache[query][:limit]
        
        # Perform search (implementation details omitted)
        results = await self._perform_search(query, limit)
        self.cache[query] = results
        
        return results
    
    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    def track_queries(self, ctx):
        """Track search-related messages."""
        message = ctx.parameters["message"]
        if "search" in message.content.lower():
            print(f"Search-related message: {message.content}")
    
    async def install(self, agent: Agent):
        """Initialize the component with the agent."""
        await super().install(agent)
        print(f"SearchComponent installed with {len(self.agent.tools)} total tools")
    
    async def _perform_search(self, query: str, limit: int) -> list[str]:
        """Internal search implementation."""
        # Mock search results
        return [f"Result {i} for '{query}'" for i in range(1, limit + 1)]

# Usage
async with Agent(
    "You are a research assistant.",
    extensions=[SearchComponent()]
) as agent:
    
    response = await agent.call("Search for Python async patterns")
    # Component's search tool will be used automatically
```

### Component Tools

Components can define tools that are automatically registered with the agent:

--8<-- "tests/unit/components/test_component_tools.py:27:65"

**Tool Registration Process:**

1. `@tool` decorator creates `BoundTool` descriptor
2. `AgentComponentType` metaclass collects tools in `_component_tools`
3. Tools registered automatically during `install()` phase
4. Tools have access to component state via `self`
5. Tools can access agent via `self.agent`

### Advanced Tool Configuration

```python
class AdvancedComponent(AgentComponent):
    
    @tool(name="custom_search", hide=["api_key"])
    async def search_with_auth(
        self, 
        query: str, 
        api_key: str = "default_key"
    ) -> dict:
        """Search with authentication (API key hidden from LLM)."""
        # Hidden parameters don't appear in tool schema but are still accessible
        return await self._authenticated_search(query, api_key)
    
    @tool(description="Advanced search with retry logic")
    async def robust_search(self, query: str) -> str:
        """Search with automatic retry on failure."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                result = await self._risky_search(query)
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    return f"Search failed after {max_retries} attempts: {e}"
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return "Search failed"
    
    @tool
    def get_search_stats(self) -> dict:
        """Get search component statistics."""
        return {
            "total_searches": len(self.search_history),
            "cache_size": len(self.cache),
            "component_enabled": self.enabled
        }
```

## Event System Integration

Components can subscribe to and emit events for sophisticated agent orchestration:

```python
class EventDrivenComponent(AgentComponent):
    
    def setup(self, agent: Agent):
        """Register event handlers during synchronous setup."""
        super().setup(agent)
        
        # Setup is called early, so we can register handlers
        # that need to be active during agent initialization
    
    @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
    def on_message_added(self, ctx):
        """React to new messages with high priority."""
        message = ctx.parameters["message"]
        print(f"New message: {message.role} - {message.content[:50]}...")
    
    @on(AgentEvents.TOOL_CALL_BEFORE)
    async def before_tool_execution(self, ctx):
        """Intercept tool calls before execution."""
        tool_name = ctx.parameters["tool_name"]
        parameters = ctx.parameters["parameters"]
        
        # Add logging, validation, or parameter modification
        print(f"About to call {tool_name} with {parameters}")
        
        # Modify parameters if needed
        if tool_name == "search" and "limit" not in parameters:
            ctx.parameters["parameters"]["limit"] = 5
    
    @on(AgentEvents.TOOL_CALL_AFTER)
    async def after_tool_execution(self, ctx):
        """React to tool execution results."""
        tool_name = ctx.parameters["tool_name"]
        response = ctx.parameters["response"]
        
        # Log results, cache responses, trigger follow-up actions
        if response.success:
            print(f"Tool {tool_name} succeeded: {response.response[:100]}")
        else:
            print(f"Tool {tool_name} failed: {response.error}")
    
    async def emit_custom_event(self, data: dict):
        """Emit custom events to other components."""
        await self.agent.apply("custom:search_completed", {
            "component_id": id(self),
            "timestamp": time.time(),
            **data
        })
```

## Built-in Components

Good Agent includes several built-in components for common functionality:

### TaskManager Component

Provides todo list management with agent tool integration:

```python
from good_agent.extensions import TaskManager

async with Agent(
    "Task coordinator", 
    extensions=[TaskManager()]
) as agent:
    
    # Agent can now create and manage todo lists
    await agent.call("Create a project list with 3 development tasks")
    
    # Access component directly
    task_manager = agent[TaskManager]
    print(f"Created {len(task_manager.lists)} lists")
```

### MessageInjectorComponent

Base class for components that inject content into messages:

--8<-- "src/good_agent/core/components/injection.py:16:42"

```python
from good_agent import MessageInjectorComponent
from good_agent.content import TextContentPart

class ContextComponent(MessageInjectorComponent):
    
    def get_system_prompt_prefix(self, agent: Agent) -> list[ContentPartType]:
        """Add context to the beginning of system prompts."""
        return [TextContentPart(text="Current environment: production")]
    
    def get_user_message_suffix(self, agent: Agent, message: UserMessage) -> list[ContentPartType]:
        """Add timestamp to user messages."""
        timestamp = datetime.now().isoformat()
        return [TextContentPart(text=f"\n\n[Timestamp: {timestamp}]")]
```

### CitationManager Component

Manages citations and references in agent responses:

```python
from good_agent.extensions import CitationManager

async with Agent(
    "Research assistant",
    extensions=[CitationManager()]
) as agent:
    
    # Component automatically manages citations in responses
    response = await agent.call("Tell me about Python async programming")
    
    # Access citation data
    citation_manager = agent[CitationManager]
    citations = citation_manager.get_all_citations()
```

### AgentSearch Component

Provides semantic search capabilities within agent conversations:

```python
from good_agent.extensions import AgentSearch

async with Agent(
    "Knowledge assistant",
    extensions=[AgentSearch()]
) as agent:
    
    # Component enables semantic search across message history
    await agent.call("What did we discuss about databases earlier?")
```

## Component Dependencies

Components can declare dependencies on other components:

```python
class DatabaseComponent(AgentComponent):
    """Component that provides database access."""
    
    @tool
    async def query_db(self, sql: str) -> list[dict]:
        """Execute a database query."""
        return await self._execute_query(sql)

class AnalyticsComponent(AgentComponent):
    """Component that depends on DatabaseComponent."""
    
    __depends__ = ["DatabaseComponent"]  # Declare dependency
    
    async def install(self, agent: Agent):
        await super().install(agent)
        
        # Access dependency
        db_component = self.get_dependency(DatabaseComponent)
        if db_component:
            print("Database component available")
        else:
            raise RuntimeError("DatabaseComponent required but not found")
    
    @tool
    async def analyze_data(self, table: str) -> dict:
        """Analyze data from a database table."""
        db = self.get_dependency(DatabaseComponent)
        
        if not db:
            return {"error": "Database component not available"}
        
        # Use dependency's tools
        data = await db.query_db(f"SELECT * FROM {table}")
        return self._analyze(data)

# Usage - order matters when dependencies exist
agent = Agent(
    "Data analyst",
    extensions=[
        DatabaseComponent(),      # Must come first
        AnalyticsComponent()      # Depends on DatabaseComponent
    ]
)
```

## Component State Management

### Enable/Disable Components

```python
class ToggleableComponent(AgentComponent):
    
    @tool
    def process_data(self, data: str) -> str:
        """Process data if component is enabled."""
        if not self.enabled:
            return "Component is disabled"
        
        return f"Processed: {data.upper()}"

# Usage
component = ToggleableComponent()
agent = Agent("Assistant", extensions=[component])
await agent.initialize()

# Tools are available when enabled
result = await agent.tools["process_data"](_agent=agent, data="test")
print(result.response)  # "Processed: TEST"

# Disable component - tools become unavailable
component.enabled = False
print(f"Tool available: {'process_data' in agent.tools}")  # False

# Re-enable component
component.enabled = True
print(f"Tool available: {'process_data' in agent.tools}")  # True
```

### Component Cloning

Components support cloning for creating independent instances:

```python
class StatefulComponent(AgentComponent):
    def __init__(self, initial_value: int = 0):
        super().__init__()
        self.value = initial_value
    
    def _clone_init_args(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Provide arguments for clone construction."""
        return (), {"initial_value": self.value}
    
    @tool
    def increment(self) -> int:
        """Increment the component's value."""
        self.value += 1
        return self.value

# Create and clone component
original = StatefulComponent(initial_value=10)
clone = original.clone()

# Clone is independent
original.value = 20
print(f"Original: {original.value}, Clone: {clone.value}")  # Original: 20, Clone: 10
```

## Tool Adapters

Components can use tool adapters to modify tool behavior transparently:

```python
from good_agent import ToolAdapter

class LoggingAdapter(ToolAdapter):
    """Adapter that logs all tool calls."""
    
    def should_adapt(self, tool_name: str, agent: Agent) -> bool:
        """Apply to all tools."""
        return True
    
    async def adapt_parameters(
        self, 
        tool_name: str, 
        parameters: dict, 
        agent: Agent
    ) -> dict:
        """Log parameters before tool execution."""
        print(f"Calling {tool_name} with {parameters}")
        return parameters
    
    async def adapt_response(
        self, 
        tool_name: str, 
        response: ToolResponse, 
        agent: Agent
    ) -> ToolResponse:
        """Log response after tool execution."""
        print(f"Tool {tool_name} returned: {response.response}")
        return response

class AdapterComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        # Register the adapter
        self.register_tool_adapter(LoggingAdapter())
    
    @tool
    def example_tool(self, data: str) -> str:
        """Example tool that will be logged."""
        return f"Processed: {data}"

# Tool calls will now be logged automatically
agent = Agent("Assistant", extensions=[AdapterComponent()])
```

## Testing Components

### Unit Testing Component Tools

```python
import pytest
from good_agent import Agent, AgentComponent, tool

class TestableComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.call_count = 0
    
    @tool
    async def test_tool(self, value: str) -> str:
        """A tool for testing."""
        self.call_count += 1
        return f"Called {self.call_count} times with '{value}'"

@pytest.mark.asyncio
async def test_component_tool_registration():
    """Test that component tools are registered correctly."""
    component = TestableComponent()
    agent = Agent("Test agent", extensions=[component])
    await agent.initialize()
    
    # Tool should be registered
    assert "test_tool" in agent.tools
    
    # Tool should work
    result = await agent.tools["test_tool"](_agent=agent, value="test")
    assert result.success
    assert "Called 1 times" in result.response
    
    # Component state should be updated
    assert component.call_count == 1

@pytest.mark.asyncio
async def test_component_enable_disable():
    """Test component enable/disable functionality."""
    component = TestableComponent()
    agent = Agent("Test agent", extensions=[component])
    await agent.initialize()
    
    # Initially enabled
    assert component.enabled
    assert "test_tool" in agent.tools
    
    # Disable component
    component.enabled = False
    assert "test_tool" not in agent.tools
    
    # Re-enable component
    component.enabled = True
    assert "test_tool" in agent.tools
```

### Integration Testing with Events

```python
@pytest.mark.asyncio
async def test_component_event_handling():
    """Test component event handling."""
    events_received = []
    
    class EventTestComponent(AgentComponent):
        @on(AgentEvents.MESSAGE_APPEND_AFTER)
        def track_messages(self, ctx):
            events_received.append(ctx.parameters["message"].content)
    
    agent = Agent("Test", extensions=[EventTestComponent()])
    await agent.initialize()
    
    # Add messages
    agent.append("Hello")
    agent.append("World")
    
    # Events should have been received
    assert len(events_received) == 2
    assert "Hello" in events_received
    assert "World" in events_received
```

### Mocking Component Dependencies

```python
from unittest.mock import Mock

@pytest.mark.asyncio
async def test_component_with_mocked_dependency():
    """Test component with mocked external dependencies."""
    
    class ExternalServiceComponent(AgentComponent):
        def __init__(self, service_client=None):
            super().__init__()
            self.service_client = service_client or self._create_client()
        
        def _create_client(self):
            # In real code, this would create actual service client
            return Mock()
        
        @tool
        async def call_service(self, data: str) -> str:
            """Call external service."""
            result = await self.service_client.call_api(data)
            return f"Service returned: {result}"
    
    # Create component with mocked client
    mock_client = Mock()
    mock_client.call_api.return_value = "mocked_response"
    
    component = ExternalServiceComponent(service_client=mock_client)
    agent = Agent("Test", extensions=[component])
    await agent.initialize()
    
    # Test tool with mock
    result = await agent.tools["call_service"](_agent=agent, data="test")
    assert "mocked_response" in result.response
    
    # Verify mock was called
    mock_client.call_api.assert_called_once_with("test")
```

## Best Practices

### 1. Design for Reusability

```python
class ConfigurableComponent(AgentComponent):
    """Component with flexible configuration."""
    
    def __init__(self, api_key: str, timeout: float = 30.0, retries: int = 3):
        super().__init__()
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
    
    def _clone_init_args(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        return (), {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "retries": self.retries
        }
```

### 2. Handle Errors Gracefully

```python
class RobustComponent(AgentComponent):
    
    @tool
    async def reliable_operation(self, data: str) -> str:
        """Operation with comprehensive error handling."""
        try:
            if not self.enabled:
                return "Component is disabled"
            
            if not data.strip():
                return "Error: Empty data provided"
            
            result = await self._risky_operation(data)
            return f"Success: {result}"
            
        except ConnectionError:
            return "Error: Service unavailable, please try again later"
        except ValueError as e:
            return f"Error: Invalid data format - {e}"
        except Exception as e:
            # Log unexpected errors but don't crash
            logger.error(f"Unexpected error in {self.__class__.__name__}: {e}")
            return "Error: Internal component error"
```

### 3. Use Dependency Injection

```python
from abc import ABC, abstractmethod

class StorageInterface(ABC):
    @abstractmethod
    async def save(self, key: str, data: dict) -> bool:
        pass

class TestableComponent(AgentComponent):
    def __init__(self, storage: StorageInterface | None = None):
        super().__init__()
        self.storage = storage or self._create_default_storage()
    
    def _create_default_storage(self) -> StorageInterface:
        """Create default storage implementation."""
        return FileStorage()  # Default implementation
    
    @tool
    async def save_data(self, key: str, data: dict) -> str:
        """Save data using injected storage."""
        success = await self.storage.save(key, data)
        return "Saved successfully" if success else "Save failed"
```

### 4. Implement Proper Logging

```python
import logging

class LoggingComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def install(self, agent: Agent):
        await super().install(agent)
        self.logger.info(f"Component installed on agent {agent.name}")
    
    @tool
    async def logged_operation(self, data: str) -> str:
        """Operation with comprehensive logging."""
        self.logger.debug(f"Starting operation with data: {data[:50]}...")
        
        try:
            result = await self._perform_operation(data)
            self.logger.info(f"Operation completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Operation failed: {e}", exc_info=True)
            raise
```

### 5. Document Component APIs

```python
class WellDocumentedComponent(AgentComponent):
    """
    A well-documented component for demonstration.
    
    This component provides example functionality and serves as a template
    for creating new components with proper documentation.
    
    Attributes:
        config (dict): Component configuration
        state (str): Current component state
        
    Example:
        >>> component = WellDocumentedComponent(config={"key": "value"})
        >>> agent = Agent("Assistant", extensions=[component])
        >>> await agent.initialize()
    """
    
    def __init__(self, config: dict | None = None):
        """
        Initialize the component.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__()
        self.config = config or {}
        self.state = "initialized"
    
    @tool
    async def documented_tool(self, input_data: str, format_type: str = "json") -> str:
        """
        Process input data and return formatted result.
        
        This tool demonstrates proper documentation with clear parameter
        descriptions and return value documentation.
        
        Args:
            input_data: The data to process (required)
            format_type: Output format - "json", "xml", or "text" (default: "json")
            
        Returns:
            Formatted string containing the processed data
            
        Raises:
            ValueError: If format_type is not supported
            
        Example:
            The agent can call this tool like:
            "Process this data: 'hello world' in XML format"
        """
        if format_type not in ["json", "xml", "text"]:
            raise ValueError(f"Unsupported format: {format_type}")
        
        # Implementation details...
        return f"Processed '{input_data}' as {format_type}"
```

Agent components provide a powerful foundation for building modular, reusable, and testable agent functionality. The system's event-driven architecture, automatic tool registration, and lifecycle management make it easy to create sophisticated agent extensions while maintaining clean separation of concerns.
