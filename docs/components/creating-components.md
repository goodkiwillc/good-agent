# Creating Custom Components

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

## Basic Component Structure

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

## Component Tools

Components can define tools that are automatically registered with the agent:

```python
--8<-- "tests/unit/components/test_component_tools.py:27:65"
```

**Tool Registration Process:**

1. `@tool` decorator creates `BoundTool` descriptor
2. `AgentComponentType` metaclass collects tools in `_component_tools`
3. Tools registered automatically during `install()` phase
4. Tools have access to component state via `self`
5. Tools can access agent via `self.agent`

## Advanced Tool Configuration

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
