# Messages & History

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent provides a sophisticated message system for managing conversation history, with strong typing, role-based filtering, and powerful content handling. This page covers message types, history management, and advanced message operations.

## Message Types

Good Agent supports four core message types, each with specific capabilities and use cases:

### User Messages

Represent input from users, including text and images:

```python
--8<-- "examples/docs/messages_user.py"
```

### System Messages

Provide instructions and context to the LLM:

```python
--8<-- "examples/docs/messages_system.py"
```

### Assistant Messages

Represent responses from the LLM, including tool calls:

```python
--8<-- "examples/docs/messages_assistant.py"
```

### Tool Messages

Contain results from tool execution:

```python
--8<-- "examples/docs/messages_tool.py"
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

## Message Templating

Good Agent supports Jinja2-based templating in message content, allowing dynamic variable substitution, context providers, custom filters, and structured content generation.

### Basic Template Variables

Use `{{variable}}` syntax in message content and provide values via the `context` parameter:

```python
# Simple variable substitution
agent.append(
    "The weather in {{city}} is {{temp}}°F",
    context={"city": "Paris", "temp": 72}
)

# System messages with templates
from good_agent.messages import SystemMessage
system_msg = SystemMessage(
    "You are an expert in {{domain}}",
    context={"domain": "machine learning"}
)
```

### Context Providers

Context providers are functions that dynamically supply values to templates. They're called automatically when a template references their variable name.

#### Global Context Providers

Register global context providers that work across all agents:

```python
from good_agent import Agent
from good_agent.agent.context import ContextManager

# Register global context provider
@ContextManager.context_providers("current_user")
def get_current_user():
    return "chris@example.com"

@ContextManager.context_providers("now")
def current_time():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Use in any agent
async with Agent("Current time is {{now}}") as agent:
    # System prompt automatically includes timestamp
    print(agent[0].content)  # "Current time is 2025-11-21 15:30:00"
```

#### Instance Context Providers

Register context providers specific to an agent instance:

```python
async with Agent("Assistant") as agent:
    # Register instance-specific provider
    @agent.context.context_provider("session_id")
    def get_session():
        return "sess_abc123"

    # Use in messages
    agent.append("Session: {{session_id}}")
    # Renders as: "Session: sess_abc123"
```

#### Built-in Context Providers

Good Agent includes built-in context providers:

- `{{now}}` - Current datetime
- `{{today}}` - Current date at midnight

```python
agent.append("Today's date: {{today}}, current time: {{now}}")
```

### Agent Context Management

Agents have a context dictionary that can be set at initialization or modified later:

```python
# Set context at initialization
async with Agent("Assistant", context={"env": "production", "version": "1.0"}) as agent:
    agent.append("Running in {{env}} environment, version {{version}}")

    # Access context
    print(agent.context.as_dict())  # {"env": "production", "version": "1.0"}

    # Context values override provider values
    agent.append("Time: {{now}}")  # Uses built-in provider
```

### Template Inheritance and Includes

Templates support Jinja2's inheritance and include features:

{% raw %}
```python
# Register named templates
agent.template_manager.add_template(
    "greeting",
    "Hello {{name}}, welcome to {{service}}!"
)

# Use in messages
rendered = agent.template_manager.render(
    "greeting",
    context={"name": "Alice", "service": "Good Agent"}
)
agent.append(rendered)
```
{% endraw %}

### Custom Jinja2 Filters

Good Agent includes custom Jinja2 filters for advanced formatting:

```python
# Using built-in section filter for structured content
agent.append("""
{% section "instructions" type="list" %}
Step 1: Connect to database
Step 2: Run query
Step 3: Process results
{% end section %}
""")
```

### Line Statements and Comments

Templates support line-statement syntax with `!#` prefix and comments with `!##`:

```python
agent.append("""
!# set title = "Analysis Report"
!## This is a comment and won't render
<h1>{{ title }}</h1>
!# section "content"
Report body here
!# end section
""")
```

### Template Validation

Access undefined variables to detect templating errors:

```python
# This will warn about undefined variables in strict mode
agent.append("Test {{undefined_var}}")

# Extract variables from a template
variables = agent.template_manager.extract_template_variables(
    "Hello {{name}}, your score is {{score}}"
)
print(variables)  # ['name', 'score']
```

### Context Priority

Context values are resolved in this priority order (highest to lowest):

1. Message-level `context` parameter
2. Agent context (`agent.context`)
3. Instance context providers
4. Global context providers

```python
from good_agent.agent.context import ContextManager

@ContextManager.context_providers("global_var")
def global_value():
    return "global"

async with Agent("Assistant") as agent:
    # Register instance context provider
    @agent.context.context_provider("instance_var")
    def instance_value():
        return "instance"

    # Use instance context provider (no overrides)
    agent.append("Instance value: {{instance_var}}")
    # Renders as: "Instance value: instance"

    # Use global context provider (no overrides)
    agent.append("Global value: {{global_var}}")
    # Renders as: "Global value: global"

    # Agent context overrides instance/global providers
    agent.context["instance_var"] = "agent-level"
    agent.append("Agent context: {{instance_var}}")
    # Renders as: "Agent context: agent-level"

    # Message context takes highest priority
    agent.append("Message context: {{instance_var}}", context={"instance_var": "message-level"})
    # Renders as: "Message context: message-level"
```

### File-Based Templates

Templates can be loaded from files in a `prompts/` directory:

```python
# prompts/system/assistant.txt contains:
# "You are a helpful assistant specialized in {{domain}}"

async with Agent() as agent:
    # Load and render file template
    await agent.template_manager.preload_templates(["system/assistant"])

    agent.system.set(
        agent.template_manager.render(
            "system/assistant",
            context={"domain": "Python programming"}
        )
    )
```

### Dependency Injection in Context Providers

Context providers support dependency injection for agent and message access:

```python
from good_agent import Agent
from good_agent.messages import Message

async with Agent("Assistant") as agent:
    @agent.context.context_provider("last_user_message")
    def get_last_user_msg(agent: Agent, message: Message):
        # Access agent and current message
        if agent.user:
            return agent.user[-1].content
        return "No user messages yet"

    agent.append("User")
    agent.append("Last user said: {{last_user_message}}")
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

### Interactive Execution & Messages

Messages are emitted during interactive execution:

```python
agent.append("Complex task")
async for message in agent.execute():
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

### Templating

- **Use context providers** for dynamic values that change per request
- **Set agent context** at initialization for values shared across messages
- **Template validation** to catch undefined variables early
- **File-based templates** for reusable prompts and system messages

### Content Management

- **Render appropriately** for the target audience (DISPLAY vs LLM)
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

## Message Persistence & Storage

### Database Integration

Store and retrieve message history from databases:

```python
import asyncpg
from typing import List
import json

class MessagePersistence:
    """PostgreSQL-based message persistence."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    async def save_messages(self, agent_id: str, messages: List[Message]) -> None:
        """Save message history to database."""
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Create table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    metadata JSONB,
                    sequence_order INTEGER NOT NULL
                )
            """)
            
            # Insert messages
            for i, msg in enumerate(messages):
                await conn.execute("""
                    INSERT INTO agent_messages 
                    (id, agent_id, role, content, timestamp, metadata, sequence_order)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata
                """, 
                str(msg.id), 
                agent_id,
                msg.role,
                msg.content,
                msg.timestamp,
                json.dumps(msg.model_dump(exclude={"id", "role", "content", "timestamp"})),
                i
                )
        finally:
            await conn.close()
    
    async def load_messages(self, agent_id: str) -> List[Message]:
        """Load message history from database."""
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            rows = await conn.fetch("""
                SELECT id, role, content, timestamp, metadata
                FROM agent_messages 
                WHERE agent_id = $1 
                ORDER BY sequence_order
            """, agent_id)
            
            messages = []
            for row in rows:
                metadata = json.loads(row['metadata'])
                
                # Reconstruct message based on role
                if row['role'] == 'user':
                    msg = UserMessage(content=row['content'], **metadata)
                elif row['role'] == 'assistant':
                    msg = AssistantMessage(content=row['content'], **metadata)
                elif row['role'] == 'system':
                    msg = SystemMessage(content=row['content'], **metadata)
                elif row['role'] == 'tool':
                    msg = ToolMessage(
                        content=row['content'],
                        tool_call_id=metadata.get('tool_call_id'),
                        tool_name=metadata.get('tool_name'),
                        **{k: v for k, v in metadata.items() 
                           if k not in ['tool_call_id', 'tool_name']}
                    )
                
                # Restore original ID and timestamp
                msg.id = ULID.from_str(row['id'])
                msg.timestamp = row['timestamp']
                messages.append(msg)
            
            return messages
        finally:
            await conn.close()

# Usage with agents
async def persistent_agent_session():
    """Example of agent with persistent message history."""
    persistence = MessagePersistence("postgresql://user:pass@localhost/agents")
    agent_id = "user_123_session"
    
    # Load existing history
    try:
        historical_messages = await persistence.load_messages(agent_id)
        agent = Agent("Assistant")
        agent.messages.extend(historical_messages)
        print(f"Loaded {len(historical_messages)} historical messages")
    except:
        # Start fresh if no history exists
        agent = Agent("Assistant")
    
    # Continue conversation
    await agent.initialize()
    response = await agent.call("Continue our previous conversation")
    
    # Save updated history
    await persistence.save_messages(agent_id, agent.messages)
```

### File-Based Persistence

Simple file-based message storage:

```python
import json
from pathlib import Path
from datetime import datetime

class FileMessageStore:
    """File-based message persistence."""
    
    def __init__(self, base_path: str = "./message_store"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
    
    def _get_session_file(self, session_id: str) -> Path:
        """Get file path for a session."""
        return self.base_path / f"{session_id}.json"
    
    def save_session(self, session_id: str, messages: List[Message]) -> None:
        """Save message session to file."""
        session_data = {
            "session_id": session_id,
            "saved_at": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.model_dump(exclude={"id", "role", "content", "timestamp"})
                }
                for msg in messages
            ]
        }
        
        session_file = self._get_session_file(session_id)
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    def load_session(self, session_id: str) -> List[Message]:
        """Load message session from file."""
        session_file = self._get_session_file(session_id)
        
        if not session_file.exists():
            return []
        
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        messages = []
        for msg_data in session_data["messages"]:
            # Reconstruct message with original ID and timestamp
            if msg_data["role"] == "user":
                msg = UserMessage(content=msg_data["content"], **msg_data["metadata"])
            elif msg_data["role"] == "assistant":
                msg = AssistantMessage(content=msg_data["content"], **msg_data["metadata"])
            elif msg_data["role"] == "system":
                msg = SystemMessage(content=msg_data["content"], **msg_data["metadata"])
            elif msg_data["role"] == "tool":
                metadata = msg_data["metadata"]
                msg = ToolMessage(
                    content=msg_data["content"],
                    tool_call_id=metadata.get("tool_call_id"),
                    tool_name=metadata.get("tool_name"),
                    **{k: v for k, v in metadata.items() 
                       if k not in ["tool_call_id", "tool_name"]}
                )
            
            msg.id = ULID.from_str(msg_data["id"])
            msg.timestamp = datetime.fromisoformat(msg_data["timestamp"])
            messages.append(msg)
        
        return messages
    
    def list_sessions(self) -> List[str]:
        """List all available session IDs."""
        return [f.stem for f in self.base_path.glob("*.json")]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session file."""
        session_file = self._get_session_file(session_id)
        if session_file.exists():
            session_file.unlink()
            return True
        return False

# Usage
store = FileMessageStore()

# Save session
await agent.call("Hello!")
store.save_session("user_session_1", agent.messages)

# Load session later
messages = store.load_session("user_session_1")
new_agent = Agent("Assistant")
new_agent.messages.extend(messages)
```

## Message Analytics & Insights

### Conversation Analysis

Analyze message patterns and conversation health:

```python
from collections import Counter
from typing import Dict, Any
import matplotlib.pyplot as plt

class ConversationAnalyzer:
    """Analyze conversation patterns and metrics."""
    
    def __init__(self, messages: List[Message]):
        self.messages = messages
    
    def basic_stats(self) -> Dict[str, Any]:
        """Get basic conversation statistics."""
        role_counts = Counter(msg.role for msg in self.messages)
        
        # Calculate average message length by role
        role_lengths = {}
        for role in role_counts:
            role_messages = [msg for msg in self.messages if msg.role == role]
            avg_length = sum(len(msg.content) for msg in role_messages) / len(role_messages)
            role_lengths[role] = avg_length
        
        # Time span analysis
        if self.messages:
            start_time = min(msg.timestamp for msg in self.messages)
            end_time = max(msg.timestamp for msg in self.messages)
            duration = end_time - start_time
        else:
            duration = None
        
        return {
            "total_messages": len(self.messages),
            "by_role": dict(role_counts),
            "average_length_by_role": role_lengths,
            "conversation_duration": duration,
            "messages_per_minute": len(self.messages) / (duration.total_seconds() / 60) if duration else 0
        }
    
    def tool_usage_analysis(self) -> Dict[str, Any]:
        """Analyze tool usage patterns."""
        # Count tool calls
        tool_calls = []
        for msg in self.messages:
            if isinstance(msg, AssistantMessage) and msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
        
        if not tool_calls:
            return {"tool_calls": 0, "unique_tools": 0, "most_used_tools": []}
        
        tool_names = [call.function.name for call in tool_calls]
        tool_counts = Counter(tool_names)
        
        # Tool success rate analysis
        tool_results = [msg for msg in self.messages if isinstance(msg, ToolMessage)]
        success_by_tool = {}
        
        for tool_name in tool_counts:
            tool_results_for_name = [msg for msg in tool_results if msg.tool_name == tool_name]
            if tool_results_for_name:
                # Assuming successful results don't contain "error" in content
                successes = sum(1 for msg in tool_results_for_name 
                               if "error" not in msg.content.lower())
                success_rate = successes / len(tool_results_for_name)
                success_by_tool[tool_name] = success_rate
        
        return {
            "tool_calls": len(tool_calls),
            "unique_tools": len(tool_counts),
            "most_used_tools": tool_counts.most_common(5),
            "tool_success_rates": success_by_tool
        }
    
    def conversation_flow_analysis(self) -> Dict[str, Any]:
        """Analyze conversation flow patterns."""
        if len(self.messages) < 2:
            return {"patterns": [], "transitions": {}}
        
        # Analyze role transitions
        role_pairs = []
        for i in range(len(self.messages) - 1):
            current_role = self.messages[i].role
            next_role = self.messages[i + 1].role
            role_pairs.append((current_role, next_role))
        
        transition_counts = Counter(role_pairs)
        
        # Find unusual patterns
        unusual_patterns = []
        for (from_role, to_role), count in transition_counts.items():
            if from_role == to_role and from_role != "system":
                unusual_patterns.append(f"Consecutive {from_role} messages: {count} times")
        
        return {
            "role_transitions": dict(transition_counts),
            "unusual_patterns": unusual_patterns,
            "conversation_turns": sum(1 for (f, t) in role_pairs if f == "user" and t == "assistant")
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive conversation analysis report."""
        basic = self.basic_stats()
        tools = self.tool_usage_analysis()
        flow = self.conversation_flow_analysis()
        
        report = f"""
# Conversation Analysis Report

## Basic Statistics
- Total Messages: {basic['total_messages']}
- Duration: {basic['conversation_duration']}
- Rate: {basic['messages_per_minute']:.1f} messages/minute

## Messages by Role
{chr(10).join(f"- {role}: {count}" for role, count in basic['by_role'].items())}

## Tool Usage
- Total tool calls: {tools['tool_calls']}
- Unique tools used: {tools['unique_tools']}
- Most used tools: {', '.join(f"{tool}({count})" for tool, count in tools['most_used_tools'])}

## Conversation Flow
- Conversation turns: {flow['conversation_turns']}
- Unusual patterns: {len(flow['unusual_patterns'])}
{chr(10).join(f"  - {pattern}" for pattern in flow['unusual_patterns'])}
        """
        
        return report.strip()

# Usage
analyzer = ConversationAnalyzer(agent.messages)
report = analyzer.generate_report()
print(report)

# Export analysis data
analysis_data = {
    "basic_stats": analyzer.basic_stats(),
    "tool_usage": analyzer.tool_usage_analysis(),
    "conversation_flow": analyzer.conversation_flow_analysis()
}

with open("conversation_analysis.json", "w") as f:
    json.dump(analysis_data, f, indent=2, default=str)
```

### Message Quality Assessment

Evaluate message quality and conversation health:

```python
import re
from typing import List, Tuple

class MessageQualityAssessor:
    """Assess message quality and conversation health."""
    
    def __init__(self, messages: List[Message]):
        self.messages = messages
    
    def assess_message_quality(self, message: Message) -> Dict[str, Any]:
        """Assess quality of individual message."""
        content = message.content
        
        # Length assessment
        length_score = min(len(content) / 100, 1.0)  # Normalize to 0-1
        
        # Complexity assessment (simple heuristic)
        sentences = len(re.split(r'[.!?]+', content))
        words = len(content.split())
        avg_word_length = sum(len(word) for word in content.split()) / max(words, 1)
        
        complexity_score = min((sentences * avg_word_length) / 50, 1.0)
        
        # Content quality indicators
        has_questions = bool(re.search(r'\?', content))
        has_specificity = bool(re.search(r'\b(specific|exactly|precisely|detail)\b', content.lower()))
        has_politeness = bool(re.search(r'\b(please|thank|sorry|appreciate)\b', content.lower()))
        
        # Role-specific assessment
        role_specific_score = self._assess_role_specific_quality(message)
        
        return {
            "length_score": length_score,
            "complexity_score": complexity_score,
            "has_questions": has_questions,
            "has_specificity": has_specificity,
            "has_politeness": has_politeness,
            "role_specific_score": role_specific_score,
            "overall_quality": (length_score + complexity_score + role_specific_score) / 3
        }
    
    def _assess_role_specific_quality(self, message: Message) -> float:
        """Assess quality based on message role."""
        content = message.content.lower()
        
        if message.role == "user":
            # Good user messages are clear and specific
            clarity_indicators = ["what", "how", "why", "when", "where", "which"]
            clarity_score = sum(1 for indicator in clarity_indicators if indicator in content) / len(clarity_indicators)
            return min(clarity_score * 2, 1.0)
        
        elif message.role == "assistant":
            # Good assistant messages are helpful and structured
            helpfulness_indicators = ["here's", "i can", "let me", "to help", "consider", "option"]
            helpfulness_score = sum(1 for indicator in helpfulness_indicators if indicator in content) / len(helpfulness_indicators)
            return min(helpfulness_score * 2, 1.0)
        
        elif message.role == "system":
            # Good system messages are clear and directive
            directive_indicators = ["you are", "your role", "respond", "format", "style"]
            directive_score = sum(1 for indicator in directive_indicators if indicator in content) / len(directive_indicators)
            return min(directive_score * 2, 1.0)
        
        return 0.5  # Default for other roles
    
    def assess_conversation_health(self) -> Dict[str, Any]:
        """Assess overall conversation health."""
        if not self.messages:
            return {"health_score": 0, "issues": ["No messages"]}
        
        issues = []
        health_indicators = []
        
        # Check for balanced participation
        role_counts = Counter(msg.role for msg in self.messages)
        user_count = role_counts.get("user", 0)
        assistant_count = role_counts.get("assistant", 0)
        
        if user_count == 0:
            issues.append("No user messages")
        elif assistant_count == 0:
            issues.append("No assistant responses")
        else:
            balance_ratio = min(user_count, assistant_count) / max(user_count, assistant_count)
            health_indicators.append(balance_ratio)
        
        # Check for appropriate conversation flow
        consecutive_same_role = 0
        max_consecutive = 0
        prev_role = None
        
        for msg in self.messages:
            if msg.role == prev_role and msg.role != "system":
                consecutive_same_role += 1
                max_consecutive = max(max_consecutive, consecutive_same_role)
            else:
                consecutive_same_role = 1
            prev_role = msg.role
        
        if max_consecutive > 3:
            issues.append(f"Too many consecutive {prev_role} messages ({max_consecutive})")
        else:
            health_indicators.append(1.0 - (max_consecutive - 1) / 10)
        
        # Check average message quality
        quality_scores = [
            self.assess_message_quality(msg)["overall_quality"] 
            for msg in self.messages
        ]
        avg_quality = sum(quality_scores) / len(quality_scores)
        health_indicators.append(avg_quality)
        
        # Check for tool usage appropriateness
        tool_calls = sum(1 for msg in self.messages if isinstance(msg, AssistantMessage) and msg.tool_calls)
        tool_results = sum(1 for msg in self.messages if isinstance(msg, ToolMessage))
        
        if tool_calls > tool_results:
            issues.append(f"Unmatched tool calls: {tool_calls - tool_results}")
        elif tool_calls > 0:
            tool_completion_rate = tool_results / tool_calls
            health_indicators.append(tool_completion_rate)
        
        # Calculate overall health score
        health_score = sum(health_indicators) / len(health_indicators) if health_indicators else 0
        
        return {
            "health_score": health_score,
            "issues": issues,
            "average_message_quality": avg_quality,
            "balance_ratio": balance_ratio if 'balance_ratio' in locals() else 0,
            "tool_completion_rate": tool_completion_rate if 'tool_completion_rate' in locals() else 1.0
        }
    
    def generate_quality_report(self) -> str:
        """Generate comprehensive quality assessment report."""
        health = self.assess_conversation_health()
        
        # Assess individual messages
        message_assessments = [
            (i, self.assess_message_quality(msg))
            for i, msg in enumerate(self.messages)
        ]
        
        # Find best and worst messages
        best_msg = max(message_assessments, key=lambda x: x[1]["overall_quality"]) if message_assessments else None
        worst_msg = min(message_assessments, key=lambda x: x[1]["overall_quality"]) if message_assessments else None
        
        report = f"""
# Message Quality Assessment Report

## Overall Health Score: {health['health_score']:.2f}/1.00

## Health Indicators
- Average Message Quality: {health['average_message_quality']:.2f}
- Balance Ratio: {health['balance_ratio']:.2f}
- Tool Completion Rate: {health['tool_completion_rate']:.2f}

## Issues Identified
{chr(10).join(f"- {issue}" for issue in health['issues']) if health['issues'] else "- No issues found"}

## Message Quality Highlights
- Best Message (#{best_msg[0]}): {best_msg[1]['overall_quality']:.2f} quality score
- Worst Message (#{worst_msg[0]}): {worst_msg[1]['overall_quality']:.2f} quality score

## Recommendations
{self._generate_recommendations(health, message_assessments)}
        """
        
        return report.strip()
    
    def _generate_recommendations(self, health: Dict, assessments: List) -> str:
        """Generate improvement recommendations."""
        recommendations = []
        
        if health['health_score'] < 0.6:
            recommendations.append("- Consider improving overall conversation structure")
        
        if health['average_message_quality'] < 0.5:
            recommendations.append("- Focus on more detailed and specific messages")
        
        if health['balance_ratio'] < 0.5:
            recommendations.append("- Encourage more balanced participation between user and assistant")
        
        if health['tool_completion_rate'] < 0.8:
            recommendations.append("- Review tool execution reliability")
        
        # Check for messages with very low quality
        low_quality_messages = [
            i for i, assessment in assessments 
            if assessment['overall_quality'] < 0.3
        ]
        
        if low_quality_messages:
            recommendations.append(f"- Review messages at positions: {', '.join(map(str, low_quality_messages))}")
        
        return '\n'.join(recommendations) if recommendations else "- Conversation quality looks good!"

# Usage
assessor = MessageQualityAssessor(agent.messages)
quality_report = assessor.generate_quality_report()
print(quality_report)
```

## Message Security & Privacy

### Content Sanitization

Remove sensitive information from messages:

```python
import re
from typing import Pattern, List

class MessageSanitizer:
    """Sanitize messages to remove sensitive information."""
    
    def __init__(self):
        # Common patterns for sensitive data
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'api_key': re.compile(r'\b[A-Za-z0-9]{32,}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'url_with_token': re.compile(r'https?://[^\s]*[?&](?:token|key|secret)=[^\s&]*'),
        }
    
    def add_pattern(self, name: str, pattern: Pattern[str]) -> None:
        """Add custom sanitization pattern."""
        self.patterns[name] = pattern
    
    def sanitize_content(self, content: str, replacement: str = "[REDACTED]") -> Tuple[str, List[str]]:
        """Sanitize content and return cleaned version with detected types."""
        detected_types = []
        sanitized = content
        
        for pattern_name, pattern in self.patterns.items():
            matches = pattern.findall(content)
            if matches:
                detected_types.append(pattern_name)
                sanitized = pattern.sub(replacement, sanitized)
        
        return sanitized, detected_types
    
    def sanitize_message(self, message: Message) -> Tuple[Message, List[str]]:
        """Sanitize a message and return cleaned version."""
        sanitized_content, detected_types = self.sanitize_content(message.content)
        
        # Create new message with sanitized content
        if isinstance(message, UserMessage):
            sanitized_msg = UserMessage(sanitized_content)
        elif isinstance(message, AssistantMessage):
            sanitized_msg = AssistantMessage(
                sanitized_content,
                tool_calls=message.tool_calls,
                reasoning=message.reasoning,
                citations=message.citations
            )
        elif isinstance(message, SystemMessage):
            sanitized_msg = SystemMessage(sanitized_content)
        elif isinstance(message, ToolMessage):
            sanitized_msg = ToolMessage(
                sanitized_content,
                tool_call_id=message.tool_call_id,
                tool_name=message.tool_name
            )
        else:
            sanitized_msg = message  # Fallback
        
        # Preserve original metadata
        sanitized_msg.id = message.id
        sanitized_msg.timestamp = message.timestamp
        
        return sanitized_msg, detected_types
    
    def sanitize_message_list(self, messages: List[Message]) -> Tuple[List[Message], Dict[str, int]]:
        """Sanitize a list of messages."""
        sanitized_messages = []
        detection_summary = {}
        
        for message in messages:
            sanitized_msg, detected_types = self.sanitize_message(message)
            sanitized_messages.append(sanitized_msg)
            
            # Update detection summary
            for detected_type in detected_types:
                detection_summary[detected_type] = detection_summary.get(detected_type, 0) + 1
        
        return sanitized_messages, detection_summary

# Privacy-aware agent wrapper
class PrivacyAwareAgent:
    """Agent wrapper that automatically sanitizes messages."""
    
    def __init__(self, agent: Agent, sanitize_on_save: bool = True):
        self.agent = agent
        self.sanitizer = MessageSanitizer()
        self.sanitize_on_save = sanitize_on_save
        self._original_messages = []  # Store originals if needed
    
    def get_sanitized_history(self) -> List[Message]:
        """Get sanitized version of message history."""
        sanitized_messages, detection_summary = self.sanitizer.sanitize_message_list(self.agent.messages)
        
        if detection_summary:
            print(f"Privacy Notice: Sanitized {sum(detection_summary.values())} sensitive items")
            for item_type, count in detection_summary.items():
                print(f"  - {item_type}: {count} instances")
        
        return sanitized_messages
    
    def export_safe_history(self, file_path: str) -> None:
        """Export sanitized message history to file."""
        sanitized_messages = self.get_sanitized_history()
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "message_count": len(sanitized_messages),
            "privacy_notice": "This export has been sanitized to remove sensitive information",
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in sanitized_messages
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)

# Usage
sanitizer = MessageSanitizer()

# Add custom pattern for internal IDs
sanitizer.add_pattern('internal_id', re.compile(r'\bID-\d{8,}\b'))

# Sanitize message
original_msg = UserMessage("My email is user@example.com and phone is 555-123-4567")
sanitized_msg, detected = sanitizer.sanitize_message(original_msg)

print(f"Original: {original_msg.content}")
print(f"Sanitized: {sanitized_msg.content}")
print(f"Detected: {detected}")

# Use with agent
privacy_agent = PrivacyAwareAgent(agent)
safe_history = privacy_agent.get_sanitized_history()
privacy_agent.export_safe_history("safe_conversation.json")
```

## Next Steps

- **[Tools](tools.md)** - Add function calling capabilities to your agents
- **[Events](events.md)** - React to message lifecycle events  
- **[Structured Output](../features/structured-output.md)** - Extract typed data from assistant messages
- **[Interactive Execution](../features/interactive-execution.md)** - Process messages in real-time during execution
