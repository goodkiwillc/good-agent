# Interactive Execution

Good Agent provides granular control over the agent's execution lifecycle through the `agent.execute()` method, enabling you to process messages and events step-by-step as they are generated. This is essential for building responsive UIs, handling long-running workflows, and implementing custom tool approval flows.

## Overview

### Key Concepts

- **Step-by-Step Execution** - Process the agent's reasoning loop one event at a time
- **Event Iterator** - Iterate over `AssistantMessage`, `ToolMessage`, and other events
- **Pattern Matching** - Use Python's `match/case` syntax for elegant message handling
- **Interactive Control** - Pause execution for user input or tool approval
- **Real-time UIs** - Update interfaces immediately as the agent thinks and acts

### Execute vs Call

Good Agent provides two main execution methods:

- **`agent.call()`** - One-shot method that runs until completion and returns the final result
- **`agent.execute()`** - Iterator method that yields each message as it is generated during the execution loop

```python
from good_agent import Agent

async with Agent("You are a helpful assistant.") as agent:
    # One-shot: Get final result
    result = await agent.call("What's 2 + 2?")
    print(result.content)  # "4"
    
    # Interactive: Process each message
    async for message in agent.execute("Calculate 2 + 2 and explain"):
        print(f"{message.role}: {message.content}")
```

## Basic Iteration

### Simple Message Processing

Iterate through the agent's execution and handle each message:

```python
from good_agent import Agent, tool

@tool
async def calculate(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)  # In production, use a safe evaluator

async with Agent("You are a math assistant.", tools=[calculate]) as agent:
    async for message in agent.execute("What's 15 * 8 + 32?"):
        print(f"{message.role.upper()}: {message.content}")
```

Output:
```
ASSISTANT: I'll calculate 15 * 8 + 32 for you.
TOOL: 152.0
ASSISTANT: 15 * 8 + 32 = 152
```

### Accessing Message Properties

Each message provides rich metadata for processing:

```python
async with Agent("Assistant with tools", tools=[calculate]) as agent:
    async for message in agent.execute("Calculate 10 + 5 and 20 * 3"):
        print(f"Message #{message.iteration_index}: {message.role}")
        print(f"Content: {message.content}")
        print(f"Timestamp: {message.created_at}")
        
        # Tool-specific properties
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                print(f"Tool: {tool_call.function.name}")
                print(f"Args: {tool_call.function.arguments}")
        
        if hasattr(message, 'tool_name'):
            print(f"Tool used: {message.tool_name}")
            print(f"Result: {message.tool_response}")
        
        print("---")
```

## Pattern Matching with Messages

### Using Match/Case for Message Types

Python's pattern matching provides elegant message handling:

```python
from good_agent.messages import AssistantMessage, ToolMessage

@tool
async def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Search results for '{query}': [mock results]"

@tool 
async def save_note(content: str) -> str:
    """Save a note for later."""
    return f"Note saved: {content}"

async with Agent("Research assistant", tools=[search_web, save_note]) as agent:
    async for message in agent.execute("Search for Python tutorials and save a note"):
        match message:
            case AssistantMessage(content=text) if message.tool_calls:
                print(f"🤖 Planning: {text}")
                for tool_call in message.tool_calls:
                    print(f"  → Will call: {tool_call.function.name}")
                    
            case AssistantMessage(content=text):
                print(f"🤖 Response: {text}")
                
            case ToolMessage(tool_name=name, content=result):
                print(f"🛠️  {name} → {result}")
                
            case _:
                print(f"📨 Other message: {message.role}")
```

### Advanced Pattern Matching

Handle specific tool patterns and message combinations:

```python
from good_agent.messages import UserMessage, SystemMessage

@tool
async def get_weather(location: str) -> dict:
    """Get weather information."""
    return {"temp": 72, "condition": "sunny", "location": location}

@tool
async def book_flight(departure: str, destination: str) -> str:
    """Book a flight."""
    return f"Flight booked from {departure} to {destination}"

async with Agent("Travel agent", tools=[get_weather, book_flight]) as agent:
    async for message in agent.execute("Check weather in Paris and book a flight there from NYC"):
        match message:
            case AssistantMessage() if "weather" in message.content.lower():
                print("🌤️  Getting weather information...")
                
            case ToolMessage(tool_name="get_weather", content=weather_data):
                temp = weather_data.get("temp", "unknown")
                condition = weather_data.get("condition", "unknown")
                location = weather_data.get("location", "unknown")
                print(f"🌡️  {location}: {temp}°F, {condition}")
                
            case ToolMessage(tool_name="book_flight", content=booking_info):
                print(f"✈️  {booking_info}")
                
            case AssistantMessage(tool_calls=calls) if calls:
                for call in calls:
                    if call.function.name == "book_flight":
                        print("✈️  Booking flight...")
                    elif call.function.name == "get_weather":
                        print("🌤️  Checking weather...")
                        
            case AssistantMessage(content=text):
                print(f"🎯 Final answer: {text}")
```

## Iteration Control

### Max Iterations and Early Termination

Control how long the agent runs:

```python
async with Agent("Research assistant", tools=[search_web]) as agent:
    iteration_count = 0
    
    async for message in agent.execute("Research AI trends", max_iterations=3):
        iteration_count += 1
        print(f"Iteration {iteration_count}: {message.role}")
        
        # Early termination based on content
        if "final report" in message.content.lower():
            print("Research complete!")
            break
            
        # Warning for long-running processes
        if iteration_count > 2:
            print("⚠️ Agent is taking multiple iterations...")
```

### Conditional Processing

Process messages conditionally based on context:

```python
approved_tools = {"search", "calculate", "get_weather"}
pending_approvals = []

async with Agent("Controlled assistant", tools=[search_web, calculate]) as agent:
    async for message in agent.execute("Search for weather data and calculate averages"):
        match message:
            case AssistantMessage(tool_calls=calls) if calls:
                # Check if tools need approval
                for call in calls:
                    tool_name = call.function.name
                    if tool_name not in approved_tools:
                        print(f"⚠️ Tool '{tool_name}' requires approval")
                        pending_approvals.append(call)
                    else:
                        print(f"✅ Auto-approved: {tool_name}")
                        
            case ToolMessage(tool_name=name, success=True):
                print(f"✅ {name} completed successfully")
                
            case ToolMessage(tool_name=name, success=False, content=error):
                print(f"❌ {name} failed: {error}")
```

## Real-Time UI Updates

### Building Responsive Interfaces

Create responsive UIs that update as the agent works:

```python
import asyncio
from datetime import datetime

class ConsoleUI:
    def __init__(self):
        self.message_count = 0
        self.start_time = datetime.now()
        
    def display_header(self):
        print("=" * 60)
        print("🤖 GOOD AGENT INTERACTIVE DEMO")
        print("=" * 60)
        
    def display_message(self, message, elapsed_time):
        self.message_count += 1
        timestamp = f"[{elapsed_time:.1f}s]"
        
        match message:
            case AssistantMessage(content=text, tool_calls=calls):
                if calls:
                    print(f"{timestamp} 🤖 THINKING: {text}")
                    for call in calls:
                        args = call.function.arguments
                        print(f"{timestamp} 🛠️  CALLING: {call.function.name}({args})")
                else:
                    print(f"{timestamp} 🤖 RESPONSE: {text}")
                    
            case ToolMessage(tool_name=name, content=result):
                # Truncate long results for UI
                display_result = str(result)
                if len(display_result) > 100:
                    display_result = display_result[:100] + "..."
                print(f"{timestamp} ⚙️  RESULT: {name} → {display_result}")
                
            case _:
                print(f"{timestamp} 📨 {message.role.upper()}: {message.content}")
    
    def display_footer(self):
        total_time = (datetime.now() - self.start_time).total_seconds()
        print("=" * 60)
        print(f"✅ Completed {self.message_count} messages in {total_time:.1f}s")
        print("=" * 60)

# Usage
async def interactive_demo():
    ui = ConsoleUI()
    ui.display_header()
    
    async with Agent("Demo assistant", tools=[calculate, search_web]) as agent:
        async for message in agent.execute("Calculate 15 * 8 and search for Python tutorials"):
            elapsed = (datetime.now() - ui.start_time).total_seconds()
            ui.display_message(message, elapsed)
            
            # Add small delay for demo effect
            await asyncio.sleep(0.1)
    
    ui.display_footer()

# Run the demo
await interactive_demo()
```

### Progress Tracking

Track agent progress through complex workflows:

```python
class ProgressTracker:
    def __init__(self):
        self.steps = []
        self.current_step = 0
        
    def add_step(self, description: str):
        self.steps.append({"desc": description, "status": "pending"})
        
    def complete_step(self, index: int):
        if 0 <= index < len(self.steps):
            self.steps[index]["status"] = "completed"
            
    def display_progress(self):
        print("\n📊 PROGRESS:")
        for i, step in enumerate(self.steps):
            status = "✅" if step["status"] == "completed" else "⏳"
            current = "👈" if i == self.current_step else "  "
            print(f"  {status} {step['desc']} {current}")
        print()

tracker = ProgressTracker()
tracker.add_step("Search for information")  
tracker.add_step("Analyze results")
tracker.add_step("Generate summary")

async with Agent("Research assistant", tools=[search_web]) as agent:
    async for message in agent.execute("Research and summarize AI trends"):
        match message:
            case ToolMessage(tool_name="search_web"):
                tracker.complete_step(0)
                tracker.current_step = 1
                tracker.display_progress()
                
            case AssistantMessage() if "analysis" in message.content.lower():
                tracker.complete_step(1)
                tracker.current_step = 2
                tracker.display_progress()
                
            case AssistantMessage() if not message.tool_calls:
                tracker.complete_step(2)
                tracker.display_progress()
                print("🎉 Research complete!")
```

## Interactive Tool Approval

### Manual Tool Approval Workflow

Implement approval workflows for sensitive operations:

```python
import asyncio

@tool
async def send_email(recipient: str, subject: str, body: str) -> str:
    """Send an email."""
    return f"Email sent to {recipient}"

@tool  
async def delete_file(filepath: str) -> str:
    """Delete a file."""
    return f"Deleted {filepath}"

@tool
async def make_purchase(item: str, amount: float) -> str:
    """Make a purchase."""
    return f"Purchased {item} for ${amount}"

dangerous_tools = {"send_email", "delete_file", "make_purchase"}

async def get_user_approval(tool_name: str, args: dict) -> bool:
    """Simulate user approval (in real app, this would be a UI prompt)."""
    print(f"\n🚨 APPROVAL REQUIRED:")
    print(f"Tool: {tool_name}")
    print(f"Arguments: {args}")
    
    # Simulate user input (in real app, get from UI)
    response = input("Approve this action? (y/n): ").lower().strip()
    return response == 'y'

async with Agent("Assistant with dangerous tools", 
                 tools=[send_email, delete_file, make_purchase]) as agent:
    
    async for message in agent.execute("Send a thank you email to user@example.com"):
        match message:
            case AssistantMessage(tool_calls=calls) if calls:
                # Check each tool call for approval
                for call in calls:
                    tool_name = call.function.name
                    
                    if tool_name in dangerous_tools:
                        args = eval(call.function.arguments)  # In production, use json.loads
                        approved = await get_user_approval(tool_name, args)
                        
                        if not approved:
                            print(f"❌ Tool '{tool_name}' was rejected by user")
                            # In a real implementation, you'd modify the tool call or skip execution
                        else:
                            print(f"✅ Tool '{tool_name}' approved")
                            
            case ToolMessage(tool_name=name, success=True):
                print(f"✅ Executed: {name}")
                
            case ToolMessage(tool_name=name, success=False, content=error):
                print(f"❌ Failed: {name} - {error}")
                
            case AssistantMessage(content=text):
                print(f"🤖 {text}")
```

## Error Handling

### Graceful Error Recovery

Handle errors during the execution loop:

```python
import logging
from good_agent.exceptions import ToolExecutionError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
async def unreliable_tool(data: str) -> str:
    """A tool that sometimes fails."""
    if "error" in data.lower():
        raise Exception("Simulated tool failure")
    return f"Processed: {data}"

async def robust_execution(agent, query: str):
    """Run with comprehensive error handling."""
    try:
        message_count = 0
        successful_tools = 0
        failed_tools = 0
        
        async for message in agent.execute(query, max_iterations=5):
            message_count += 1
            logger.info(f"Processing message #{message_count}: {message.role}")
            
            match message:
                case AssistantMessage(content=text):
                    print(f"🤖 {text}")
                    
                case ToolMessage(tool_name=name, success=True):
                    successful_tools += 1
                    print(f"✅ {name} succeeded")
                    
                case ToolMessage(tool_name=name, success=False, content=error):
                    failed_tools += 1
                    print(f"❌ {name} failed: {error}")
                    logger.warning(f"Tool failure: {name} - {error}")
                    
                case _:
                    logger.info(f"Other message type: {type(message)}")
                    
    except ToolExecutionError as e:
        logger.error(f"Tool execution error: {e}")
        print(f"🚨 Critical tool error: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}")
        print(f"🚨 Unexpected error: {e}")
        
    finally:
        print(f"\n📊 Session summary:")
        print(f"  Total messages: {message_count}")
        print(f"  Successful tools: {successful_tools}")
        print(f"  Failed tools: {failed_tools}")

# Usage
async with Agent("Error-prone assistant", tools=[unreliable_tool]) as agent:
    await robust_execution(agent, "Process this data and handle any error data")
```

### Timeout Handling

Implement timeouts for long-running executions:

```python
async def execution_with_timeout(agent, query: str, timeout_seconds: int = 30):
    """Run with timeout protection."""
    try:
        async with asyncio.timeout(timeout_seconds):
            async for message in agent.execute(query):
                print(f"{message.role}: {message.content}")
                
                # Simulate processing delay
                await asyncio.sleep(0.1)
                
    except asyncio.TimeoutError:
        print(f"🕐 Execution timed out after {timeout_seconds} seconds")
        print("🛑 Stopping agent execution")
        
    except Exception as e:
        print(f"🚨 Error during execution: {e}")

# Usage with timeout
async with Agent("Slow assistant") as agent:
    await execution_with_timeout(agent, "Process complex data", timeout_seconds=10)
```

## Advanced Patterns

### Message Buffering and Batching

Buffer messages for batch processing:

```python
from collections import deque
import asyncio

class MessageBuffer:
    def __init__(self, batch_size: int = 5, flush_interval: float = 2.0):
        self.buffer = deque()
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.last_flush = asyncio.get_event_loop().time()
        
    def add_message(self, message):
        self.buffer.append(message)
        
    def should_flush(self) -> bool:
        current_time = asyncio.get_event_loop().time()
        return (
            len(self.buffer) >= self.batch_size or 
            (current_time - self.last_flush) >= self.flush_interval
        )
        
    def flush(self) -> list:
        messages = list(self.buffer)
        self.buffer.clear()
        self.last_flush = asyncio.get_event_loop().time()
        return messages

async def buffered_execution():
    buffer = MessageBuffer(batch_size=3, flush_interval=1.5)
    
    async with Agent("Buffered assistant", tools=[calculate]) as agent:
        async for message in agent.execute("Calculate 1+1, 2+2, and 3+3"):
            buffer.add_message(message)
            
            if buffer.should_flush():
                batch = buffer.flush()
                print(f"\n📦 Processing batch of {len(batch)} messages:")
                
                for msg in batch:
                    print(f"  - {msg.role}: {msg.content[:50]}...")
                    
                # Simulate batch processing
                await asyncio.sleep(0.5)
                print("✅ Batch processed\n")
        
        # Flush remaining messages
        if buffer.buffer:
            final_batch = buffer.flush()
            print(f"📦 Final batch: {len(final_batch)} messages")

await buffered_execution()
```

### Concurrent Message Processing

Process multiple agent executions concurrently:

```python
async def concurrent_agents():
    """Run multiple agents concurrently and process their event loops."""
    
    async def process_agent_loop(agent_name: str, agent, query: str):
        """Process a single agent's execution loop."""
        print(f"🚀 Starting {agent_name}")
        
        async for message in agent.execute(query, max_iterations=3):
            print(f"[{agent_name}] {message.role}: {message.content}")
            await asyncio.sleep(0.1)  # Simulate processing time
            
        print(f"✅ {agent_name} completed")
    
    # Create multiple agents
    math_agent = Agent("Math specialist", tools=[calculate])
    research_agent = Agent("Research specialist", tools=[search_web])
    
    await math_agent.initialize()
    await research_agent.initialize()
    
    # Run agents concurrently
    await asyncio.gather(
        process_agent_loop("MATH", math_agent, "Calculate 15 * 8"),
        process_agent_loop("RESEARCH", research_agent, "Search for Python news"),
    )
    
    await math_agent.close()
    await research_agent.close()

await concurrent_agents()
```

## Event System Integration

### Monitoring Execution with Events

Combine the execution loop with the event system for advanced monitoring:

```python
from good_agent.events import AgentEvents
from good_agent.core.event_router import EventContext

async with Agent("Event-monitored assistant", tools=[calculate]) as agent:
    # Set up event handlers
    @agent.on(AgentEvents.EXECUTE_ITERATION_BEFORE)
    def before_iteration(ctx: EventContext):
        iteration = ctx.parameters.get("iteration", 0)
        print(f"🔄 Starting iteration {iteration + 1}")
        
    @agent.on(AgentEvents.TOOL_CALL_BEFORE)  
    def before_tool_call(ctx: EventContext):
        tool_name = ctx.parameters["tool_name"]
        args = ctx.parameters["arguments"]
        print(f"🛠️  About to call {tool_name} with {args}")
        
    @agent.on(AgentEvents.TOOL_CALL_AFTER)
    def after_tool_call(ctx: EventContext):
        tool_name = ctx.parameters["tool_name"]
        success = ctx.parameters["success"]
        duration = ctx.parameters.get("duration", 0)
        print(f"⚙️  Tool {tool_name} {'✅' if success else '❌'} ({duration:.2f}s)")
    
    # Run execution with event monitoring
    async for message in agent.execute("Calculate 25 * 4 + 10"):
        print(f"📨 Message: {message.role} - {message.content}")
```

## Performance and Optimization

### Execution Performance Tips

Optimize execution speed for production use:

```python
import time
from typing import AsyncGenerator

class PerformanceMonitor:
    def __init__(self):
        self.start_time = None
        self.message_times = []
        self.total_messages = 0
        
    def start(self):
        self.start_time = time.time()
        
    def record_message(self):
        if self.start_time:
            self.message_times.append(time.time() - self.start_time)
            self.total_messages += 1
            
    def get_stats(self) -> dict:
        if not self.message_times:
            return {}
            
        return {
            "total_time": self.message_times[-1] if self.message_times else 0,
            "total_messages": self.total_messages,
            "avg_time_per_message": sum(self.message_times) / len(self.message_times),
            "messages_per_second": self.total_messages / (self.message_times[-1] or 1)
        }

async def optimized_execution(query: str) -> AsyncGenerator:
    """Optimized execution with performance monitoring."""
    monitor = PerformanceMonitor()
    monitor.start()
    
    async with Agent("Optimized assistant", tools=[calculate]) as agent:
        async for message in agent.execute(query, max_iterations=10):
            monitor.record_message()
            
            # Yield immediately for low latency
            yield message
            
            # Optional: Add batching for high-throughput scenarios
            if monitor.total_messages % 100 == 0:
                stats = monitor.get_stats()
                print(f"📊 Performance: {stats['messages_per_second']:.1f} msg/sec")

# Usage
async for msg in optimized_execution("Do complex calculations"):
    print(f"Fast processing: {msg.role}")
```

## Complete Examples

Here are comprehensive examples showing advanced execution patterns:

```python
--8<-- "examples/streaming/advanced_streaming.py"
```

## Best Practices

### Architecture Guidelines

- **Handle all message types** - Always include patterns for AssistantMessage and ToolMessage
- **Implement timeouts** - Prevent infinite loops in production systems  
- **Buffer appropriately** - Balance responsiveness with processing efficiency
- **Monitor performance** - Track message rates and processing times
- **Graceful error handling** - Continue execution even when individual tools fail
- **User experience** - Provide visual feedback for long-running operations

### Production Considerations

```python
async def production_execution(agent, query: str):
    """Production-ready execution with all best practices."""
    
    # Configuration
    MAX_ITERATIONS = 20
    MESSAGE_TIMEOUT = 60
    PROGRESS_UPDATE_INTERVAL = 5
    
    start_time = time.time()
    message_count = 0
    last_progress_update = start_time
    
    try:
        async with asyncio.timeout(MESSAGE_TIMEOUT):
            async for message in agent.execute(query, max_iterations=MAX_ITERATIONS):
                message_count += 1
                current_time = time.time()
                
                # Progress updates
                if current_time - last_progress_update >= PROGRESS_UPDATE_INTERVAL:
                    elapsed = current_time - start_time
                    print(f"📊 Progress: {message_count} messages in {elapsed:.1f}s")
                    last_progress_update = current_time
                
                # Process message with comprehensive error handling
                try:
                    match message:
                        case AssistantMessage(content=text, tool_calls=calls):
                            if calls:
                                print(f"🤖 Planning: {text}")
                            else:
                                print(f"🤖 Response: {text}")
                                
                        case ToolMessage(tool_name=name, success=True, content=result):
                            print(f"✅ {name}: Success")
                            
                        case ToolMessage(tool_name=name, success=False, content=error):
                            print(f"❌ {name}: {error}")
                            # Log error but continue execution
                            logger.warning(f"Tool {name} failed: {error}")
                            
                        case _:
                            print(f"📨 Other: {message.role}")
                            
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue  # Continue with next message
                    
    except asyncio.TimeoutError:
        print(f"⏰ Execution timeout after {MESSAGE_TIMEOUT}s")
    except Exception as e:
        logger.error(f"Execution error: {e}")
    finally:
        total_time = time.time() - start_time
        print(f"📈 Final stats: {message_count} messages in {total_time:.1f}s")
```

## Next Steps

- **[Agent Modes](./modes.md)** - Learn about execution in different agent modes
- **[Events](../core/events.md)** - Monitor execution with events
- **[Multi-Agent](./multi-agent.md)** - Coordinate execution across multiple agents  
- **[Human-in-the-Loop](./human-in-the-loop.md)** - Build interactive approval workflows
- **[Tools](../core/tools.md)** - Understand tool execution in interactive contexts
