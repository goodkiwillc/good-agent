# Messages & History

Good Agent provides a sophisticated message system for managing conversation history, with strong typing, role-based filtering, and powerful content handling. This page covers message types, history management, and advanced message operations.

## Message Types

Good Agent supports four core message types, each with specific capabilities and use cases:

### User Messages

Represent input from users, including text and images:

```python
from good_agent.messages import UserMessage

# Text-only message  
user_msg = UserMessage("Hello, how are you?")

# Multi-part content
user_msg = UserMessage("Analyze this image", images=["path/to/image.jpg"])

# With image detail settings
user_msg = UserMessage(
    "What's in this image?",
    images=["image.jpg"],
    image_detail="high"  # "auto", "low", "high"
)
```

### System Messages

Provide instructions and context to the LLM:

```python
from good_agent.messages import SystemMessage

# Basic system message
system_msg = SystemMessage("You are a helpful assistant.")

# With templating
system_msg = SystemMessage(
    "You are an expert in {{domain}}",
    context={"domain": "machine learning"}
)
```

### Assistant Messages

Represent responses from the LLM, including tool calls:

```python
from good_agent.messages import AssistantMessage
from good_agent.tools import ToolCall

# Text response
assistant_msg = AssistantMessage("I'm doing well, thank you!")

# With tool calls
assistant_msg = AssistantMessage(
    "Let me calculate that for you.",
    tool_calls=[ToolCall(id="call_123", function={"name": "calculator", "arguments": "{}"})]
)

# With reasoning (o1 models)
assistant_msg = AssistantMessage(
    "The answer is 42.",
    reasoning="I need to think about this carefully..."
)

# With citations
assistant_msg = AssistantMessage(
    "According to recent research...",
    citations=["https://example.com/paper.pdf"]
)
```

### Tool Messages

Contain results from tool execution:

```python
from good_agent.messages import ToolMessage

# Basic tool result
tool_msg = ToolMessage(
    "Result: 42",
    tool_call_id="call_123",
    tool_name="calculator"
)

# With structured response
tool_msg = ToolMessage(
    content="Calculation complete",
    tool_call_id="call_123", 
    tool_name="calculator",
    tool_response=calculator_result  # ToolResponse object
)
```

## Message Lists & History

### Basic Message Access

Agents provide array-like access to their message history:

```python
async with Agent("Assistant") as agent:
    agent.append("Hello")
    agent.append("How are you?", role="user")
    
    # Array-style access
    first_msg = agent[0]      # System message (if present)
    last_msg = agent[-1]      # Most recent message
    recent = agent[-3:]       # Last 3 messages
    
    # Length and iteration
    count = len(agent)        # Total message count
    for msg in agent:         # Iterate all messages
        print(f"{msg.role}: {msg.content}")
```

### Role-Based Filtering

Access messages by role using filtered views:

```python
async with Agent("Assistant") as agent:
    agent.append("What is 2+2?")
    
    # Role-specific views (FilteredMessageList)
    user_messages = agent.user          # All user messages
    assistant_messages = agent.assistant # All assistant messages
    tool_messages = agent.tool          # All tool messages
    system_message = agent.system       # System message (single)
    
    # Access specific messages
    last_user = agent.user[-1]          # Latest user message
    first_assistant = agent.assistant[0] # First assistant response
    
    # Check content
    if agent.user[-1].content == "What is 2+2?":
        print("Last user asked about math")
```

### Filtered List Operations

Role views provide convenient operations:

```python
async with Agent("Assistant") as agent:
    # Append with automatic role setting
    agent.user.append("Hello!")           # Creates UserMessage
    agent.assistant.append("Hi there!")   # Creates AssistantMessage
    agent.tool.append(                    # Creates ToolMessage
        "Result: 42",
        tool_call_id="call_123",
        tool_name="calculator"
    )
    
    # Get content of first message in each role
    user_content = agent.user.content        # First user message content
    assistant_content = agent.assistant.content  # First assistant message content
```

### System Message Management

System messages have special handling:

```python
async with Agent() as agent:  # No initial system message
    # Set system message
    agent.system.set("You are a helpful assistant")
    
    # Or with config parameters
    agent.system.set(
        "You are a creative writer",
        temperature=0.8,    # Applied to agent config
        max_tokens=2000     # Applied to agent config
    )
    
    # Access system message
    if agent[0] and agent[0].role == "system":
        print(f"System prompt: {agent[0].content}")
```

## Message Content & Rendering

### Content Types

Messages support rich content beyond simple strings:

```python
from good_agent.content import TextContentPart, ImageContentPart, FileContentPart

# Multi-part content
agent.append(
    TextContentPart(text="Analyze this image:"),
    ImageContentPart(url="https://example.com/image.jpg"),
    FileContentPart(path="/path/to/document.pdf")
)

# Template variables in content
agent.append(
    "The weather in {{city}} is {{temp}}°F",
    context={"city": "Paris", "temp": 72}
)
```

### Render Modes

Messages can be rendered in different ways:

```python
from good_agent.content import RenderMode

# Different render modes
display_content = msg.render(RenderMode.DISPLAY)    # For UI display
llm_content = msg.render(RenderMode.LLM)           # For LLM consumption  
raw_content = msg.render(RenderMode.RAW)           # Raw, unprocessed

# Default rendering
content = msg.content  # Usually same as DISPLAY mode
```

### Message Metadata

Messages carry rich metadata:

```python
# Message properties
print(f"ID: {msg.id}")              # Unique ULID
print(f"Role: {msg.role}")          # Message role
print(f"Timestamp: {msg.timestamp}")# Creation time
print(f"Content: {msg.content}")    # Rendered content

# Assistant message specifics
if isinstance(msg, AssistantMessage):
    print(f"Tool calls: {msg.tool_calls}")
    print(f"Reasoning: {msg.reasoning}")
    print(f"Citations: {msg.citations}")

# Tool message specifics
if isinstance(msg, ToolMessage):
    print(f"Tool name: {msg.tool_name}")
    print(f"Call ID: {msg.tool_call_id}")
    print(f"Response: {msg.tool_response}")
```

## Message Operations

### Adding Messages

Multiple ways to add messages to an agent:

```python
async with Agent("Assistant") as agent:
    # Simple append (creates UserMessage by default)
    agent.append("Hello!")
    
    # Specify role explicitly
    agent.append("I'm ready to help", role="assistant")
    
    # Multi-part content
    agent.append(
        "Check this image:",
        ImageContentPart(url="image.jpg"),
        role="user"
    )
    
    # With template context
    agent.append(
        "Process {{filename}}",
        context={"filename": "data.csv"},
        role="user"
    )
    
    # Direct message object
    from good_agent.messages import UserMessage
    agent.messages.append(UserMessage("Direct message"))
```

### Message Modification

Messages can be updated after creation:

```python
# Modify message content
agent[-1].content_parts = [TextContentPart(text="Updated content")]

# Add tool calls to assistant message
if isinstance(agent[-1], AssistantMessage):
    agent[-1].tool_calls = [
        ToolCall(id="call_123", function={"name": "search", "arguments": "{}"})
    ]

# Update metadata
agent[-1].annotations = ["important", "verified"]
```

### Message Deletion & Replacement

```python
# Remove last message
agent.messages.pop()

# Remove specific message
del agent[5]  # Remove message at index 5

# Replace message
agent[3] = UserMessage("Replacement message")

# Clear all messages (except system)
system_msg = agent[0] if agent[0] and agent[0].role == "system" else None
agent.messages.clear()
if system_msg:
    agent.messages.append(system_msg)
```

## Message Validation

Good Agent validates message sequences to ensure LLM compatibility:

```python
from good_agent.messages.validation import ValidationMode

async with Agent(
    "Assistant",
    message_validation_mode="strict"  # "strict", "warn", "silent"
) as agent:
    # These operations may trigger validation warnings/errors:
    agent.append("User message")
    agent.append("Another user message")  # May warn about consecutive user messages
    
    # Check validation state
    validation_errors = agent._message_validator.validate(agent.messages)
    if validation_errors:
        print("Validation issues found:", validation_errors)
```

## Advanced Message Patterns

### Message Search & Filtering

```python
# Find messages by content
math_messages = [msg for msg in agent.messages if "math" in msg.content.lower()]

# Find tool messages by tool name
calc_messages = [
    msg for msg in agent.tool 
    if msg.tool_name == "calculator"
]

# Find messages with tool calls
assistant_with_tools = [
    msg for msg in agent.assistant
    if msg.tool_calls
]

# Find recent messages
from datetime import datetime, timedelta
recent_cutoff = datetime.now() - timedelta(minutes=5)
recent_messages = [
    msg for msg in agent.messages
    if msg.timestamp > recent_cutoff
]
```

### Message Transformation

```python
# Create summary of conversation
def summarize_messages(messages):
    summary = []
    for msg in messages:
        if msg.role == "user":
            summary.append(f"User: {msg.content[:50]}...")
        elif msg.role == "assistant":
            summary.append(f"Assistant: {msg.content[:50]}...")
    return "\n".join(summary)

conversation_summary = summarize_messages(agent.messages)

# Export message history
def export_messages(messages):
    return [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "id": str(msg.id)
        }
        for msg in messages
    ]

exported = export_messages(agent.messages)
```

### Message Cloning & Templates

```python
# Clone existing message
original = agent[-1]
clone = type(original)(
    content=original.content,
    **{k: v for k, v in original.model_dump().items() 
       if k not in ['id', 'timestamp']}
)

# Create message templates
def create_error_message(error_text: str) -> AssistantMessage:
    return AssistantMessage(
        f"I encountered an error: {error_text}. Let me try a different approach.",
        annotations=["error", "retry"]
    )

error_msg = create_error_message("API timeout")
agent.messages.append(error_msg)
```

## Message Versioning & History

### Version Tracking

Messages participate in the agent's versioning system:

```python
async with Agent("Assistant") as agent:
    # Initial state
    agent.append("Hello")
    version1 = agent.version_id
    
    # Add more messages
    agent.append("How are you?")
    agent.append("I'm fine, thanks!", role="assistant")
    version2 = agent.version_id
    
    print(f"Version {version1} → {version2}")
    print(f"Current messages: {len(agent)}")
    
    # Revert to earlier version
    agent.revert_to_version(0)  # Back to "Hello" only
    version3 = agent.version_id  # New version created
    
    print(f"After revert: {len(agent)} messages")
    assert version3 != version2  # New version ID
```

### Message Registry

All messages are preserved in an internal registry:

```python
# Access the message registry (read-only)
message_ids = [msg.id for msg in agent.messages]
registry = agent._message_registry

# Get historical messages by ID
for msg_id in message_ids:
    historical_msg = registry.get(msg_id)
    if historical_msg:
        print(f"Found: {historical_msg.content}")
```

## Performance & Memory Management

### Message Limits

For long-running agents, manage message history:

```python
async with Agent("Long-running assistant") as agent:
    # Monitor message count
    if len(agent) > 1000:
        # Keep system message + last 100 messages
        system_msg = agent[0] if agent[0].role == "system" else None
        recent_messages = agent.messages[-100:]
        
        # Clear and rebuild
        agent.messages.clear()
        if system_msg:
            agent.messages.append(system_msg)
        agent.messages.extend(recent_messages)
        
        print(f"Trimmed to {len(agent)} messages")
```

### Efficient Message Access

```python
# Efficient patterns
last_user_msg = agent.user[-1]           # O(n) scan
last_assistant_msg = agent.assistant[-1] # O(n) scan

# More efficient for multiple accesses
user_msgs = list(agent.user)     # Single scan
assistant_msgs = list(agent.assistant)  # Single scan

# Batch operations
for role in ["user", "assistant", "tool"]:
    role_messages = getattr(agent, role)
    print(f"{role}: {len(role_messages)} messages")
```

## Integration with Features

### Structured Output Messages

Messages integrate with structured output:

```python
from pydantic import BaseModel

class Analysis(BaseModel):
    sentiment: str
    confidence: float

# Response includes structured data
response = await agent.call(
    "Analyze: 'I love this!'",
    response_model=Analysis
)

# Access structured output
if isinstance(response, AssistantMessageStructuredOutput):
    analysis = response.structured_output  # Analysis instance
    print(f"Sentiment: {analysis.sentiment}")
```

### Streaming & Messages

Messages are emitted during streaming execution:

```python
agent.append("Complex task")
async for message in agent.execute(streaming=True):
    match message:
        case AssistantMessage(content=text):
            print(f"Assistant: {text}")
        case ToolMessage(tool_name=name, content=result):
            print(f"Tool {name}: {result}")
```

### Event Integration

Messages trigger events throughout their lifecycle:

```python
from good_agent.events import AgentEvents

@agent.on(AgentEvents.MESSAGE_ADDED)
async def on_message_added(ctx):
    message = ctx.parameters["message"]
    print(f"New {message.role} message: {message.content[:50]}")

@agent.on(AgentEvents.AGENT_VERSION_CHANGE)
async def on_version_change(ctx):
    print(f"Message history changed: {ctx.parameters['changes']}")
```

## Best Practices

### Message Organization

- **Use role views** (`agent.user`, `agent.assistant`) for cleaner code
- **Validate message sequences** to ensure LLM compatibility
- **Limit message history** in long-running applications
- **Use structured content** for complex data instead of plain strings

### Performance

- **Batch role-based operations** to minimize filtering overhead
- **Cache message lists** when accessing multiple times
- **Monitor message count** and implement pruning strategies
- **Use message IDs** for efficient lookups in large histories

### Content Management

- **Render appropriately** for the target audience (DISPLAY vs LLM)
- **Template variables** for dynamic content generation
- **Rich content types** for multimodal interactions
- **Validate content** before sending to LLM

## Troubleshooting

### Common Issues

```python
# ❌ Empty system message access
if agent[0]:  # Check existence first
    system_content = agent[0].content

# ❌ Role mismatch
agent.tool.append("Result")  # Missing tool_call_id

# ✅ Proper tool message
agent.tool.append("Result", tool_call_id="call_123", tool_name="calculator")

# ❌ Modifying read-only content
agent[-1].content = "New content"  # Use content_parts instead

# ✅ Proper content update
agent[-1].content_parts = [TextContentPart(text="New content")]
```

### Validation Errors

```python
# Check validation mode
print(agent.config.message_validation_mode)

# Handle validation errors
try:
    agent.append("Problematic message", role="unknown")
except ValueError as e:
    print(f"Validation error: {e}")
    
# Disable validation temporarily
with agent.config(message_validation_mode="silent"):
    agent.append("Experimental message")
```

### Memory Issues

```python
# Monitor memory usage
print(f"Messages: {len(agent)}")
print(f"Versions: {agent._version_manager.version_count}")
print(f"Registry size: {len(agent._message_registry._messages)}")

# Implement cleanup
if len(agent._message_registry._messages) > 5000:
    # Consider creating a fresh agent with recent context
    pass
```

## Next Steps

- **[Tools](tools.md)** - Add function calling capabilities to your agents
- **[Events](events.md)** - React to message lifecycle events  
- **[Structured Output](../features/structured-output.md)** - Extract typed data from assistant messages
- **[Streaming](../features/streaming.md)** - Process messages in real-time during execution
