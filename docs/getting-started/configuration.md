# Configuration

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent provides extensive configuration options to customize your agent's behavior, from LLM parameters to debugging options. This page covers all configuration options with examples and best practices.

## Configuration Categories

Agent configuration is divided into three main categories:

- **LLM Configuration** - Model parameters, API settings, and generation options
- **Agent-Only Configuration** - Tools, templates, validation, and agent-specific behavior
- **Runtime Configuration** - Dynamic configuration changes and context scoping

## Basic Configuration

Configure your agent during initialization by passing parameters:

```python
from good_agent import Agent

async with Agent(
    "You are a helpful assistant",     # System prompt (positional)
    model="gpt-4o",                    # LLM model
    temperature=0.0,                   # Deterministic output
    max_tokens=1000,                   # Response length limit
    tools=[calculator, search],        # Available tools
    context={"env": "production"},     # Template variables
    debug=False,                       # Disable debug logging
) as agent:
    response = await agent.call("Hello!")
```

!!! tip "Configuration Loading Order"
    Configuration is resolved in this order (later values override earlier ones):
    
    1. Package defaults
    2. Environment variables (`OPENAI_API_KEY`, etc.)
    3. Constructor parameters
    4. Context manager overrides (`with agent.config(...)`)
    5. Per-call overrides (`agent.call(..., temperature=0.1)`)

## LLM Configuration

### Model Selection

Choose from any LiteLLM-supported provider:

```python
# OpenAI models (default provider)
async with Agent(model="gpt-4o") as agent:
    ...

async with Agent(model="gpt-4o-mini") as agent:
    ...

# Anthropic models
async with Agent(model="claude-3-5-sonnet-20241022") as agent:
    ...

# Google models
async with Agent(model="gemini-pro") as agent:
    ...

# Azure OpenAI
async with Agent(
    model="azure/my-deployment-name",
    base_url="https://my-resource.openai.azure.com",
    api_version="2024-02-01",
) as agent:
    ...
```

### Generation Parameters

Fine-tune LLM output behavior:

```python
async with Agent(
    "You are a creative writer",
    
    # Core generation params
    temperature=0.8,           # Higher = more creative (0.0-2.0)
    top_p=0.9,                # Nucleus sampling (0.0-1.0)
    max_tokens=2000,          # Maximum response tokens
    max_completion_tokens=1500,  # Alternative to max_tokens
    
    # Penalties
    frequency_penalty=0.1,    # Reduce repetition (-2.0 to 2.0)
    presence_penalty=0.1,     # Encourage topic diversity (-2.0 to 2.0)
    
    # Control options
    seed=42,                  # Reproducible outputs (when supported)
    stop=["END", "STOP"],     # Stop sequences
    n=1,                      # Number of completions
    
    # Advanced
    logprobs=True,            # Include log probabilities
    top_logprobs=5,           # Number of top logprobs
) as agent:
    ...
```

### Authentication & API Settings

Configure API access and timeouts:

```python
from httpx import Timeout

async with Agent(
    model="gpt-4o",
    
    # API authentication
    api_key="sk-...",                    # Override env var
    base_url="https://api.openai.com/v1", # Custom endpoint
    
    # Request configuration
    timeout=Timeout(30.0),               # Request timeout
    extra_headers={"X-Custom": "value"}, # Additional headers
    
    # Provider-specific
    api_version="2024-02-01",            # For Azure/other providers
    deployment_id="my-deployment",        # For Azure
    custom_llm_provider="custom",        # For custom providers
) as agent:
    ...
```

!!! warning "API Key Security"
    Never hardcode API keys. Use environment variables or secure credential management:
    
    ```bash
    export OPENAI_API_KEY="sk-..."
    export ANTHROPIC_API_KEY="sk-ant-..."
    ```

### Tool Configuration

Control how the LLM uses tools:

```python
async with Agent(
    "You are a helpful assistant",
    tools=[calculator, search, weather],
    
    # Tool behavior
    tool_choice="auto",              # "auto", "none", or specific tool
    parallel_tool_calls=True,        # Allow multiple simultaneous calls
    
    # Tool filtering (Good Agent specific)
    include_tool_filters=["calc*"],  # Only tools matching patterns
    exclude_tool_filters=["debug*"], # Exclude tools matching patterns
) as agent:
    ...
```

## Agent-Only Configuration

### Context & Templates

Provide dynamic values for message templating:

```python
--8<-- "tests/unit/templating/test_template_context.py:23:29"
```

Context variables can be used in any message:

```python
agent.append("Weather in {{location}} is {{temp}}°{{unit}}")
# Renders: "Weather in New York is 72°F"
```

See [Templates](../core/agents.md#templates) for advanced templating features.

### Validation & Debugging

Control message validation and debug output:

```python
async with Agent(
    "Assistant",
    
    # Message validation
    message_validation_mode="warn",    # "strict", "warn", "silent"
    
    # Debug output
    debug=True,                        # Enable debug logging
    litellm_debug=True,                # Enable LiteLLM debug logs
    print_messages=True,               # Print messages to console
    print_messages_mode="display",     # "display", "llm", "raw"
    print_messages_role=["user", "assistant"],  # Which roles to print
    print_messages_markdown=True,      # Format as markdown
) as agent:
    ...
```

### Template System

Configure the template engine:

```python
async with Agent(
    "Assistant",
    
    # Template configuration
    template_path="/path/to/templates",   # Custom template directory
    undefined_behavior="log",             # "strict", "silent", "log"
    template_functions={"now": datetime.now},  # Custom template functions
    enable_template_cache=True,           # Cache compiled templates
    use_template_sandbox=False,           # Disable sandboxed execution
) as agent:
    ...
```

### MCP Server Integration

Load Model Context Protocol servers for external tools:

```python
async with Agent(
    "Assistant with MCP tools",
    mcp_servers=[
        "filesystem",                     # Server name
        {"name": "web", "command": "npx @modelcontextprotocol/server-web"},
        {"name": "git", "uri": "stdio://git-mcp"},
    ],
) as agent:
    # MCP tools are automatically available
    await agent.call("List files in current directory")
```

!!! note "MCP Server Format"
    MCP servers can be specified as:
    
    - `str` - Server name (must be in PATH)
    - `dict` - Full server configuration with command/URI
    
    See [Tools](../core/tools.md#mcp-integration) for details.

## Dynamic Configuration

### Context Managers

Temporarily override configuration for specific operations:

```python
--8<-- "tests/unit/agent/test_agent.py:94:114"
```

Context managers can be nested and scoped:

```python
async with agent.config(temperature=0.8):
    # Creative mode
    async with agent.config(max_tokens=500):
        # Creative but concise
        response = await agent.call("Write a poem")
```

### Per-Call Overrides

Override configuration for individual calls:

```python
# Override specific parameters
response = await agent.call(
    "Analyze this data", 
    temperature=0.0,      # Deterministic
    max_tokens=2000,      # Longer response
    stream=True           # Enable streaming
)

# Override with structured output
from pydantic import BaseModel

class Analysis(BaseModel):
    summary: str
    score: float

response = await agent.call(
    "Analyze sentiment",
    response_model=Analysis,  # Structured output
    temperature=0.2           # More consistent
)
```

## Configuration Reference

### LLM Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"gpt-4o-mini"` | LLM model identifier |
| `temperature` | `float` | `0.7` | Sampling temperature (0.0-2.0) |
| `max_tokens` | `int` | `None` | Maximum tokens in response |
| `max_completion_tokens` | `int` | `None` | Alternative to max_tokens |
| `top_p` | `float` | `1.0` | Nucleus sampling threshold |
| `n` | `int` | `1` | Number of completions |
| `stream_options` | `dict` | `{}` | Streaming configuration |
| `stop` | `str \| list[str]` | `None` | Stop sequences |
| `presence_penalty` | `float` | `0.0` | Presence penalty (-2.0 to 2.0) |
| `frequency_penalty` | `float` | `0.0` | Frequency penalty (-2.0 to 2.0) |
| `logit_bias` | `dict` | `{}` | Logit bias dictionary |
| `user` | `str` | `None` | User identifier |
| `seed` | `int` | `None` | Random seed for reproducibility |
| `tool_choice` | `str \| dict` | `"auto"` | Tool selection strategy |
| `parallel_tool_calls` | `bool` | `True` | Allow parallel tool execution |

### API & Authentication

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | env var | API key for provider |
| `base_url` | `str` | provider default | API base URL |
| `api_version` | `str` | `None` | API version (Azure, etc.) |
| `timeout` | `float \| Timeout` | `60.0` | Request timeout |
| `extra_headers` | `dict` | `{}` | Additional HTTP headers |
| `deployment_id` | `str` | `None` | Deployment identifier |
| `custom_llm_provider` | `str` | `None` | Custom provider name |

### Agent-Specific Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tools` | `list` | `[]` | Available tools/functions |
| `mcp_servers` | `list` | `[]` | MCP server configurations |
| `include_tool_filters` | `list[str]` | `[]` | Include tool name patterns |
| `exclude_tool_filters` | `list[str]` | `[]` | Exclude tool name patterns |
| `context` | `dict` | `{}` | Template context variables |
| `template_path` | `str` | `None` | Custom template directory |
| `undefined_behavior` | `str` | `"silent"` | Undefined variable handling |
| `name` | `str` | `None` | Agent instance name |
| `debug` | `bool` | `False` | Enable debug logging |
| `message_validation_mode` | `str` | `"warn"` | Message validation level |

## Environment Variables

Good Agent respects standard LiteLLM environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI authentication | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic authentication | `sk-ant-...` |
| `GOOGLE_API_KEY` | Google AI authentication | `AIza...` |
| `OPENAI_BASE_URL` | Custom OpenAI endpoint | `https://api.custom.com/v1` |
| `LITELLM_LOG` | LiteLLM logging level | `DEBUG`, `INFO` |

Set environment variables before running your application:

```bash
export OPENAI_API_KEY="sk-..."
export LITELLM_LOG="INFO"
python your_agent.py
```

## Best Practices

### Production Configuration

For production deployments:

```python
async with Agent(
    system_prompt,
    model="gpt-4o",              # Stable, high-quality model
    temperature=0.1,             # Lower temperature for consistency
    max_tokens=2000,             # Reasonable limit
    timeout=Timeout(30.0),       # Reasonable timeout
    message_validation_mode="strict",  # Catch issues early
    debug=False,                 # Disable debug in production
    print_messages=False,        # Don't print to console
) as agent:
    ...
```

### Development Configuration

For local development:

```python
async with Agent(
    system_prompt,
    model="gpt-4o-mini",         # Faster, cheaper model
    temperature=0.7,             # Default creativity
    debug=True,                  # Enable debugging
    print_messages=True,         # See message flow
    print_messages_markdown=True,  # Pretty formatting
    message_validation_mode="warn",  # Show warnings
) as agent:
    ...
```

### Configuration Validation

Validate your configuration at startup:

```python
def validate_config():
    import os
    
    # Check required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set")
    
    # Test agent initialization
    try:
        async with Agent("Test") as agent:
            await agent.call("Hello")
    except Exception as e:
        raise RuntimeError(f"Agent configuration failed: {e}")

# Run validation before main application
validate_config()
```

## Troubleshooting

### Configuration Not Applied

```python
# ❌ Configuration after initialization
agent = Agent("Assistant")
agent.config.temperature = 0.5  # Won't work

# ✅ Configuration during initialization
async with Agent("Assistant", temperature=0.5) as agent:
    ...
```

### Type Errors

```python
# ❌ Wrong types
async with Agent(temperature="0.5") as agent:  # Should be float
    ...

# ✅ Correct types
async with Agent(temperature=0.5) as agent:
    ...
```

### Environment Variable Issues

```bash
# Check if variables are set
echo $OPENAI_API_KEY

# Verify in Python
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

### Provider-Specific Settings

Different providers may require specific configuration:

```python
# Azure OpenAI
async with Agent(
    model="azure/gpt-4",
    base_url="https://resource.openai.azure.com",
    api_version="2024-02-01",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
) as agent:
    ...

# Anthropic
async with Agent(
    model="claude-3-sonnet-20240229",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
) as agent:
    ...
```

## Next Steps

- **[Core Agents](../core/agents.md)** - Deep dive into agent lifecycle and state management
- **[Tools](../core/tools.md)** - Add custom capabilities to your agents
- **[Structured Output](../features/structured-output.md)** - Extract typed data from responses
- **[Agent Modes](../features/modes.md)** - Dynamic configuration switching
