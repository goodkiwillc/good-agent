# Custom Tools

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent's tool system allows you to create custom tools with parameter validation, type safety, and dependency injection. This guide covers the core patterns for building tools.

## Basic Tool Definition

Tools are Python functions decorated with `@tool`:

```python
--8<-- "examples/docs/custom_tools_basic.py"
```

## Parameter Validation with Pydantic

Use Pydantic's `Field` for comprehensive parameter validation:

```python
--8<-- "examples/docs/custom_tools_parameter_validation.py"
```

## Structured Return Types

Use Pydantic models for structured, validated return values:

```python
--8<-- "examples/docs/custom_tools_structured_returns.py"
```

## Error Handling

Tools should handle errors gracefully and provide clear error messages:

```python
--8<-- "examples/docs/custom_tools_error_handling.py"
```

## Dependency Injection

> **⚠️ Note**: The dependency injection API is currently under construction. The patterns shown below may change in future versions.

Good Agent uses [FastDepends](https://lancetnik.github.io/FastDepends/) for dependency injection in tools.

### Basic Dependency Injection

```python
--8<-- "examples/docs/custom_tools_dependency_injection.py"
```

### Accessing Agent Context

To access the agent instance and other context from within a tool:

```python
--8<-- "examples/docs/custom_tools_context_access.py"
```

## Tool Composition

Build complex workflows by calling tools from within other tools:

```python
--8<-- "examples/docs/custom_tools_composition.py"
```

## Best Practices

### 1. Use Type Hints and Validation

```python
--8<-- "examples/docs/custom_tools_best_practices_validation.py"
```

### 2. Provide Clear Documentation

```python
--8<-- "examples/docs/custom_tools_best_practices_documentation.py"
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
