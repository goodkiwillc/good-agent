# Phase 4 Task 1: Message API Consolidation Proposal

## Current State Analysis

### Agent Public API
- **Total public methods/properties**: 74
- **Target**: <30 public methods

### Current Message Operation Patterns

We currently have **5 different ways** to add messages to an agent:

```python
# Pattern 1: agent.append() - Main convenience method
agent.append("Hello", role="user")
agent.append("Response", role="assistant", tool_calls=[...])

# Pattern 2: agent.add_tool_response() - Specialized method
agent.add_tool_response("result", tool_call_id="123", tool_name="search")

# Pattern 3: agent.add_tool_invocation() - Record tool execution
agent.add_tool_invocation(tool, response, parameters, tool_call_id)

# Pattern 4: agent.add_tool_invocations() - Record multiple tool executions
agent.add_tool_invocations(tool, [(params1, resp1), (params2, resp2)])

# Pattern 5: Direct message creation + append
msg = agent.model.create_message("Hello", role="user")
agent.append(msg)

# Pattern 6: Direct MessageList manipulation
agent.messages.append(msg)

# Internal Pattern 7: agent._append_message() - Used internally
agent._append_message(msg)  # Should remain private
```

### Usage Statistics

From code analysis:
- `append()` calls: 29 occurrences across 7 files
- `add_tool_response()`: Specialized tool message creation
- `add_tool_invocation()` / `add_tool_invocations()`: Tool invocation recording
- `messages.append()`: Direct list manipulation (advanced usage)

## Problems with Current API

1. **Cognitive overhead**: Too many ways to accomplish the same goal
2. **Inconsistent patterns**: Different methods for similar operations
3. **API surface bloat**: Contributes to 74 public methods
4. **Unclear best practices**: New users don't know which method to use

## Proposed Solution

### Consolidate to 2 Clear Patterns

#### Pattern 1: Convenience Method (90% of use cases)
```python
# User messages (default role)
agent.append("Hello")
agent.append("Hello", "How are you?")  # Multiple content parts

# Assistant messages
agent.append("Response", role="assistant")
agent.append("", role="assistant", tool_calls=[...])

# Tool messages
agent.append("Result", role="tool", tool_call_id="123")
agent.append("Result", role="tool", tool_call_id="123", tool_name="search")

# System messages (use set_system_message instead)
agent.set_system_message("You are helpful")  # Keep existing method
```

#### Pattern 2: Full Control (Advanced, 10% of use cases)
```python
# Create message with full control
msg = Message(content="Hello", role="user", context={...})
agent.messages.append(msg)

# Or use model.create_message for type-specific messages
msg = agent.model.create_message("Response", role="assistant", tool_calls=[...])
agent.messages.append(msg)
```

### Methods to Deprecate (with migration path)

1. **`add_tool_response()`** → `append(content, role="tool", tool_call_id=...)`
   ```python
   # Old
   agent.add_tool_response("result", tool_call_id="123", tool_name="search")

   # New
   agent.append("result", role="tool", tool_call_id="123", tool_name="search")
   ```

2. **Keep `add_tool_invocation()` and `add_tool_invocations()`**
   - These serve a different purpose: recording tool executions that happened outside the agent
   - They create both assistant message (with tool call) AND tool message (with response)
   - Not redundant with `append()` which only creates a single message
   - **Decision**: Keep these methods as they provide valuable functionality

## Implementation Plan

### Step 1: Enhance `append()` to support all message types (Day 1)
- ✅ Already supports `role="user"`, `role="assistant"`, `role="tool"`
- ✅ Already has proper overloads for type safety
- Current implementation is complete

### Step 2: Add deprecation warning to `add_tool_response()` (Day 1)
```python
def add_tool_response(
    self,
    content: str,
    tool_call_id: str,
    tool_name: str | None = None,
    **kwargs,
) -> None:
    """Add a tool response message to the conversation

    .. deprecated:: 0.3.0
        Use ``append(content, role="tool", tool_call_id=...)`` instead.
        This method will be removed in version 1.0.0.
    """
    warnings.warn(
        "add_tool_response() is deprecated. "
        "Use append(content, role='tool', tool_call_id=...) instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return self.append(
        content, role="tool", tool_call_id=tool_call_id, tool_name=tool_name, **kwargs
    )
```

### Step 3: Update internal code to use new pattern (Day 2)
- Find all `add_tool_response()` calls in codebase
- Replace with `append(role="tool", ...)`
- Update tests

### Step 4: Update documentation (Day 2)
- Document the 2 clear patterns
- Add migration guide
- Update all examples

### Step 5: Update CHANGELOG.md and MIGRATION.md (Day 2)
- Document deprecation
- Provide migration examples
- Set removal timeline (v1.0.0)

## Success Criteria

- ✅ 2 clear, documented patterns for adding messages
- ✅ Deprecation warning for `add_tool_response()`
- ✅ All internal code updated to use new patterns
- ✅ All tests passing
- ✅ Migration guide complete
- ✅ Examples updated

## Breaking Changes

**None** - This is a deprecation, not a removal. Backward compatibility maintained via deprecation warnings.

## Risk Assessment

**Risk Level**: Low
- Existing code continues to work
- Deprecation warnings guide migration
- Can be reverted easily if issues arise

## Timeline

- **Day 1**: Add deprecation warning, test
- **Day 2**: Update internal code, documentation
- **Total**: 2 days

## Questions for User

1. ✅ Confirm keeping `add_tool_invocation()` and `add_tool_invocations()` (they serve different purpose)
2. ✅ Confirm deprecation timeline (remove in v1.0.0)
3. Any other message-related methods that should be consolidated?

## Next Steps

After approval:
1. Implement deprecation warning
2. Update internal code
3. Update tests and documentation
4. Move to Phase 4 Task 2: Clarify call() vs execute()
