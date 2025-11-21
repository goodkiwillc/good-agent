# Tool Adapters

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
