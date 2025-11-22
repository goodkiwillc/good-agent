# Tools

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent provides a powerful tool system that enables agents to interact with external services, APIs, and custom functions. Tools use standard Python functions with dependency injection, type hints, and automatic schema generation. This page covers tool definition, registration, execution, and integration patterns.

## Tool Basics

### Defining Tools

Create tools using the `@tool` decorator on any Python function:

```python
--8<-- "examples/docs/tools_basic_definition.py:10:24"
```

**Key Features:**

- **Async support**: Tools can be `async` or sync functions
- **Type hints**: Parameter and return types are automatically converted to JSON schema
- **Docstrings**: Function docstrings become tool descriptions
- **Validation**: Input parameters are validated using Pydantic

### Tool Registration

Tools are registered automatically when used with agents:

```python
--8<-- "examples/docs/tools_registration.py:26:31"
```

**Manual Registration:**

```python
--8<-- "examples/docs/tools_manual_registration.py:18:24"
```

### Tool Metadata

Customize tool behavior with the decorator:

```python
--8<-- "examples/docs/tools_metadata.py:7:16"
```

## Dependency Injection

Good Agent uses FastDepends for powerful dependency injection in tools:

### Basic Dependencies

```python
--8<-- "examples/docs/tools_dependencies_basic.py:9:33"
```

### Agent Context Dependencies

Access agent state and context within tools:

```python
--8<-- "examples/docs/tools_context_dependency.py:10:24"
```

### Real-World Example

```python
--8<-- "tests/spec/test_public_contract.py:280:320"
```

## Tool Execution

### Automatic Execution

Tools are called automatically by the LLM during conversation:

```python
--8<-- "examples/docs/tools_execution_automatic.py"
```

### Direct Invocation

Invoke tools programmatically for testing or custom workflows:

```python
--8<-- "examples/docs/tools_direct_invocation.py:20:32"
```

**Advanced Invocation Options:**

```python
--8<-- "examples/docs/tools_invocation_options.py:20:35"
```

### Error Handling

Tools should handle errors gracefully:

```python
--8<-- "examples/docs/tools_error_handling.py"
```

## Component-Based Tools

Define tools as methods in AgentComponent classes for better organization:

### Basic Component Tools

```python
--8<-- "examples/docs/tools_component_basic.py"
```

### Stateful Components

Components maintain state across tool calls:

```python
--8<-- "examples/docs/tools_component_stateful.py"
```

## Model Context Protocol (MCP)

Good Agent supports MCP for integrating external tool servers:

### Loading MCP Servers

```python
--8<-- "examples/docs/tools_mcp_basic.py"
```

### MCP Server Configuration

MCP servers can be configured with various options:

```python
--8<-- "examples/docs/tools_mcp_config.py"
```

### MCP Tool Lifecycle

MCP servers are managed automatically:

```python
--8<-- "examples/docs/tools_mcp_lifecycle.py"
```

## Advanced Tool Patterns

### Conditional Tool Registration

Control when tools are available:

```python
--8<-- "examples/docs/tools_conditional_registration.py"
```

### Tool Filtering

Filter available tools by name patterns:

```python
--8<-- "examples/docs/tools_filtering.py"
```

### Dynamic Tool Registration

Add tools during agent execution:

```python
--8<-- "examples/docs/tools_dynamic_registration.py"
```

### Tool Chaining

Tools can call other tools:

```python
--8<-- "examples/docs/tools_chaining.py"
```

## Tool Testing

### Unit Testing Tools

Test tools independently:

```python
--8<-- "examples/docs/tools_testing_unit.py"
```

### Integration Testing

Test tools within agent context:

```python
--8<-- "examples/docs/tools_testing_integration.py"
```

### Mocking Tools

Mock tools for testing:

```python
--8<-- "examples/docs/tools_testing_mocking.py"
```

## Tool Schema & Validation

### Automatic Schema Generation

Good Agent automatically generates JSON schemas from Python type hints:

```python
--8<-- "examples/docs/tools_schema_generation.py"
```

### Custom Validation

Add custom validation logic:

```python
--8<-- "examples/docs/tools_validation_custom.py"
```

### Complex Type Support

Tools support complex Pydantic models:

```python
--8<-- "examples/docs/tools_complex_types.py"
```

## Agent as a Tool

You can convert any Agent into a tool that can be used by another Agent. This enables powerful multi-agent orchestration patterns where agents delegate complex tasks to specialized sub-agents.

### Creating an Agent Tool

Use the `as_tool()` method to convert an agent into a tool:

```python
--8<-- "examples/docs/tools_agent_as_tool.py"
```

### Multi-Turn Sessions

By default, Agent-as-a-Tool supports multi-turn conversations (`multi_turn=True`). This means the sub-agent maintains its state and conversation history across multiple calls from the parent agent.

When a sub-agent is called multiple times:
1. The first call creates a new session and returns a session ID (e.g., `<researcher session_id="1">...`)
2. Subsequent calls by the parent agent will automatically use this session ID to continue the conversation
3. State (memory, context) persists for the duration of the parent's lifecycle

```python
--8<-- "examples/docs/tools_agent_as_tool_multiturn.py:12:16"
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
--8<-- "examples/docs/tools_performance.py"
```

### Dependency Management

- **Singleton dependencies**: Use singletons for shared resources
- **Lazy initialization**: Initialize expensive resources only when needed
- **Resource cleanup**: Properly close connections and clean up resources

```python
--8<-- "examples/docs/tools_dependencies_singleton.py"
```

### Tool Organization

- **Group related tools** in components or modules
- **Use consistent naming** conventions (verb_noun pattern)
- **Document dependencies** and side effects clearly
- **Separate concerns** (data access, business logic, formatting)

```python
--8<-- "examples/docs/tools_organization.py"
```

## Troubleshooting

### Common Issues

```python
--8<-- "examples/docs/tools_best_practices.py"
```

### Tool Registration Errors

```python
--8<-- "examples/docs/tools_debug_registration.py"
```

### Dependency Injection Issues

```python
--8<-- "examples/docs/tools_debug_dependencies.py"
```

### Tool Execution Errors

```python
--8<-- "examples/docs/tools_debug_execution.py"
```

### MCP Connection Issues

```python
--8<-- "examples/docs/tools_debug_mcp.py"
```

## Next Steps

- **[Events](events.md)** - React to tool execution events and lifecycle changes
- **[Agent Modes](../features/modes.md)** - Use tools in different agent contexts
- **[Custom Components](../extensibility/components.md)** - Build reusable tool collections
- **[Advanced Tool Patterns](../extensibility/custom-tools.md)** - Complex tool architectures and patterns
