# Tools

Good Agent provides a powerful tool system that enables agents to interact with external services, APIs, and custom functions. Tools use standard Python functions with dependency injection, type hints, and automatic schema generation. This page covers tool definition, registration, execution, and integration patterns.

## Tool Basics

### Defining Tools

Create tools using the `@tool` decorator on any Python function:

```python
from good_agent import tool

@tool
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic math operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unknown operation: {operation}")

@tool
def get_current_time() -> str:
    """Get the current time in ISO format."""
    from datetime import datetime
    return datetime.now().isoformat()
```

**Key Features:**

- **Async support**: Tools can be `async` or sync functions
- **Type hints**: Parameter and return types are automatically converted to JSON schema
- **Docstrings**: Function docstrings become tool descriptions
- **Validation**: Input parameters are validated using Pydantic

### Tool Registration

Tools are registered automatically when used with agents:

```python
async with Agent("Assistant", tools=[calculate, get_current_time]) as agent:
    # Tools are automatically registered and available to the LLM
    response = await agent.call("What is 5 + 3 and what time is it?")
```

**Manual Registration:**

```python
from good_agent.tools import ToolManager

# Direct registration
manager = ToolManager()
await manager.register_tool(calculate, name="math_calc")

# Access registered tool
tool_instance = manager["math_calc"]
```

### Tool Metadata

Customize tool behavior with the decorator:

```python
@tool(
    name="search_docs",                    # Override function name
    description="Search project docs",     # Override docstring
    register=True,                         # Auto-register globally
    context_variables=["project_path"]     # Required context variables
)
async def search_documentation(query: str, limit: int = 5) -> list[str]:
    """Search through project documentation."""
    return [f"Result {i}: {query}" for i in range(limit)]
```

## Dependency Injection

Good Agent uses FastDepends for powerful dependency injection in tools:

### Basic Dependencies

```python
from fast_depends import Depends
from good_agent import tool

# Dependency provider
def get_database():
    return {"connection": "postgresql://localhost/db"}

def get_api_client():
    return {"api_key": "secret", "base_url": "https://api.example.com"}

@tool
async def query_database(
    query: str,
    limit: int = 10,
    db: dict = Depends(get_database),      # Injected dependency
    api: dict = Depends(get_api_client),   # Multiple dependencies
) -> list[dict]:
    """Query the database with API enrichment."""
    # Use db and api connections
    results = [{"id": i, "query": query} for i in range(limit)]
    return results
```

### Agent Context Dependencies

Access agent state and context within tools:

```python
from good_agent.tools import ToolContext

@tool
async def agent_aware_tool(
    query: str,
    context: ToolContext = Depends()  # Injected agent context
) -> str:
    """Tool that can access agent state."""
    agent = context.agent
    tool_call = context.tool_call

    # Access agent properties
    agent_name = agent.name
    message_count = len(agent.messages)
    last_user_message = agent.user[-1].content if agent.user else "No messages"

    return f"Agent {agent_name} ({message_count} messages): {query}"
```

### Real-World Example

```python
--8<-- "tests/spec/test_public_contract.py:280:320"
```

## Tool Execution

### Automatic Execution

Tools are called automatically by the LLM during conversation:

```python
async with Agent("You are a helpful calculator", tools=[calculate]) as agent:
    # LLM will automatically call the calculate tool
    response = await agent.call("What is 15 * 7?")
    print(response.content)  # "105" or similar
```

### Direct Invocation

Invoke tools programmatically for testing or custom workflows:

```python
async with Agent("Assistant", tools=[calculate]) as agent:
    # Direct tool invocation
    result = await agent.invoke(
        calculate,
        operation="add",
        a=10,
        b=5
    )

    print(f"Success: {result.success}")      # True
    print(f"Response: {result.response}")    # 15.0
    print(f"Tool name: {result.tool_name}")  # "calculate"
    print(f"Parameters: {result.parameters}") # {"operation": "add", "a": 10, "b": 5}
```

**Advanced Invocation Options:**

```python
# With custom tool call ID
result = await agent.invoke(
    calculate,
    tool_call_id="custom_123",
    operation="multiply",
    a=6,
    b=7
)

# Skip creating assistant message (for processing existing tool calls)
result = await agent.invoke(
    calculate,
    skip_assistant_message=True,
    operation="add",
    a=1,
    b=2
)
```

### Error Handling

Tools should handle errors gracefully:

```python
@tool
async def divide_numbers(a: float, b: float) -> float:
    """Divide two numbers safely."""
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b

# Usage with error handling
async with Agent("Calculator", tools=[divide_numbers]) as agent:
    result = await agent.invoke(divide_numbers, a=10, b=0)

    if not result.success:
        print(f"Error: {result.error}")
        print(f"Traceback: {result.traceback}")
```

## Component-Based Tools

Define tools as methods in AgentComponent classes for better organization:

### Basic Component Tools

```python
from good_agent import AgentComponent, tool

class MathComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.calculation_history = []

    @tool
    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        self.calculation_history.append(f"{a} + {b} = {result}")
        return result

    @tool
    def get_history(self) -> list[str]:
        """Get calculation history."""
        return self.calculation_history.copy()

# Usage
math_component = MathComponent()
async with Agent("Calculator", extensions=[math_component]) as agent:
    response = await agent.call("Add 5 and 3, then show me the history")
```

### Stateful Components

Components maintain state across tool calls:

```python
class TaskManager(AgentComponent):
    def __init__(self):
        super().__init__()
        self.tasks = []
        self.completed = []

    @tool
    def create_task(self, task: str) -> str:
        """Create a new task."""
        self.tasks.append(task)
        return f"Created task: {task}"

    @tool
    def complete_task(self, task: str) -> str:
        """Mark a task as completed."""
        if task in self.tasks:
            self.tasks.remove(task)
            self.completed.append(task)
            return f"Completed task: {task}"
        return f"Task not found: {task}"

    @tool
    def list_tasks(self) -> dict[str, list[str]]:
        """List all tasks."""
        return {"pending": self.tasks, "completed": self.completed}

# Component tools integrate with agent state
task_mgr = TaskManager()
async with Agent("Task assistant", extensions=[task_mgr]) as agent:
    agent.append("Create a task to 'Review documentation' and then complete it")
    await agent.call()
```

## Model Context Protocol (MCP)

Good Agent supports MCP for integrating external tool servers:

### Loading MCP Servers

```python
async with Agent(
    "Assistant with external tools",
    mcp_servers=[
        # Server names (must be in PATH)
        "filesystem",
        "brave-search",

        # Full server configurations
        {"name": "web", "command": "npx @modelcontextprotocol/server-web"},
        {"name": "git", "uri": "stdio://git-mcp-server"},
    ]
) as agent:
    # MCP tools are automatically available
    await agent.call("List files in the current directory")
    await agent.call("Search the web for Python news")
```

### MCP Server Configuration

MCP servers can be configured with various options:

```python
mcp_servers = [
    # Simple string format
    "filesystem-server",

    # Dictionary with command
    {
        "name": "custom-server",
        "command": "python /path/to/server.py",
        "args": ["--config", "production"],
        "env": {"API_KEY": "secret"}
    },

    # URI-based connection
    {
        "name": "remote-server",
        "uri": "tcp://remote.example.com:8080"
    }
]

async with Agent("MCP-enabled assistant", mcp_servers=mcp_servers) as agent:
    # All MCP tools are available alongside native tools
    pass
```

### MCP Tool Lifecycle

MCP servers are managed automatically:

```python
async with Agent("Assistant", mcp_servers=["filesystem"]) as agent:
    # Servers connect during agent initialization

    # Use MCP tools normally
    await agent.call("Create a new file called 'notes.txt'")

    # Servers disconnect automatically on context exit
```

## Advanced Tool Patterns

### Conditional Tool Registration

Control when tools are available:

```python
@tool
def production_tool() -> str:
    """Tool only available in production."""
    return "Production data"

@tool
def debug_tool() -> str:
    """Tool only available in debug mode."""
    return "Debug information"

# Conditional registration
tools = [production_tool] if is_production else [debug_tool, production_tool]

async with Agent("Context-aware assistant", tools=tools) as agent:
    pass
```

### Tool Filtering

Filter available tools by name patterns:

```python
async with Agent(
    "Restricted assistant",
    tools=[calculate, get_time, debug_tool, admin_tool],
    include_tool_filters=["calculate*", "get_*"],  # Only matching tools
    exclude_tool_filters=["debug*", "admin*"],    # Exclude patterns
) as agent:
    # Only 'calculate' and 'get_time' are available
    pass
```

### Dynamic Tool Registration

Add tools during agent execution:

```python
async with Agent("Extensible assistant") as agent:
    # Start with basic tools
    await agent.tools.register_tool(calculate, name="math")

    # Add more tools based on conversation
    if "search" in agent.user[-1].content.lower():
        await agent.tools.register_tool(search_web, name="web_search")

    # Remove tools
    if "basic_mode" in agent.user[-1].content:
        del agent.tools["web_search"]
```

### Tool Chaining

Tools can call other tools:

```python
@tool
async def search_and_summarize(
    query: str,
    context: ToolContext = Depends()
) -> str:
    """Search for information and summarize results."""
    agent = context.agent

    # Call search tool
    search_result = await agent.invoke("search_web", query=query)

    if search_result.success:
        # Process results and call summarization
        summary_result = await agent.invoke(
            "summarize_text",
            text=search_result.response
        )
        return summary_result.response if summary_result.success else "Failed to summarize"

    return "Search failed"
```

## Tool Testing

### Unit Testing Tools

Test tools independently:

```python
import pytest
from good_agent.tools import ToolManager

@pytest.mark.asyncio
async def test_calculate_tool():
    manager = ToolManager()
    await manager.register_tool(calculate)

    # Test direct invocation
    result = await manager["calculate"](operation="add", a=5, b=3)

    assert result.success is True
    assert result.response == 8.0
    assert result.tool_name == "calculate"

@pytest.mark.asyncio
async def test_error_handling():
    manager = ToolManager()
    await manager.register_tool(divide_numbers)

    # Test error case
    result = await manager["divide_numbers"](a=10, b=0)

    assert result.success is False
    assert "Division by zero" in result.error
    assert result.traceback is not None
```

### Integration Testing

Test tools within agent context:

```python
@pytest.mark.asyncio
async def test_tool_in_agent():
    async with Agent("Test agent", tools=[calculate]) as agent:
        # Test agent can use tool
        response = await agent.call("Calculate 7 times 8")

        # Verify tool was called
        tool_messages = [msg for msg in agent.tool if msg.tool_name == "calculate"]
        assert len(tool_messages) >= 1

        # Verify response contains result
        assert "56" in response.content
```

### Mocking Tools

Mock tools for testing:

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_with_mocked_tool():
    # Create mock tool
    mock_search = AsyncMock(return_value="Mocked search results")

    async with Agent("Test agent", tools=[mock_search]) as agent:
        result = await agent.invoke(mock_search, query="test")

        assert result.success is True
        assert result.response == "Mocked search results"
        mock_search.assert_called_once_with(query="test")
```

## Tool Schema & Validation

### Automatic Schema Generation

Good Agent automatically generates JSON schemas from Python type hints:

```python
from typing import Literal, Optional
from pydantic import Field

@tool
async def advanced_search(
    query: str,
    limit: int = Field(default=10, ge=1, le=100, description="Number of results"),
    sort_by: Literal["relevance", "date", "title"] = "relevance",
    include_content: bool = True,
    categories: Optional[list[str]] = None
) -> dict:
    """Advanced search with validation and schema generation."""
    return {
        "query": query,
        "results": [f"Result {i}" for i in range(min(limit, 5))],
        "sort_by": sort_by,
        "categories": categories or []
    }

# Schema is automatically available to LLM
async with Agent("Search assistant", tools=[advanced_search]) as agent:
    # LLM understands parameter constraints and types
    await agent.call("Search for 'python' with at most 5 results sorted by date")
```

### Custom Validation

Add custom validation logic:

```python
from pydantic import validator

@tool
async def create_user(
    name: str,
    email: str,
    age: int
) -> dict:
    """Create a user with validation."""
    # Custom validation
    if age < 13:
        raise ValueError("Users must be at least 13 years old")

    if "@" not in email:
        raise ValueError("Invalid email format")

    return {"name": name, "email": email, "age": age, "id": "user_123"}
```

### Complex Type Support

Tools support complex Pydantic models:

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TaskModel(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: Optional[datetime] = None
    tags: list[str] = []

@tool
async def create_complex_task(task: TaskModel) -> dict:
    """Create a task using a complex model."""
    return {
        "created": True,
        "task_id": "task_456",
        "task": task.model_dump()
    }

# LLM receives full schema for TaskModel
async with Agent("Task manager", tools=[create_complex_task]) as agent:
    await agent.call("""
        Create a high-priority task titled 'Review documentation'
        due tomorrow with tags 'urgent' and 'docs'
    """)
```

## Agent as a Tool

You can convert any Agent into a tool that can be used by another Agent. This enables powerful multi-agent orchestration patterns where agents delegate complex tasks to specialized sub-agents.

### Creating an Agent Tool

Use the `as_tool()` method to convert an agent into a tool:

```python
# 1. Create specialized agents
researcher = Agent(
    "You are a research specialist. Search for information and summarize findings.",
    name="researcher",
    tools=[web_search]
)

writer = Agent(
    "You are a technical writer. Create content based on research.",
    name="writer"
)

# 2. Convert them to tools
research_tool = researcher.as_tool(
    description="Delegate research tasks to a specialist agent"
)

# 3. Use in a manager agent
manager = Agent(
    "You are a content manager. Coordinate research and writing.",
    tools=[research_tool] # The writer agent can also be used here if converted
)

async with manager:
    await manager.call("Research the history of AI agents")
```

### Multi-Turn Sessions

By default, Agent-as-a-Tool supports multi-turn conversations (`multi_turn=True`). This means the sub-agent maintains its state and conversation history across multiple calls from the parent agent.

When a sub-agent is called multiple times:
1. The first call creates a new session and returns a session ID (e.g., `<researcher session_id="1">...`)
2. Subsequent calls by the parent agent will automatically use this session ID to continue the conversation
3. State (memory, context) persists for the duration of the parent's lifecycle

```python
# Disable multi-turn for stateless, one-shot execution
stateless_tool = researcher.as_tool(multi_turn=False)
```

### How it Works

- **One-shot (`multi_turn=False`)**: Each tool call forks a fresh instance of the base agent. No state is preserved between calls.
- **Multi-turn (`multi_turn=True`)**: A session ID is generated on the first call. The tool wrapper maintains a registry of forked agent sessions. Subsequent calls with the same ID are routed to the existing session instance.

## Performance & Best Practices

### Tool Performance

- **Async tools**: Use `async` for I/O-bound operations
- **Caching**: Cache expensive computations within tool implementations
- **Timeouts**: Implement timeouts for network calls and long-running operations
- **Connection pooling**: Reuse database connections and HTTP clients

```python
import asyncio
from functools import lru_cache

# Connection pool (shared across tool calls)
HTTP_CLIENT = None

async def get_http_client():
    global HTTP_CLIENT
    if not HTTP_CLIENT:
        import aiohttp
        HTTP_CLIENT = aiohttp.ClientSession()
    return HTTP_CLIENT

@tool
async def fetch_url(url: str, timeout: float = 10.0) -> str:
    """Fetch URL with connection pooling and timeout."""
    client = await get_http_client()

    try:
        async with asyncio.timeout(timeout):
            async with client.get(url) as response:
                return await response.text()
    except asyncio.TimeoutError:
        raise ValueError(f"Timeout fetching {url}")

# Sync tool with caching
@tool
@lru_cache(maxsize=100)
def expensive_calculation(n: int) -> int:
    """Cached expensive calculation."""
    time.sleep(1)  # Simulate expensive work
    return n * n * n
```

### Dependency Management

- **Singleton dependencies**: Use singletons for shared resources
- **Lazy initialization**: Initialize expensive resources only when needed
- **Resource cleanup**: Properly close connections and clean up resources

```python
from contextlib import asynccontextmanager

class DatabaseConnection:
    _instance = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance.connect()
        return cls._instance

    async def connect(self):
        # Initialize database connection
        self.connection = "db_connection"

    async def close(self):
        # Clean up connection
        self.connection = None

async def get_db():
    return await DatabaseConnection.get_instance()

@tool
async def query_users(
    name_filter: str,
    db: DatabaseConnection = Depends(get_db)
) -> list[dict]:
    """Query users with shared DB connection."""
    # Use db.connection
    return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
```

### Tool Organization

- **Group related tools** in components or modules
- **Use consistent naming** conventions (verb_noun pattern)
- **Document dependencies** and side effects clearly
- **Separate concerns** (data access, business logic, formatting)

```python
# tools/database.py
class DatabaseTools(AgentComponent):
    @tool
    def create_user(self, user_data: dict) -> dict:
        """Create a new user."""
        pass

    @tool
    def get_user(self, user_id: str) -> dict:
        """Retrieve user by ID."""
        pass

    @tool
    def update_user(self, user_id: str, updates: dict) -> dict:
        """Update user information."""
        pass

# tools/search.py
class SearchTools(AgentComponent):
    @tool
    def search_users(self, query: str) -> list[dict]:
        """Search for users."""
        pass

    @tool
    def search_content(self, query: str) -> list[dict]:
        """Search for content."""
        pass
```

## Troubleshooting

### Common Issues

```python
# ❌ Missing type hints
@tool
def bad_tool(param):  # No type hints
    return param

# ✅ Proper type hints
@tool
def good_tool(param: str) -> str:
    return param

# ❌ Sync tool with async dependency
@tool
def sync_tool(db: AsyncDB = Depends(get_async_db)):  # Won't work
    pass

# ✅ Async tool with async dependency
@tool
async def async_tool(db: AsyncDB = Depends(get_async_db)):
    pass
```

### Tool Registration Errors

```python
# Check tool registration
async with Agent("Assistant", tools=[my_tool]) as agent:
    # List available tools
    available_tools = list(agent.tools.keys())
    print("Available tools:", available_tools)

    # Check specific tool
    if "my_tool" in agent.tools:
        tool_instance = agent.tools["my_tool"]
        print("Tool metadata:", tool_instance.metadata)
```

### Dependency Injection Issues

```python
# Debug dependency injection
from good_agent.tools import ToolContext

@tool
async def debug_tool(
    param: str,
    context: ToolContext = Depends()
) -> str:
    """Tool for debugging dependencies."""
    print(f"Agent: {context.agent}")
    print(f"Tool call: {context.tool_call}")
    return f"Debug: {param}"

# Test dependency injection
async with Agent("Debug agent", tools=[debug_tool]) as agent:
    result = await agent.invoke(debug_tool, param="test")
    print(result.response)
```

### Tool Execution Errors

```python
# Handle tool execution errors
async with Agent("Error-handling agent", tools=[risky_tool]) as agent:
    result = await agent.invoke(risky_tool, param="test")

    if not result.success:
        print(f"Tool failed: {result.error}")
        print(f"Parameters used: {result.parameters}")
        if result.traceback:
            print(f"Traceback: {result.traceback}")
```

### MCP Connection Issues

```python
# Debug MCP server connections
async with Agent(
    "MCP agent",
    mcp_servers=["filesystem"],
    debug=True  # Enable debug logging
) as agent:
    # Check MCP server status
    if hasattr(agent.tools, '_mcp_client'):
        mcp_client = agent.tools._mcp_client
        print(f"MCP servers connected: {mcp_client.connected_servers}")
```

## Next Steps

- **[Events](events.md)** - React to tool execution events and lifecycle changes
- **[Agent Modes](../features/modes.md)** - Use tools in different agent contexts
- **[Custom Components](../extensibility/components.md)** - Build reusable tool collections
- **[Advanced Tool Patterns](../extensibility/custom-tools.md)** - Complex tool architectures and patterns
