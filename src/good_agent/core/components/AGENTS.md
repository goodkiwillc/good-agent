# AgentComponents Architecture

## Overview

The AgentComponents system provides a powerful, extensible architecture for creating modular agent functionality. Components can register tools, handle events, inject content into messages, adapt tool behavior, and integrate seamlessly with the agent lifecycle.

## Core Architecture

### AgentComponent Base Class

All components extend `AgentComponent`, which provides:

- **Event-driven integration** via EventRouter
- **Tool registration** with automatic binding to component instances
- **Lifecycle management** with setup and install phases
- **State management** with enable/disable support
- **Dependency resolution** between components
- **Tool adaptation** for transparent parameter/response transformation

### Component Lifecycle

```python
# 1. Component creation
component = MyComponent()

# 2. Synchronous setup - called during agent registration
component.setup(agent)  # Set agent reference, register early event handlers

# 3. Async installation - called during agent initialization
await component.install(agent)  # Register tools, initialize resources

# 4. Runtime operation - components are now active and responding to events
```

**Key Phases:**

1. **Setup** (sync): Agent reference setup, early event handler registration
2. **Install** (async): Tool registration, resource initialization, service connections
3. **Runtime**: Event handling, tool execution, message injection

### Component Registration

```python
# Register components as extensions during agent creation
agent = Agent(
    "System prompt",
    extensions=[
        MyComponent(),
        AnotherComponent(config="value")
    ]
)
```

## Core Features

### 1. Component-Bound Tools

Components can define tools that are automatically bound to the component instance:

```python
from good_agent import AgentComponent, tool

class SearchComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.search_history = []  # Component state

    @tool
    async def search(self, query: str, limit: int = 10) -> list[str]:
        """Search for information."""
        # Access component state via self
        self.search_history.append(query)

        # Access agent via self.agent
        context = self.agent.context

        # Perform search logic
        results = await self._perform_search(query, limit)
        return results

    @tool(name="custom_search", hide=["api_key"])
    async def advanced_search(self, query: str, api_key: str = "default") -> dict:
        """Advanced search with custom configuration."""
        # Hidden parameters still accessible but not shown in LLM schema
        return await self._advanced_search(query, api_key)
```

**Tool Binding Process:**
- `@tool` decorator detects methods (functions with 'self' parameter)
- Creates `BoundTool` descriptor that stores unbound method
- `AgentComponentType` metaclass collects tool descriptors in `_component_tools`
- Tools registered automatically after agent initialization via `AGENT_INIT_AFTER` event

### 2. Event System Integration

Components can subscribe to and emit events:

```python
class EventComponent(AgentComponent):
    def setup(self, agent: Agent):
        """Register event handlers during setup."""
        super().setup(agent)

        # Subscribe to agent events
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def handle_tool_result(ctx):
            tool_name = ctx.parameters.get("tool_name")
            response = ctx.parameters.get("response")
            # Process tool result

        # Subscribe to custom events
        @agent.on("custom:event")
        def handle_custom(ctx):
            data = ctx.parameters.get("data")
            # Handle custom event

    async def my_method(self):
        # Emit events
        await self.agent.apply("custom:event", data={"key": "value"})
```

### 3. Message Injection System

Components can inject content into system prompts and user messages at runtime:

```python
from good_agent.components import MessageInjectorComponent
from good_agent.content import TextContentPart, TemplateContentPart

class ContextInjector(MessageInjectorComponent):
    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id

    def get_system_prompt_prefix(self, agent) -> list[ContentPartType]:
        """Inject session context at start of system prompt."""
        return [
            TextContentPart(text=f"Session ID: {self.session_id}\n"),
            TemplateContentPart(template="Current time: {{ timestamp }}")
        ]

    def get_user_message_suffix(self, agent, message) -> list[ContentPartType]:
        """Add context to end of user messages."""
        if "help" in str(message.content).lower():
            return [TextContentPart(text="\n(User requested help)")]
        return []

# Or use SimpleMessageInjector for basic text injection
injector = SimpleMessageInjector(
    system_prefix="[CONTEXT] ",
    system_suffix=" [END]",
    user_suffix="\nPlease be detailed.",
    use_templates=True  # Detect {{ }} template syntax
)
```

**Injection Architecture:**
- System prompts: Modified via `MESSAGE_SET_SYSTEM_AFTER` event (messages replaced due to frozen models)
- User messages: Modified via `MESSAGE_RENDER_BEFORE` event (non-destructive, affects rendering only)
- Full template support with agent context access
- Runtime enable/disable via `component.enabled` property

### 4. Tool Adapter System

Components can transparently modify tool behavior without changing tool implementations:

```python
from good_agent.components import ToolAdapter, AgentComponent

class CitationAdapter(ToolAdapter):
    """Transform URL parameters to citation indices for token efficiency."""

    def __init__(self, component):
        super().__init__(component)
        self.citations = []  # URL to index mapping

    def should_adapt(self, tool, agent):
        """Only adapt tools with URL parameters."""
        schema = tool.model.model_json_schema()
        properties = schema.get("properties", {})
        return any("url" in k.lower() for k in properties)

    def adapt_signature(self, tool, signature, agent):
        """Replace url: str with citation_idx: int in LLM schema."""
        import copy
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]

        if "url" in params:
            params["citation_idx"] = {
                "type": "integer",
                "description": "Citation index (0-based)",
                "minimum": 0
            }
            del params["url"]
        return adapted

    def adapt_parameters(self, tool_name, parameters, agent):
        """Convert citation index back to URL before tool execution."""
        adapted = dict(parameters)
        if "citation_idx" in adapted:
            idx = adapted.pop("citation_idx")
            if 0 <= idx < len(self.citations):
                adapted["url"] = self.citations[idx]
        return adapted

class CitationComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.adapter = CitationAdapter(self)

    async def install(self, agent):
        await super().install(agent)
        self.register_tool_adapter(self.adapter)
```

For detailed tool adapter documentation, see [TOOL_ADAPTER.md](TOOL_ADAPTER.md).

### 5. Dependency Resolution

Components can access other installed components:

```python
class IntegratedComponent(AgentComponent):
    """Component that integrates with other components."""

    def __init__(self):
        super().__init__()
        # Don't declare explicit dependencies - use integration patterns instead

    async def my_tool(self, query: str) -> str:
        # Access other components via type lookup
        search_component = self.get_dependency(SearchComponent)
        if search_component:
            # Use other component's functionality
            results = await search_component.search(query)
            return f"Found {len(results)} results"
        return "Search not available"

    def setup(self, agent):
        super().setup(agent)

        # Better pattern: Listen to tool events for integration
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def handle_search_results(ctx):
            tool_name = ctx.parameters.get("tool_name")
            if tool_name == "search":
                result = ctx.parameters.get("response")
                # Process search results from any component
                self._process_search_result(result)
```

**Best Practice:** Use event-based integration rather than explicit dependencies for loose coupling.

## Component Examples

### Basic Component

```python
from good_agent import AgentComponent, tool

class BasicComponent(AgentComponent):
    """Minimal component example."""

    def __init__(self, config_value: str = "default"):
        super().__init__()
        self.config_value = config_value

    @tool
    async def basic_tool(self, input_value: str) -> str:
        """A simple tool that processes input."""
        return f"Processed '{input_value}' with config '{self.config_value}'"

    async def install(self, agent):
        """Install component on agent."""
        await super().install(agent)
        # Additional setup if needed
```

### Advanced Multi-Feature Component

```python
class AdvancedComponent(MessageInjectorComponent):
    """Component demonstrating multiple features."""

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.request_count = 0

        # Set up tool adapter
        self.auth_adapter = AuthAdapter(self, api_key)

    async def install(self, agent):
        await super().install(agent)

        # Register tool adapter
        self.register_tool_adapter(self.auth_adapter)

    @tool(hide=["api_key"])
    async def api_call(self, endpoint: str, data: dict, api_key: str = None) -> dict:
        """Make authenticated API call."""
        # Use injected API key if not provided
        key = api_key or self.api_key
        self.request_count += 1

        # Make API call logic here
        return {"status": "success", "endpoint": endpoint, "count": self.request_count}

    def get_system_prompt_suffix(self, agent) -> list[ContentPartType]:
        """Inject API usage stats into system prompt."""
        return [
            TextContentPart(text=f"\nAPI requests made: {self.request_count}")
        ]

    def setup(self, agent):
        super().setup(agent)

        # Listen to tool execution for tracking
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def track_tool_usage(ctx):
            tool_name = ctx.parameters.get("tool_name")
            if tool_name == "api_call":
                # Track API usage
                pass
```

## Testing Components

### Basic Component Testing

```python
import pytest
from good_agent import Agent

@pytest.mark.asyncio
async def test_component_functionality():
    component = BasicComponent("test_config")

    async with Agent("Test", extensions=[component]) as agent:
        # Test tool registration
        assert "basic_tool" in agent.tools

        # Test tool execution
        tool = agent.tools["basic_tool"]
        result = await tool(_agent=agent, input_value="test")
        assert result.success
        assert "test" in result.response
        assert "test_config" in result.response

@pytest.mark.asyncio
async def test_component_integration():
    """Test component integration with agent."""
    component = BasicComponent()

    async with Agent("Test", extensions=[component]) as agent:
        # Test via natural language (if auto_execute_tools=True)
        response = await agent.call("Use basic_tool with input 'hello'")
        # Agent should use the tool automatically

        # Or test direct invocation
        result = await agent.invoke('basic_tool', input_value='hello')
        assert result == "Processed 'hello' with config 'default'"
```

### Testing Message Injection

```python
@pytest.mark.asyncio
async def test_message_injection():
    injector = SimpleMessageInjector(
        system_prefix="[PREFIX] ",
        user_suffix=" [SUFFIX]"
    )

    async with Agent("Base prompt", extensions=[injector]) as agent:
        # Check system message injection
        system_msg = agent.messages[0]  # First message is system
        content = await system_msg.render(RenderMode.LLM)
        assert content.startswith("[PREFIX] Base prompt")

        # Check user message injection
        agent.append("Test message")
        user_msg = agent.messages[-1]
        content = await user_msg.render(RenderMode.LLM)
        assert content.endswith(" [SUFFIX]")
```

### Testing Tool Adapters

```python
@pytest.mark.asyncio
async def test_tool_adapter():
    component = ComponentWithAdapter()

    async with Agent("Test", tools=[url_tool], extensions=[component]) as agent:
        # Adapter should modify tool signature
        signatures = agent._generate_tool_signatures()
        url_sig = next(s for s in signatures if s["function"]["name"] == "url_tool")

        # Should have citation_idx instead of url
        params = url_sig["function"]["parameters"]["properties"]
        assert "citation_idx" in params
        assert "url" not in params

        # Test parameter adaptation
        # (Would need to mock LLM response with citation_idx)
```

## Best Practices

### 1. Component Design

- **Single Responsibility**: Each component should have a focused purpose
- **Loose Coupling**: Use events for integration rather than explicit dependencies
- **State Management**: Keep component state in the component, not in adapters
- **Error Handling**: Handle failures gracefully and provide meaningful error messages

### 2. Tool Registration

- **Type Hints**: Always provide complete type annotations for tools
- **Documentation**: Include docstrings for all tools
- **Parameter Validation**: Use Pydantic models for complex parameters
- **Hidden Parameters**: Use `hide=[]` to exclude sensitive parameters from LLM schemas

### 3. Event Handling

- **Use Enum Constants**: Always use `AgentEvents.*` constants, not string literals
- **Handler Parameters**: Event handlers receive `EventContext`, extract data via `ctx.parameters`
- **Event Timing**: Use appropriate event phases (BEFORE/AFTER) for your use case
- **Priority**: Set handler priority when order matters

### 4. Message Injection

- **Performance**: Only inject when necessary (check conditions first)
- **Template Context**: Injected templates have access to full agent context
- **Content Parts**: Use appropriate content part types (Text vs Template)
- **Enable State**: Respect `component.enabled` for runtime control

### 5. Tool Adaptation

- **Metadata**: Always implement `analyze_transformation()` for conflict detection
- **Reversibility**: Ensure parameter transformations are bidirectional
- **Error Handling**: Handle invalid parameters gracefully
- **State Management**: Store adapter state in the parent component

## Component Integration Patterns

### Event-Based Integration

**Preferred pattern** for component communication:

```python
class ProducerComponent(AgentComponent):
    """Component that produces data."""

    @tool
    async def fetch_data(self, url: str) -> dict:
        data = await self._fetch(url)

        # Emit event for other components
        await self.agent.apply("data:fetched", data=data, url=url)

        return data

class ConsumerComponent(AgentComponent):
    """Component that consumes data from other components."""

    def setup(self, agent):
        super().setup(agent)

        # Listen for data events
        @agent.on("data:fetched")
        def handle_data(ctx):
            data = ctx.parameters.get("data")
            url = ctx.parameters.get("url")
            # Process data from any producer
            self._process_data(data, url)
```

### Tool Hook Integration

For processing tool results from other components:

```python
class IntegrationComponent(AgentComponent):
    """Component that enhances other components via tool hooks."""

    def setup(self, agent):
        super().setup(agent)

        # Hook into all tool executions
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def enhance_tool_results(ctx):
            tool_name = ctx.parameters.get("tool_name")
            response = ctx.parameters.get("response")

            # Enhance specific tool types
            if tool_name in ["search", "fetch"]:
                enhanced = self._enhance_result(response)
                # Could modify ctx.parameters["response"] if needed
```

### Context Provider Integration

Share data via agent context:

```python
class ContextProviderComponent(AgentComponent):
    """Component that provides dynamic context."""

    async def install(self, agent):
        await super().install(agent)

        # Register context providers
        @agent.template.context_provider("session_info")
        def get_session_info():
            return {
                "id": self.session_id,
                "start_time": self.start_time.isoformat(),
                "request_count": self.request_count
            }

# Other components can access via templates:
# "Session {{session_info.id}} started at {{session_info.start_time}}"
```

## Summary

The AgentComponents architecture provides a comprehensive system for building modular, extensible agents. Key benefits:

- **Modularity**: Components can be developed and tested independently
- **Extensibility**: Multiple integration patterns (tools, events, injection, adaptation)
- **Type Safety**: Full type annotations and validation throughout
- **Lifecycle Management**: Proper setup and teardown with state management
- **Event-Driven**: Loose coupling through comprehensive event system

Use components when you need to:
- Add tools to agents
- Modify agent behavior (message injection)
- Transform tool parameters or responses (adaptation)
- Integrate with external services
- Share functionality across multiple agents
- Create reusable agent extensions
