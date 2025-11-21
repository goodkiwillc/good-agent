# Tool Adapter Pattern - AgentComponents

## Overview

The Tool Adapter pattern allows AgentComponents to transparently intercept and modify tool behavior without changing the original tool implementations. This enables powerful use cases like parameter transformation, authentication injection, caching, and citation management.

## Architecture

### Core Components

1. **ToolAdapter**: Base class for creating adapters
2. **ToolAdapterRegistry**: Manages multiple adapters and conflict resolution
3. **AgentComponent Integration**: Built-in support via `register_tool_adapter()`

### How It Works

The adapter system hooks into three key events in the tool lifecycle:

1. **TOOLS_GENERATE_SIGNATURE**: Modifies tool signatures before sending to LLM
2. **TOOL_CALL_BEFORE**: Transforms parameters from LLM before tool execution
3. **TOOL_CALL_AFTER**: Optionally modifies tool responses

## Creating a Tool Adapter

### Basic Structure

```python
from good_agent.components import AgentComponent, ToolAdapter
from good_agent.components import AdapterMetadata

class MyAdapter(ToolAdapter):
    """Custom adapter for modifying tool behavior."""
    
    def should_adapt(self, tool, agent):
        """Determine if this adapter applies to the tool."""
        # Return True if this adapter should modify the tool
        return "specific_param" in tool.name
    
    def analyze_transformation(self, tool, signature):
        """Analyze what transformations will be performed."""
        # Used for conflict detection
        return AdapterMetadata(
            modified_params={"param1"},
            added_params={"new_param"},
            removed_params={"old_param"}
        )
    
    def adapt_signature(self, tool, signature, agent):
        """Transform the tool signature for the LLM."""
        import copy
        adapted = copy.deepcopy(signature)
        # Modify the signature here
        params = adapted["function"]["parameters"]["properties"]
        params["new_param"] = {
            "type": "string",
            "description": "New parameter"
        }
        return adapted
    
    def adapt_parameters(self, tool_name, parameters, agent):
        """Transform parameters from LLM to original format."""
        adapted = dict(parameters)
        # Transform parameters back
        if "new_param" in adapted:
            value = adapted.pop("new_param")
            adapted["original_param"] = process(value)
        return adapted
    
    def adapt_response(self, tool_name, response, agent):
        """Optionally transform the tool response."""
        # Return None to keep original, or modified response
        return None
```

### Using the Adapter in a Component

```python
class MyComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.adapter = MyAdapter(self)
    
    async def install(self, agent):
        await super().install(agent)
        # Register the adapter
        self.register_tool_adapter(self.adapter)
```

## Common Use Cases

### 1. Citation Management (URL → Index)

Transform URL parameters to citation indices for token efficiency:

```python
class CitationAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(component)
        self.citations = []  # Store URL-to-index mapping
    
    def should_adapt(self, tool, agent):
        # Adapt tools with URL parameters
        schema = tool.model.model_json_schema()
        properties = schema.get("properties", {})
        return any("url" in k.lower() for k in properties)
    
    def adapt_signature(self, tool, signature, agent):
        # Replace url: str with citation_idx: int
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
        # Convert index back to URL
        adapted = dict(parameters)
        if "citation_idx" in adapted:
            idx = adapted.pop("citation_idx")
            if 0 <= idx < len(self.citations):
                adapted["url"] = self.citations[idx]
        return adapted
```

### 2. Authentication Injection

Add authentication transparently to tools:

```python
class AuthAdapter(ToolAdapter):
    def __init__(self, component, api_key):
        super().__init__(component)
        self.api_key = api_key
    
    def should_adapt(self, tool, agent):
        return tool.name in ["fetch_api", "call_service"]
    
    def adapt_signature(self, tool, signature, agent):
        # Add optional auth flag
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]
        params["use_auth"] = {
            "type": "boolean",
            "description": "Use authentication",
            "default": True
        }
        return adapted
    
    def adapt_parameters(self, tool_name, parameters, agent):
        adapted = dict(parameters)
        if adapted.pop("use_auth", True):
            # Inject auth header/token
            adapted["headers"] = {
                **adapted.get("headers", {}),
                "Authorization": f"Bearer {self.api_key}"
            }
        return adapted
```

### 3. Response Caching

Cache tool responses for efficiency:

```python
class CacheAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(component)
        self.cache = {}
    
    def adapt_parameters(self, tool_name, parameters, agent):
        # Check cache before execution
        cache_key = f"{tool_name}:{hash(frozenset(parameters.items()))}"
        if cache_key in self.cache:
            # Short-circuit with cached response
            # (In practice, would need to handle this differently)
            print(f"Cache hit for {tool_name}")
        return parameters
    
    def adapt_response(self, tool_name, response, agent):
        # Store response in cache
        cache_key = f"{tool_name}:latest"
        self.cache[cache_key] = response
        return response  # Return unchanged
```

## Multiple Adapters & Conflict Resolution

### Adapter Interaction

When multiple adapters modify the same tool:

1. **Signature Transformation**: Applied in priority order (forward)
2. **Parameter Transformation**: Applied in reverse order (unwrapping)
3. **Response Transformation**: Applied in priority order (forward)

### Conflict Strategies

Configure how conflicts are handled:

```python
from good_agent.components import ConflictStrategy

class MyAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(
            component,
            priority=150,  # Higher priority = runs first
            conflict_strategy=ConflictStrategy.CHAIN
        )
```

**Available Strategies:**

- **CHAIN** (default): Apply all adapters in sequence
- **EXCLUSIVE**: Raise error if multiple adapters modify same parameter
- **PRIORITY**: Use highest priority adapter only for conflicts
- **MERGE**: Custom merging logic (requires implementation)

### Example: Multiple Adapters

```python
class EnhancedComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        
        # Multiple adapters with different priorities
        self.citation_adapter = CitationAdapter(self)  # priority=100
        self.auth_adapter = AuthAdapter(self, "key")    # priority=50
        self.cache_adapter = CacheAdapter(self)         # priority=200
    
    async def install(self, agent):
        await super().install(agent)
        
        # Register in any order - priority determines execution
        self.register_tool_adapter(self.citation_adapter)
        self.register_tool_adapter(self.auth_adapter)
        self.register_tool_adapter(self.cache_adapter)
```

**Execution Order:**
1. Signatures: Cache (200) → Citation (100) → Auth (50)
2. Parameters: Auth → Citation → Cache (reverse)
3. Responses: Cache → Citation → Auth

## Type Safety Considerations

### Parameter Type Transformations

The adapter system validates type compatibility:

```python
def analyze_transformation(self, tool, signature):
    return AdapterMetadata(
        modified_params=set(),
        added_params={"index"},
        removed_params={"url"},
        # Type mappings for validation
        type_mappings={"url": (str, int)}  # str → int transformation
    )
```

### Validation Rules

1. **Basic Types**: `str ↔ int` allowed for ID/index transformations
2. **Subclasses**: Subclass relationships are valid
3. **Generic Types**: `List[str] → List[int]` if element types compatible
4. **Bidirectional**: Transformations must be reversible

## Best Practices

### 1. Stateless Adapters

Keep adapters as stateless as possible:

```python
# Good: State in component
class MyComponent(AgentComponent):
    def __init__(self):
        self.mapping = {}
        self.adapter = MyAdapter(self)

# Adapter references component.mapping
```

### 2. Metadata Analysis

Always implement `analyze_transformation()` for conflict detection:

```python
def analyze_transformation(self, tool, signature):
    # Accurately report what will be modified
    return AdapterMetadata(
        modified_params={"param1", "param2"},
        added_params={"new_param"},
        removed_params={"old_param"}
    )
```

### 3. Error Handling

Handle missing/invalid parameters gracefully:

```python
def adapt_parameters(self, tool_name, parameters, agent):
    adapted = dict(parameters)
    
    if "citation_idx" in adapted:
        idx = adapted.pop("citation_idx")
        if 0 <= idx < len(self.citations):
            adapted["url"] = self.citations[idx]
        else:
            # Handle invalid index
            raise ValueError(f"Invalid citation index: {idx}")
    
    return adapted
```

### 4. Component Integration

Respect component enabled state:

```python
async def install(self, agent):
    await super().install(agent)
    
    # Adapters automatically respect component.enabled
    self.register_tool_adapter(self.adapter)
    
    # Disable component disables adapters
    # self.enabled = False
```

## Testing Tool Adapters

### Unit Testing

```python
import pytest
from unittest.mock import MagicMock

def test_adapter_transformation():
    component = MagicMock()
    adapter = MyAdapter(component)
    
    # Test should_adapt
    tool = MagicMock()
    tool.name = "fetch_url"
    assert adapter.should_adapt(tool, agent=None)
    
    # Test signature transformation
    original_sig = {...}
    adapted_sig = adapter.adapt_signature(tool, original_sig, agent=None)
    assert "new_param" in adapted_sig["function"]["parameters"]["properties"]
    
    # Test parameter transformation
    params = {"new_param": "value"}
    adapted = adapter.adapt_parameters("fetch_url", params, agent=None)
    assert "original_param" in adapted
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_adapter_with_agent():
    class TestComponent(AgentComponent):
        def __init__(self):
            super().__init__()
            self.adapter = MyAdapter(self)
        
        async def install(self, agent):
            await super().install(agent)
            self.register_tool_adapter(self.adapter)
    
    component = TestComponent()
    agent = Agent("Test", tools=[my_tool], extensions=[component])
    await agent.ready()
    
    # Verify adapter is applied
    # Test tool execution with adapted parameters
```

## Debugging

### Enable Event Tracing

```python
# See adapter events in action
agent.set_event_trace(True)
```

### Check Adapter Registration

```python
# Verify adapters are registered
component = agent[MyComponent]
print(f"Adapters: {component._tool_adapter_registry._adapters}")
```

### Monitor Transformations

```python
class DebugAdapter(ToolAdapter):
    def adapt_signature(self, tool, signature, agent):
        print(f"Adapting signature for {tool.name}")
        adapted = super().adapt_signature(tool, signature, agent)
        print(f"Changes: {diff(signature, adapted)}")
        return adapted
```

## Advanced Topics

### Dynamic Adapter Registration

Register/unregister adapters at runtime:

```python
# Add adapter after agent is running
component.register_tool_adapter(new_adapter)

# Remove adapter
component.unregister_tool_adapter(old_adapter)
```

### Conditional Adaptation

Adapt based on agent context:

```python
def should_adapt(self, tool, agent):
    # Only adapt in certain modes
    if agent.context.get("mode") == "research":
        return tool.name in self.research_tools
    return False
```

### Adapter Composition

Chain adapters for complex transformations:

```python
class CompositeAdapter(ToolAdapter):
    def __init__(self, component, adapters):
        super().__init__(component)
        self.adapters = adapters
    
    def adapt_signature(self, tool, signature, agent):
        result = signature
        for adapter in self.adapters:
            result = adapter.adapt_signature(tool, result, agent)
        return result
```

## Summary

The Tool Adapter pattern provides a powerful, flexible way to modify tool behavior without changing tool implementations. Key benefits:

- **Transparency**: Tools remain unchanged
- **Composability**: Multiple adapters can work together
- **Type Safety**: Transformations are validated
- **Conflict Resolution**: Multiple strategies for handling conflicts
- **Component Integration**: Seamless integration with AgentComponent lifecycle

Use tool adapters when you need to:
- Transform parameters between formats (URLs ↔ indices)
- Inject authentication or headers
- Add caching or rate limiting
- Validate or sanitize inputs
- Route to different implementations
- Add logging or telemetry