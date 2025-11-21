# Event System Integration

Components integrate with their parent agent through a powerful event system, enabling sophisticated orchestration, monitoring, and behavior modification.

## Event Handler Registration

### Using the @on Decorator

The `@on` decorator is the primary way to register event handlers in components. Handlers are automatically registered with the parent agent during component setup:

```python
from good_agent import AgentComponent
from good_agent.core.event_router import on, EventContext
from good_agent.events import AgentEvents

class EventDrivenComponent(AgentComponent):
    """Component that uses event handlers to interact with the agent."""
    
    @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
    def on_message_added(self, ctx: EventContext):
        """React to new messages with high priority.
        
        The @on decorator marks this method as an event handler.
        During setup(), it's automatically registered with the parent agent.
        """
        message = ctx.parameters["message"]
        print(f"New message: {message.role} - {message.content[:50]}...")
        
        # Access parent agent through self.agent property
        total_messages = len(self.agent.messages)
        print(f"Total messages in conversation: {total_messages}")
```

**How it works:**

1. The `@on` decorator marks methods with event metadata
2. During `setup()`, the component's `_register_decorated_handlers_with_agent()` method finds all decorated methods
3. Each handler is registered with the parent agent's event router
4. Handlers execute in priority order when events are emitted

### Manual Handler Registration

You can also register handlers programmatically during `setup()` or `install()`:

```python
class DynamicComponent(AgentComponent):
    
    def setup(self, agent: Agent):
        """Register handlers during synchronous setup."""
        super().setup(agent)
        
        # Register handler directly on the agent
        agent.on(AgentEvents.TOOL_CALL_BEFORE)(self.log_tool_call)
        
        # Register with specific priority
        agent.on(
            AgentEvents.MESSAGE_APPEND_AFTER, 
            priority=50
        )(self.track_message_count)
    
    async def log_tool_call(self, ctx: EventContext):
        """Dynamically registered handler."""
        tool_name = ctx.parameters["tool_name"]
        print(f"Tool called: {tool_name}")
    
    async def track_message_count(self, ctx: EventContext):
        """Track message statistics."""
        self.message_count = len(self.agent.messages)
```

## Accessing the Parent Agent

Components can access their parent agent instance through the `self.agent` property:

```python
class AgentAwareComponent(AgentComponent):
    
    @on(AgentEvents.TOOL_CALL_AFTER)
    async def on_tool_complete(self, ctx: EventContext):
        """Handler that interacts with the parent agent."""
        
        # Access agent properties
        conversation_length = len(self.agent.messages)
        agent_name = self.agent.name
        
        # Access agent configuration
        model = self.agent.config.model
        temperature = self.agent.config.temperature
        
        # Call agent methods
        await self.agent.append(
            f"Tool execution completed. Model: {model}",
            role="system"
        )
        
        # Access other components
        from good_agent.extensions.citations import CitationManager
        citation_mgr = self.agent[CitationManager]
        if citation_mgr:
            citations = citation_mgr.get_citations()
        
        # Access tools
        available_tools = list(self.agent.tools.keys())
        print(f"Available tools: {available_tools}")
```

## EventContext: The Handler Interface

Event handlers receive an `EventContext` object containing all event data:

```python
@on(AgentEvents.TOOL_CALL_BEFORE)
async def intercept_tool_call(self, ctx: EventContext):
    """EventContext provides access to event data and control flow."""
    
    # 1. Read event parameters (immutable input data)
    tool_name = ctx.parameters["tool_name"]
    parameters = ctx.parameters["parameters"]
    agent = ctx.parameters.get("agent")  # Some events include agent reference
    
    # 2. Modify output (mutable - affects downstream handlers and final result)
    if tool_name == "search" and "limit" not in parameters:
        ctx.parameters["parameters"]["limit"] = 5
        ctx.output = parameters  # Update output for next handlers
    
    # 3. Stop event chain early with a result
    if tool_name == "forbidden_tool":
        ctx.stop_with_output({"error": "Tool not allowed"})
        # Raises ApplyInterrupt - no handlers after this execute
    
    # 4. Stop with an exception
    if not self.agent.config.get("tools_enabled"):
        ctx.stop_with_exception(RuntimeError("Tools are disabled"))
        # Records exception but doesn't raise - handler decides what to do
    
    # 5. Access return value from previous handlers
    previous_result = ctx.return_value
    
    # 6. Check if chain should stop
    if ctx.should_stop:
        return  # Exit early if previous handler called stop()
    
    # 7. Event metadata
    event_name = ctx.event  # "tool:call:before"
    timestamp = ctx.invocation_timestamp
```

### EventContext Key Properties

- **`parameters`**: Dictionary of event-specific input data (read from, but modifying affects other handlers)
- **`output`**: The accumulated result, modified by handlers in the chain
- **`return_value`**: Typed accessor for output (excludes exceptions)
- **`exception`**: Captured exception if a handler called `stop_with_exception()`
- **`should_stop`**: Boolean flag indicating if the event chain should terminate
- **`event`**: The event name being handled
- **`invocation_timestamp`**: Unix timestamp when event was dispatched

## Handler Priority and Execution Order

Handlers execute in priority order (higher numbers run first):

```python
class PriorityComponent(AgentComponent):
    
    @on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
    async def high_priority_validator(self, ctx: EventContext):
        """Runs first - validate before other handlers."""
        tool_name = ctx.parameters["tool_name"]
        if tool_name not in self.allowed_tools:
            ctx.stop_with_output({"error": "Validation failed"})
    
    @on(AgentEvents.TOOL_CALL_BEFORE, priority=100)
    async def medium_priority_logger(self, ctx: EventContext):
        """Runs second - log after validation."""
        if ctx.should_stop:
            return  # Validation failed, skip logging
        tool_name = ctx.parameters["tool_name"]
        print(f"Validated tool call: {tool_name}")
    
    @on(AgentEvents.TOOL_CALL_BEFORE, priority=50)
    async def low_priority_modifier(self, ctx: EventContext):
        """Runs last - modify parameters after logging."""
        if ctx.should_stop:
            return
        # Add metadata to all tool calls
        ctx.parameters["parameters"]["_component_id"] = id(self)
```

**Default priority**: Handlers without explicit priority default to `100`.

## Common Event Handler Patterns

### 1. Parameter Modification

```python
@on(AgentEvents.TOOL_CALL_BEFORE)
async def inject_defaults(self, ctx: EventContext):
    """Add default parameters to tool calls."""
    parameters = ctx.parameters["parameters"]
    tool_name = ctx.parameters["tool_name"]
    
    # Inject defaults based on agent configuration
    if tool_name == "search":
        parameters.setdefault("limit", self.agent.config.get("search_limit", 10))
        parameters.setdefault("safe_search", True)
```

### 2. Response Transformation

```python
@on(AgentEvents.TOOL_CALL_AFTER)
async def transform_response(self, ctx: EventContext):
    """Transform tool responses before they reach the LLM."""
    response = ctx.parameters["response"]
    tool_name = ctx.parameters["tool_name"]
    
    if tool_name == "search" and response.success:
        # Parse and enrich response
        results = response.response
        enriched = self._add_metadata(results)
        
        # Update the response
        response.response = enriched
        ctx.output = response  # Propagate to next handlers
```

### 3. Side Effects and Monitoring

```python
@on(AgentEvents.MESSAGE_APPEND_AFTER)
def track_conversation(self, ctx: EventContext):
    """Monitor conversation without modifying it."""
    message = ctx.parameters["message"]
    
    # Track statistics
    self.message_count += 1
    self.total_tokens += len(message.content.split())
    
    # Log to external system (non-blocking)
    asyncio.create_task(self._log_to_analytics({
        "role": message.role,
        "length": len(message.content),
        "agent": self.agent.name
    }))
```

### 4. Conditional Execution

```python
@on(AgentEvents.LLM_COMPLETE_BEFORE, predicate=lambda ctx: ctx.parameters.get("stream") is True)
async def on_streaming_request(self, ctx: EventContext):
    """Only execute for streaming LLM requests."""
    print("Streaming request detected")
    self.streaming_active = True
```

## Emitting Custom Events

Components can emit custom events to communicate with other components:

```python
class SearchComponent(AgentComponent):
    
    @tool
    async def search(self, query: str) -> list[dict]:
        """Perform a search and emit custom event."""
        results = await self._do_search(query)
        
        # Emit custom event for other components
        await self.agent.apply("custom:search_completed", {
            "component_id": id(self),
            "query": query,
            "result_count": len(results),
            "timestamp": time.time()
        })
        
        return results


class AnalyticsComponent(AgentComponent):
    
    def setup(self, agent: Agent):
        super().setup(agent)
        # Listen for custom events from other components
        agent.on("custom:search_completed")(self.track_search)
    
    async def track_search(self, ctx: EventContext):
        """React to search events from SearchComponent."""
        query = ctx.parameters["query"]
        result_count = ctx.parameters["result_count"]
        
        print(f"Search analytics: '{query}' returned {result_count} results")
        await self._log_to_database(ctx.parameters)
```

## Setup vs Install: When to Register Handlers

- **`setup(agent)`** (synchronous): Use for registering handlers that need to be active during agent initialization
- **`install(agent)`** (async): Use for async initialization like loading resources

```python
class HybridComponent(AgentComponent):
    
    def setup(self, agent: Agent):
        """Register critical handlers early."""
        super().setup(agent)
        # Handlers registered here are active during Agent.__init__
        agent.on(AgentEvents.AGENT_INIT_BEFORE)(self.on_init_start)
    
    async def install(self, agent: Agent):
        """Perform async setup after agent initialization."""
        await super().install(agent)
        # Load resources, connect to services, etc.
        self.database = await self._connect_to_db()
        
        # Register additional handlers after resources are ready
        agent.on(AgentEvents.EXECUTE_AFTER)(self.persist_conversation)
    
    @on(AgentEvents.TOOL_CALL_BEFORE)  # Registered automatically during setup()
    async def validate_tool_call(self, ctx: EventContext):
        """This handler is available throughout agent lifecycle."""
        pass
```
