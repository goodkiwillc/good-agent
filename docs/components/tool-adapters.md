# Tool Adapters

Tool Adapters allow components to transparently intercept and modify tool behavior without changing the original tool implementations. This pattern enables powerful cross-cutting concerns like parameter transformation, authentication injection, caching, and citation management.

## Overview

### What are Tool Adapters?

Tool Adapters are a component-level pattern that hooks into the tool execution lifecycle to:

1. **Transform tool signatures** - Modify how tools appear to the LLM
2. **Adapt parameters** - Transform parameters from the LLM before tool execution
3. **Modify responses** - Optionally transform tool responses before returning to the conversation

### When to Use Tool Adapters

Use tool adapters when you need to:

- **Transform parameter formats** - Convert between different representations (e.g., URLs ↔ citation indices)
- **Inject authentication** - Add auth tokens, API keys, or headers to tool calls
- **Add caching or rate limiting** - Implement cross-cutting performance optimizations
- **Validate or sanitize inputs** - Add extra validation beyond tool schema
- **Add logging or metrics** - Track tool usage transparently
- **Modify tool behavior conditionally** - Change behavior based on agent context

## How Tool Adapters Work

### The Three-Stage Lifecycle

Tool adapters hook into three key events in the tool execution pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TOOLS_GENERATE_SIGNATURE                                 │
│    adapt_signature() - Modify tool signature for LLM        │
│    Original: fetch_url(url: str)                            │
│    Adapted:  fetch_url(citation_idx: int)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. TOOL_CALL_BEFORE                                         │
│    adapt_parameters() - Transform LLM params to tool format │
│    LLM sends: {"citation_idx": 1}                           │
│    Tool gets: {"url": "https://example.com"}                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. TOOL_CALL_AFTER (optional)                               │
│    adapt_response() - Modify response before conversation   │
│    Original: "Raw content..."                               │
│    Adapted:  "Processed content with citations..."          │
└─────────────────────────────────────────────────────────────┘
```

### Core Methods

Every `ToolAdapter` must implement:

- **`should_adapt(tool, agent)`** - Determine if this adapter applies to the given tool
- **`adapt_signature(tool, signature, agent)`** - Transform the tool signature sent to the LLM
- **`adapt_parameters(tool_name, parameters, agent)`** - Transform parameters from LLM back to original format
- **`adapt_response(tool_name, response, agent)`** - (Optional) Transform the tool response

## Real-World Example: Citation Management

The most powerful use case is the `CitationAdapter` used by the `CitationManager` component to optimize token usage and prevent URL hallucinations:

```python
from good_agent.extensions.citations import CitationManager

# The CitationManager includes a CitationAdapter that:
# 1. Identifies tools with URL parameters
# 2. Replaces URL strings with integer indices in the signature
# 3. Translates indices back to URLs before tool execution

async with Agent(
    "Research Assistant",
    extensions=[CitationManager()]
) as agent:
    # User provides URLs directly
    await agent.call("Analyze https://example.com/article")

    # CitationAdapter automatically:
    # - Registers URL as citation #1
    # - Transforms tool signature: fetch(url: str) → fetch(citation_idx: int)
    # - LLM sees: "Use citation_idx=1 to analyze the article"
    # - Before execution: citation_idx=1 → url="https://example.com/article"
```

**Benefits:**
- Reduces token usage (integers vs long URLs)
- Prevents LLM from hallucinating invalid URLs
- Maintains consistent citation references across conversation

## Creating a Custom Tool Adapter

### Basic Structure

```python
from good_agent import ToolAdapter, AgentComponent
from good_agent.core.components import AdapterMetadata
import copy

class LoggingAdapter(ToolAdapter):
    """Adapter that logs all tool calls."""

    def should_adapt(self, tool, agent):
        """Apply to all tools."""
        return True

    def analyze_transformation(self, tool, signature):
        """Report what transformations will be performed (for conflict detection)."""
        return AdapterMetadata(
            modified_params=set(),
            added_params={"_logged"},
            removed_params=set()
        )

    def adapt_signature(self, tool, signature, agent):
        """Add logging flag to signature."""
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]
        params["_logged"] = {
            "type": "boolean",
            "description": "Internal logging flag",
            "default": True
        }
        return adapted

    def adapt_parameters(self, tool_name, parameters, agent):
        """Log parameters and remove logging flag."""
        logged = parameters.pop("_logged", True)
        if logged:
            print(f"Calling {tool_name} with {parameters}")
        return parameters

    def adapt_response(self, tool_name, response, agent):
        """Log response."""
        print(f"Tool {tool_name} returned: {response.response}")
        return response

class LoggingComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.adapter = LoggingAdapter(self)

    async def install(self, agent):
        await super().install(agent)
        # Register the adapter with the component
        self.register_tool_adapter(self.adapter)
```

### Authentication Adapter Example

```python
class AuthAdapter(ToolAdapter):
    """Inject authentication into API tools."""

    def __init__(self, component, api_key: str):
        super().__init__(component, priority=150)
        self.api_key = api_key

    def should_adapt(self, tool, agent):
        """Only adapt tools that call external APIs."""
        return tool.name in ["fetch_api", "call_service", "web_request"]

    def adapt_signature(self, tool, signature, agent):
        """Signature doesn't need to change - auth is injected transparently."""
        return signature

    def adapt_parameters(self, tool_name, parameters, agent):
        """Inject authorization header."""
        adapted = dict(parameters)

        # Add or merge headers
        headers = adapted.get("headers", {})
        headers["Authorization"] = f"Bearer {self.api_key}"
        adapted["headers"] = headers

        return adapted
```

### Caching Adapter Example

```python
import hashlib
import json
import time

class CachingAdapter(ToolAdapter):
    """Cache tool responses to avoid redundant calls."""

    def __init__(self, component, ttl: int = 3600):
        super().__init__(component, priority=200)
        self.cache = {}
        self.ttl = ttl

    def should_adapt(self, tool, agent):
        """Only cache expensive tools."""
        return tool.name in ["web_search", "fetch_url", "call_api"]

    def adapt_signature(self, tool, signature, agent):
        """Add cache control parameter."""
        adapted = copy.deepcopy(signature)
        params = adapted["function"]["parameters"]["properties"]
        params["use_cache"] = {
            "type": "boolean",
            "description": "Use cached result if available",
            "default": True
        }
        return adapted

    def adapt_parameters(self, tool_name, parameters, agent):
        """Check cache before execution."""
        use_cache = parameters.pop("use_cache", True)

        if use_cache:
            # Generate cache key
            cache_key = f"{tool_name}:{hashlib.md5(json.dumps(parameters, sort_keys=True).encode()).hexdigest()}"

            # Check if cached and not expired
            if cache_key in self.cache:
                cached_response, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.ttl:
                    print(f"Cache hit for {tool_name}")
                    # Note: In practice, you'd need to short-circuit execution here

        return parameters

    def adapt_response(self, tool_name, response, agent):
        """Cache successful responses."""
        if response.success:
            cache_key = f"{tool_name}:latest"
            self.cache[cache_key] = (response.response, time.time())
        return response
```

## Multiple Adapters & Conflict Resolution

### Adapter Priority and Chaining

When multiple adapters modify the same tool, they execute in priority order:

```python
class HighPriorityAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(component, priority=200)  # Runs first

class MediumPriorityAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(component, priority=100)  # Default priority

class LowPriorityAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(component, priority=50)   # Runs last
```

**Execution Order:**
- **Signatures**: High → Medium → Low (forward)
- **Parameters**: Low → Medium → High (reverse - unwrapping)
- **Responses**: High → Medium → Low (forward)

### Conflict Strategies

```python
from good_agent.core.components import ConflictStrategy

class ExclusiveAdapter(ToolAdapter):
    def __init__(self, component):
        super().__init__(
            component,
            conflict_strategy=ConflictStrategy.EXCLUSIVE  # Raise error on conflicts
        )
```

**Available strategies:**
- `CHAIN` (default) - Apply all adapters in sequence
- `EXCLUSIVE` - Raise error if multiple adapters modify same parameter
- `PRIORITY` - Use highest priority adapter for conflicting parameters
- `MERGE` - Custom merging logic (requires implementation)

## Component Integration

### Registration Lifecycle

```python
class MultiAdapterComponent(AgentComponent):
    def __init__(self):
        super().__init__()

        # Create adapters (bound to this component instance)
        self.citation_adapter = CitationAdapter(self)
        self.auth_adapter = AuthAdapter(self, api_key="...")
        self.cache_adapter = CachingAdapter(self)

    async def install(self, agent):
        await super().install(agent)

        # Register adapters (order doesn't matter - priority determines execution)
        self.register_tool_adapter(self.citation_adapter)
        self.register_tool_adapter(self.auth_adapter)
        self.register_tool_adapter(self.cache_adapter)

    async def uninstall(self, agent):
        # Adapters are automatically unregistered when component is uninstalled
        await super().uninstall(agent)
```

### Dynamic Adapter Management

```python
# Add adapter at runtime
component.register_tool_adapter(new_adapter)

# Remove adapter
component.unregister_tool_adapter(old_adapter)

# Conditional adaptation
class ConditionalAdapter(ToolAdapter):
    def should_adapt(self, tool, agent):
        # Only adapt in research mode
        return agent.context.get("mode") == "research" and "search" in tool.name
```

## Best Practices

### 1. Keep Adapters Stateless

Store state in the parent component, not the adapter:

```python
# Good
class MyComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.url_mapping = {}  # State in component
        self.adapter = MyAdapter(self)

# Adapter references component.url_mapping
```

### 2. Always Implement analyze_transformation()

This enables proper conflict detection:

```python
def analyze_transformation(self, tool, signature):
    return AdapterMetadata(
        modified_params={"param1"},
        added_params={"new_param"},
        removed_params={"old_param"}
    )
```

### 3. Handle Errors Gracefully

```python
def adapt_parameters(self, tool_name, parameters, agent):
    adapted = dict(parameters)

    if "citation_idx" in adapted:
        idx = adapted.pop("citation_idx")
        url = self.component.index.get_url(idx)

        if url is None:
            # Log warning but don't fail
            agent.logger.warning(f"Invalid citation index: {idx}")
            adapted["citation_idx"] = idx  # Keep original for error handling
        else:
            adapted["url"] = url

    return adapted
```

### 4. Use Deep Copies for Signatures

Always deep copy signatures before modification:

```python
import copy

def adapt_signature(self, tool, signature, agent):
    adapted = copy.deepcopy(signature)  # Don't modify original
    # ... make changes to adapted
    return adapted
```

## Differences from MCP Tool Adapter

Note: The `MCPToolAdapter` is a different pattern - it's a direct `Tool` subclass that adapts MCP server tools to the Good Agent interface, not a component-level tool adapter:

```python
# Component-level ToolAdapter (this document)
class CitationAdapter(ToolAdapter):
    """Modifies existing tools transparently."""
    pass

# MCP Tool Adapter (different pattern)
class MCPToolAdapter(Tool):
    """Wraps an MCP server tool as a Good Agent Tool."""
    pass
```

## See Also

- [CitationManager Component](built-ins.md#citationmanager-component) - Real-world adapter usage
- [Creating Components](creating-components.md) - Component development guide
- [Events](events.md) - Understanding the event lifecycle
