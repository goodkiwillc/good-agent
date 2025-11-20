# Events

Good Agent provides a comprehensive event-driven architecture that enables reactive programming, lifecycle hooks, and extensible component interactions. The event system allows you to monitor, modify, and respond to agent operations in real-time.

## Event System Overview

### Core Concepts

Good Agent events follow a `domain:action[:phase]` naming convention and cover all major operations:

- **Agent lifecycle** - initialization, state changes, versioning
- **Message operations** - creation, rendering, appending  
- **LLM interactions** - completion, streaming, extraction
- **Tool execution** - before/after calls, errors
- **Template processing** - compilation, context resolution
- **Execution flow** - iterations, errors, completion

### Event Architecture

Events are emitted synchronously or asynchronously and can be:

- **Observed** - Listen for events without modifying behavior
- **Modified** - Change event parameters or execution flow
- **Interrupted** - Stop event propagation or cancel operations
- **Chained** - Trigger additional events based on conditions

## Basic Event Handling

### Subscribing to Events

Use the `@agent.on()` decorator or method to subscribe to events:

```python
from good_agent import Agent
from good_agent.events import AgentEvents

async with Agent("Assistant") as agent:
    @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
    def on_message_added(ctx):
        message = ctx.parameters["message"]
        print(f"New {message.role} message: {message.content[:50]}...")
    
    @agent.on(AgentEvents.TOOL_CALL_BEFORE)
    async def on_tool_call(ctx):
        tool_name = ctx.parameters["tool_name"]
        arguments = ctx.parameters["arguments"]
        print(f"Calling tool {tool_name} with {arguments}")
    
    # Events will fire during normal agent operations
    response = await agent.call("Hello! Can you help me with math?")
```

### Event Context

All event handlers receive an `EventContext` with parameters and optional output:

```python
@agent.on(AgentEvents.TOOL_CALL_AFTER)
def handle_tool_result(ctx):
    # Access event parameters (read-only)
    tool_name = ctx.parameters["tool_name"] 
    success = ctx.parameters["success"]
    response = ctx.parameters.get("response")
    
    # Access agent that emitted the event
    agent = ctx.parameters["agent"]
    
    # Check for output from other handlers
    if ctx.output:
        print(f"Previous handler set output: {ctx.output}")
```

### Event Priorities

Control handler execution order with priorities (higher numbers = earlier execution):

```python
@agent.on(AgentEvents.MESSAGE_APPEND_BEFORE, priority=200)
def high_priority_handler(ctx):
    print("Runs first")

@agent.on(AgentEvents.MESSAGE_APPEND_BEFORE, priority=100)  # Default priority
def medium_priority_handler(ctx):
    print("Runs second")

@agent.on(AgentEvents.MESSAGE_APPEND_BEFORE, priority=50)
def low_priority_handler(ctx):
    print("Runs last")
```

## Agent Lifecycle Events

### Initialization & State

Monitor agent startup and state transitions:

```python
from good_agent.events import AgentEvents, AgentStateChangeParams
from good_agent.core.event_router import EventContext

@agent.on(AgentEvents.AGENT_INIT_AFTER)
def on_agent_ready(ctx: EventContext[AgentInitializeParams, None]):
    agent = ctx.parameters["agent"]
    tools = ctx.parameters["tools"]
    print(f"Agent {agent.name} initialized with {len(tools)} tools")

@agent.on(AgentEvents.AGENT_STATE_CHANGE)
def on_state_change(ctx: EventContext[AgentStateChangeParams, None]):
    old_state = ctx.parameters["old_state"]
    new_state = ctx.parameters["new_state"]
    print(f"Agent state: {old_state} → {new_state}")
```

### Version Changes

Track conversation history modifications:

```python
from good_agent.events import AgentVersionChangeParams

@agent.on(AgentEvents.AGENT_VERSION_CHANGE)
def on_version_change(ctx: EventContext[AgentVersionChangeParams, None]):
    old_version = ctx.parameters["old_version"]
    new_version = ctx.parameters["new_version"]
    changes = ctx.parameters["changes"]
    
    print(f"Version {old_version} → {new_version}")
    print(f"Message count: {changes.get('messages', 0)}")
```

## Message Events

### Message Creation & Modification

Intercept message operations:

```python
from good_agent.events import MessageAppendParams

@agent.on(AgentEvents.MESSAGE_APPEND_BEFORE)
def before_message_append(ctx: EventContext[MessageAppendParams, None]):
    message = ctx.parameters["message"]
    
    # Add metadata to messages
    if not hasattr(message, 'metadata'):
        message.metadata = {}
    message.metadata['timestamp'] = datetime.now().isoformat()
    message.metadata['handler_processed'] = True

@agent.on(AgentEvents.MESSAGE_APPEND_AFTER) 
def after_message_append(ctx: EventContext[MessageAppendParams, None]):
    message = ctx.parameters["message"]
    agent = ctx.parameters["agent"]
    
    # Log message statistics
    total_messages = len(agent.messages)
    print(f"Added {message.role} message. Total: {total_messages}")
```

### Message Rendering

Customize how messages are rendered for different contexts:

```python
from good_agent.events import MessageRenderParams

@agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)
def customize_rendering(ctx: EventContext[MessageRenderParams, list]):
    message = ctx.parameters["message"]
    mode = ctx.parameters["mode"]
    
    # Add custom rendering for specific message types
    if hasattr(message, 'metadata') and 'sensitive' in message.metadata:
        if mode == "display":
            # Mask sensitive content in display mode
            ctx.output = ["[REDACTED - Sensitive Content]"]
        # Let normal rendering proceed for LLM mode
```

## Tool Events

### Tool Call Monitoring

Track and modify tool executions:

```python
from good_agent.events import ToolCallBeforeParams, ToolCallAfterParams

@agent.on(AgentEvents.TOOL_CALL_BEFORE)
async def before_tool_call(ctx: EventContext[ToolCallBeforeParams, dict]):
    tool_name = ctx.parameters["tool_name"]
    arguments = ctx.parameters["arguments"]
    
    # Log tool calls
    print(f"🛠️  Calling {tool_name} with {arguments}")
    
    # Modify arguments if needed
    if tool_name == "search" and "limit" not in arguments:
        modified_args = arguments.copy()
        modified_args["limit"] = 10
        ctx.output = modified_args  # Return modified arguments
        return modified_args

@agent.on(AgentEvents.TOOL_CALL_AFTER)
def after_tool_call(ctx: EventContext[ToolCallAfterParams, None]):
    tool_name = ctx.parameters["tool_name"]
    success = ctx.parameters["success"]
    response = ctx.parameters.get("response")
    
    if success:
        print(f"✅ {tool_name} succeeded")
        if response and hasattr(response, 'response'):
            result = response.response
            print(f"   Result: {str(result)[:100]}...")
    else:
        error = ctx.parameters.get("error", "Unknown error")
        print(f"❌ {tool_name} failed: {error}")
```

### Tool Error Handling

Implement custom error handling and recovery:

```python
@agent.on(AgentEvents.TOOL_CALL_ERROR)
async def handle_tool_error(ctx):
    tool_name = ctx.parameters["tool_name"]
    error = ctx.parameters["error"]
    
    # Log detailed error information
    print(f"Tool {tool_name} failed: {error}")
    
    # Implement retry logic for specific tools
    if tool_name == "web_search" and "timeout" in str(error).lower():
        print("Retrying web search with longer timeout...")
        # Could trigger a retry by emitting another tool call event
```

## LLM Events

### LLM Request & Response Monitoring

Track LLM interactions:

```python
from good_agent.events import LLMCompleteParams

@agent.on(AgentEvents.LLM_COMPLETE_BEFORE)
def before_llm_call(ctx: EventContext[LLMCompleteParams, None]):
    messages = ctx.parameters["messages"]
    model = ctx.parameters["model"]
    temperature = ctx.parameters.get("temperature", "not set")
    
    print(f"🤖 Calling {model} with {len(messages)} messages")
    print(f"   Temperature: {temperature}")

@agent.on(AgentEvents.LLM_COMPLETE_AFTER)
def after_llm_call(ctx: EventContext[LLMCompleteParams, None]):
    response = ctx.parameters.get("response")
    if response:
        print(f"✅ LLM responded with {len(response.content)} characters")
```

### Streaming Events

Handle streaming LLM responses:

```python
@agent.on(AgentEvents.LLM_STREAM_CHUNK)
def on_stream_chunk(ctx):
    chunk = ctx.parameters.get("chunk")
    if chunk and hasattr(chunk, 'choices'):
        content = chunk.choices[0].delta.content
        if content:
            print(content, end='', flush=True)
```

## Execution Events

### Iteration Monitoring

Track agent execution cycles:

```python
from good_agent.events import ExecuteIterationParams

@agent.on(AgentEvents.EXECUTE_BEFORE)
def on_execute_start(ctx):
    print("🚀 Agent execution started")

@agent.on(AgentEvents.EXECUTE_ITERATION_BEFORE)
def before_iteration(ctx: EventContext[ExecuteIterationParams, None]):
    iteration = ctx.parameters.get("iteration", 0)
    print(f"🔄 Starting iteration {iteration}")

@agent.on(AgentEvents.EXECUTE_ITERATION_AFTER)
def after_iteration(ctx: EventContext[ExecuteIterationParams, None]):
    iteration = ctx.parameters.get("iteration", 0)
    print(f"✅ Completed iteration {iteration}")

@agent.on(AgentEvents.EXECUTE_AFTER)
def on_execute_end(ctx):
    print("🏁 Agent execution completed")
```

## Component Events

### Extension Integration

Handle component lifecycle and errors:

```python
from good_agent.events import ExtensionInstallParams, ExtensionErrorParams

@agent.on(AgentEvents.EXTENSION_INSTALL_AFTER)
def on_extension_installed(ctx: EventContext[ExtensionInstallParams, None]):
    extension = ctx.parameters["extension"]
    print(f"📦 Installed extension: {type(extension).__name__}")

@agent.on(AgentEvents.EXTENSION_ERROR)
def on_extension_error(ctx: EventContext[ExtensionErrorParams, None]):
    extension = ctx.parameters["extension"]
    error = ctx.parameters["error"]
    context = ctx.parameters["context"]
    
    print(f"⚠️ Extension {type(extension).__name__} error in {context}: {error}")
```

## Advanced Event Patterns

### Conditional Event Handling

Use predicates to filter events:

```python
def only_user_messages(ctx):
    """Predicate to only handle user messages."""
    message = ctx.parameters.get("message")
    return message and message.role == "user"

@agent.on(AgentEvents.MESSAGE_APPEND_AFTER, predicate=only_user_messages)
def handle_user_messages(ctx):
    message = ctx.parameters["message"]
    print(f"User said: {message.content}")
```

### Event Chaining

Trigger additional events based on conditions:

```python
@agent.on(AgentEvents.TOOL_CALL_AFTER)
async def chain_events(ctx):
    tool_name = ctx.parameters["tool_name"]
    success = ctx.parameters["success"]
    
    if tool_name == "search" and success:
        # Emit custom event for successful searches
        await agent.events.apply("search:success", 
                                 result=ctx.parameters["response"])

# Handle custom event
@agent.on("search:success")
def on_successful_search(ctx):
    result = ctx.parameters["result"]
    print(f"Search succeeded with {len(result.response)} results")
```

### Interrupting Event Flows

Stop event propagation or cancel operations:

```python
from good_agent.core.event_router import ApplyInterrupt

@agent.on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
def security_check(ctx):
    tool_name = ctx.parameters["tool_name"]
    
    # Block dangerous tools
    if tool_name in ["delete_file", "system_command"]:
        print(f"⛔ Blocked dangerous tool: {tool_name}")
        raise ApplyInterrupt("Security policy violation")
```

## Event-Based Components

### Creating Reactive Components

Build components that respond to events:

```python
from good_agent import AgentComponent
from good_agent.events import AgentEvents

class LoggingComponent(AgentComponent):
    def __init__(self, log_file: str = "agent.log"):
        super().__init__()
        self.log_file = log_file
        
    async def install(self, agent):
        await super().install(agent)
        
        # Set up event handlers during installation
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def log_message(ctx):
            message = ctx.parameters["message"]
            with open(self.log_file, "a") as f:
                f.write(f"{message.role}: {message.content}\n")
        
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def log_tool_call(ctx):
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            with open(self.log_file, "a") as f:
                f.write(f"Tool {tool_name}: {'✅' if success else '❌'}\n")

# Usage
logger = LoggingComponent("session.log")
async with Agent("Assistant", extensions=[logger]) as agent:
    # All messages and tool calls will be logged
    await agent.call("Hello world!")
```

### Stateful Event Handlers

Maintain state across event invocations:

```python
class MetricsComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.message_count = 0
        self.tool_calls = 0
        self.errors = 0
        
    async def install(self, agent):
        await super().install(agent)
        
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def count_message(ctx):
            self.message_count += 1
        
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def count_tool_call(ctx):
            self.tool_calls += 1
            if not ctx.parameters["success"]:
                self.errors += 1
    
    def get_stats(self) -> dict:
        return {
            "messages": self.message_count,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "success_rate": (self.tool_calls - self.errors) / max(1, self.tool_calls)
        }

# Usage
metrics = MetricsComponent()
async with Agent("Assistant", extensions=[metrics]) as agent:
    await agent.call("Do some work")
    stats = metrics.get_stats()
    print(f"Session stats: {stats}")
```

## Event Testing

### Testing Event Handlers

Test that events are emitted and handled correctly:

```python
import pytest
from unittest.mock import Mock

@pytest.mark.asyncio
async def test_message_event_handling():
    async with Agent("Test agent") as agent:
        # Set up mock handler
        handler = Mock()
        agent.on(AgentEvents.MESSAGE_APPEND_AFTER)(handler)
        
        # Trigger event
        agent.append("Test message")
        
        # Verify handler was called
        handler.assert_called_once()
        call_args = handler.call_args[0][0]  # EventContext
        assert call_args.parameters["message"].content == "Test message"

@pytest.mark.asyncio
async def test_tool_event_modification():
    from good_agent import tool
    
    @tool
    def test_tool(value: int) -> int:
        return value * 2
    
    async with Agent("Test agent", tools=[test_tool]) as agent:
        # Handler that modifies arguments
        @agent.on(AgentEvents.TOOL_CALL_BEFORE)
        def modify_args(ctx):
            args = ctx.parameters["arguments"]
            if "value" in args:
                modified = args.copy()
                modified["value"] = 10  # Force value to 10
                ctx.output = modified
                return modified
        
        # Invoke tool with different value
        result = await agent.tool_calls.invoke(test_tool, value=5)
        
        # Should use modified value (10 * 2 = 20)
        assert result.response == 20
```

### Event Mocking

Mock events for testing components:

```python
@pytest.mark.asyncio
async def test_component_event_handling():
    component = LoggingComponent("test.log")
    agent = Agent("Test")
    await component.install(agent)
    
    # Emit test event
    await agent.events.apply(AgentEvents.MESSAGE_APPEND_AFTER,
                           message=UserMessage("Test"),
                           agent=agent)
    
    # Verify logging occurred
    with open("test.log") as f:
        content = f.read()
        assert "user: Test" in content
```

## Performance Considerations

### Event Handler Performance

- **Keep handlers lightweight** - Avoid heavy computation in event handlers
- **Use async handlers** for I/O operations to prevent blocking
- **Consider priorities** - High-priority handlers can impact performance
- **Minimize event subscriptions** - Only subscribe to events you need

```python
# ❌ Heavy computation in handler
@agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
def slow_handler(ctx):
    time.sleep(5)  # Blocks entire event system
    heavy_computation()

# ✅ Lightweight handler with background processing
@agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
async def fast_handler(ctx):
    # Quick processing
    message = ctx.parameters["message"]
    
    # Delegate heavy work to background task
    asyncio.create_task(process_message_background(message))
```

### Event System Optimization

```python
# Batch related events when possible
class BatchProcessor(AgentComponent):
    def __init__(self, batch_size: int = 10):
        super().__init__()
        self.batch_size = batch_size
        self.message_buffer = []
        
    async def install(self, agent):
        await super().install(agent)
        
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def buffer_message(ctx):
            self.message_buffer.append(ctx.parameters["message"])
            
            if len(self.message_buffer) >= self.batch_size:
                self.process_batch()
    
    def process_batch(self):
        # Process messages in batches for efficiency
        messages = self.message_buffer.copy()
        self.message_buffer.clear()
        
        # Batch processing logic
        print(f"Processing batch of {len(messages)} messages")
```

## Complete Example

Here's a comprehensive example showing multiple event patterns:

```python
--8<-- "examples/events/basic_events.py"
```

## Best Practices

### Event Handler Design

- **Single responsibility** - Each handler should have one clear purpose
- **Idempotent operations** - Handlers should be safe to call multiple times
- **Error handling** - Always handle exceptions in event handlers
- **Clear naming** - Use descriptive handler names that indicate their purpose

### Event System Architecture

- **Use components** for complex event handling logic
- **Prefer composition** over inheritance for event-driven features
- **Document side effects** - Make it clear when handlers modify state
- **Consider event ordering** - Use priorities when handler order matters

### Debugging Events

```python
# Enable event debugging
import logging
logging.getLogger("good_agent.events").setLevel(logging.DEBUG)

# Add debug handler to see all events
@agent.on("*")  # Listen to all events
def debug_all_events(ctx):
    event_name = ctx.event_name
    params = list(ctx.parameters.keys())
    print(f"Event: {event_name} with params: {params}")
```

## Troubleshooting

### Common Issues

```python
# ❌ Handler not called
@agent.on("typo:event:name")  # Wrong event name
def handler(ctx): pass

# ✅ Use correct event names from AgentEvents
@agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
def handler(ctx): pass

# ❌ Handler exceptions breaking event chain
@agent.on(AgentEvents.TOOL_CALL_AFTER)
def bad_handler(ctx):
    raise ValueError("Oops")  # Breaks other handlers

# ✅ Handle exceptions gracefully
@agent.on(AgentEvents.TOOL_CALL_AFTER)
def good_handler(ctx):
    try:
        # Handler logic
        pass
    except Exception as e:
        print(f"Handler error: {e}")
        # Don't re-raise unless intentionally interrupting
```

### Event Debugging

```python
# Check if handlers are registered
print(f"Handlers for MESSAGE_APPEND_AFTER: {len(agent.events._handlers.get(AgentEvents.MESSAGE_APPEND_AFTER, []))}")

# Log all event emissions
@agent.on("*", priority=1000)  # Highest priority
def event_logger(ctx):
    print(f"Event emitted: {ctx.event_name}")
```

## Next Steps

- **[Agent Modes](../features/modes.md)** - Use events in mode-specific contexts
- **[Components](../extensibility/components.md)** - Build event-driven agent components
- **[Interactive Execution](../features/interactive-execution.md)** - Handle execution events
- **[Multi-Agent](../features/multi-agent.md)** - Event coordination across multiple agents
