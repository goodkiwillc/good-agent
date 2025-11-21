# Event System Integration

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
