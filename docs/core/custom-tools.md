# Custom Tools

Good Agent's tool system allows you to create custom tools with parameter validation, type safety, and dependency injection. This guide covers the core patterns for building tools.

## Basic Tool Definition

Tools are Python functions decorated with `@tool`:

```python
from good_agent import Agent, tool

@tool
async def calculate(x: int, y: int, operation: str = "add") -> int:
    """Perform basic arithmetic operations.

    Args:
        x: First number
        y: Second number
        operation: Operation to perform (add, subtract, multiply, divide)

    Returns:
        Result of the operation
    """
    if operation == "add":
        return x + y
    elif operation == "subtract":
        return x - y
    elif operation == "multiply":
        return x * y
    elif operation == "divide":
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x // y
    else:
        raise ValueError(f"Unknown operation: {operation}")

# Use the tool with an agent
async with Agent("Math assistant", tools=[calculate]) as agent:
    response = await agent.call("What is 15 + 27?")
    print(response.content)
```

## Parameter Validation with Pydantic

Use Pydantic's `Field` for comprehensive parameter validation:

```python
from good_agent import tool
from pydantic import Field
from typing import Literal

@tool
async def search(
    query: str = Field(min_length=1, description="Search query"),
    category: Literal["web", "academic", "news"] = Field(default="web"),
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results (1-100)")
) -> list[dict]:
    """
    Search with validated parameters.

    Args:
        query: The search query (must not be empty)
        category: Category to search
        max_results: Maximum number of results to return

    Returns:
        List of search results
    """
    # Validation happens automatically via Pydantic
    results = []
    for i in range(min(max_results, 5)):
        results.append({
            "title": f"Result {i+1} for '{query}'",
            "url": f"https://example.com/{i}",
            "category": category
        })
    return results
```

## Structured Return Types

Use Pydantic models for structured, validated return values:

```python
from pydantic import BaseModel
from typing import Optional

class SearchResult(BaseModel):
    """Individual search result."""
    title: str
    url: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)

class SearchResponse(BaseModel):
    """Complete search response."""
    query: str
    results: list[SearchResult]
    total_found: int

@tool
async def structured_search(query: str) -> SearchResponse:
    """
    Search with structured response.

    Args:
        query: Search query

    Returns:
        Structured search results with metadata
    """
    results = [
        SearchResult(
            title=f"Result for '{query}'",
            url="https://example.com",
            snippet="Example search result snippet",
            score=0.95
        )
    ]

    return SearchResponse(
        query=query,
        results=results,
        total_found=len(results)
    )
```

## Error Handling

Tools should handle errors gracefully and provide clear error messages:

```python
@tool
async def divide_numbers(a: float, b: float) -> float:
    """
    Divide two numbers with error handling.

    Args:
        a: Numerator
        b: Denominator

    Returns:
        Result of a / b

    Raises:
        ValueError: If denominator is zero
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")

    return a / b

@tool
async def safe_divide(a: float, b: float) -> dict:
    """
    Divide with graceful error handling.

    Returns error information instead of raising exceptions.
    """
    if b == 0:
        return {
            "success": False,
            "error": "Cannot divide by zero",
            "suggestion": "Please provide a non-zero denominator"
        }

    return {
        "success": True,
        "result": a / b
    }
```

## Dependency Injection

> **⚠️ Note**: The dependency injection API is currently under construction. The patterns shown below may change in future versions.

Good Agent uses [FastDepends](https://lancetnik.github.io/FastDepends/) for dependency injection in tools.

### Basic Dependency Injection

```python
from fast_depends import Depends

# Define a dependency provider
def get_api_client():
    """Provide an API client instance."""
    return {"api_key": "secret", "base_url": "https://api.example.com"}

@tool
async def call_api(
    endpoint: str,
    client: dict = Depends(get_api_client)  # Inject dependency
) -> dict:
    """
    Call an API endpoint with injected client.

    Args:
        endpoint: API endpoint path
        client: API client (injected automatically)

    Returns:
        API response
    """
    url = f"{client['base_url']}/{endpoint}"
    # Make API call...
    return {"url": url, "status": "success"}
```

### Accessing Agent Context

To access the agent instance and other context from within a tool:

```python
from fast_depends import Depends
from good_agent.tools import ToolContext

@tool
async def context_aware_tool(
    message: str,
    context: ToolContext = Depends(ToolContext)
) -> str:
    """
    Tool that accesses agent context.

    Args:
        message: User message
        context: Tool context with agent reference (injected)

    Returns:
        Response incorporating agent state
    """
    agent = context.agent

    # Access agent properties
    message_count = len(agent.messages)

    return f"Processing '{message}' (agent has {message_count} messages)"
```

## Tool Composition

Build complex workflows by calling tools from within other tools:

```python
@tool
async def analyze_text(text: str) -> dict:
    """Analyze text and return statistics."""
    return {
        "length": len(text),
        "words": len(text.split()),
        "uppercase": sum(1 for c in text if c.isupper())
    }

@tool
async def summarize_text(text: str) -> str:
    """Summarize text."""
    # Simple truncation for demo
    return text[:100] + "..." if len(text) > 100 else text

@tool
async def process_document(
    text: str,
    context: ToolContext = Depends(ToolContext)
) -> dict:
    """
    Process document using multiple tools.

    Args:
        text: Document text
        context: Tool context

    Returns:
        Complete analysis
    """
    agent = context.agent

    # Call analysis tool
    analysis_result = await agent.tools["analyze_text"](
        _agent=agent,
        text=text
    )

    # Call summarization tool
    summary_result = await agent.tools["summarize_text"](
        _agent=agent,
        text=text
    )

    return {
        "analysis": analysis_result.response if analysis_result.success else None,
        "summary": summary_result.response if summary_result.success else None,
        "processed": True
    }
```

## Best Practices

### 1. Use Type Hints and Validation

```python
@tool
async def validated_tool(
    data: str = Field(min_length=1, description="Input data"),
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")
) -> dict:
    """Well-validated tool with clear constraints."""
    # Pydantic handles validation automatically
    return {"data": data, "timeout": timeout}
```

### 2. Provide Clear Documentation

```python
@tool
async def well_documented_tool(
    query: str,
    options: dict | None = None
) -> dict:
    """
    Process a query with optional configuration.

    This tool demonstrates comprehensive documentation with:
    - Clear parameter descriptions
    - Expected return value structure
    - Usage examples

    Args:
        query: The search query to process (required)
        options: Optional configuration dictionary:
            - "timeout": Maximum processing time (seconds)
            - "format": Output format preference

    Returns:
        Dictionary containing:
        - "result": Processed output
        - "metadata": Processing information

    Example:
        >>> await well_documented_tool("hello world")
        {"result": "HELLO WORLD", "metadata": {...}}
    """
    return {
        "result": query.upper(),
        "metadata": {"options": options or {}}
    }
```

### 3. Handle Errors Gracefully

```python
--8<-- "examples/docs/custom_tools_best_practices_error_handling.py"
```

### 4. Keep Tools Focused

Each tool should do one thing well:

```python
--8<-- "examples/docs/custom_tools_best_practices_focused.py"
```

## Testing Tools

### Unit Testing

```python
--8<-- "examples/docs/custom_tools_testing.py"
```

## Additional Resources

- See [DESIGN.md](.spec/v1/DESIGN.md) for the complete tools specification
- See [examples/docs/tools_*.py](../examples/docs/) for working examples
- See [FastDepends documentation](https://lancetnik.github.io/FastDepends/) for dependency injection details
